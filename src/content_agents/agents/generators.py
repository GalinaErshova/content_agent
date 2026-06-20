"""
agents/generators.py — агент ГЕНЕРАЦИИ контента.

Для каждого раздела и каждого запрошенного типа (саммари/объяснение/материалы):
1) достаёт из RAG-индекса релевантные фрагменты (retrieval);
2) формирует промпт с учётом профиля аудитории и этого контекста;
3) просит модель сгенерировать текст;
4) прикрепляет к черновику ЦИТАТЫ на использованные фрагменты — это и делает
   контент 'data-driven' (каждое утверждение опирается на источник).

ДЕМОНСТРАЦИЯ ЦИКЛА САМОКОРРЕКЦИИ:
на первом проходе (revision_count == 0) блок 'edu_material' намеренно остаётся
без цитат — как будто вопросы для самопроверки сгенерированы 'из головы', а не
из источника. Критик это заметит и вернёт материал на доработку. На повторном
проходе цитаты добавляются, и критик одобряет. В реальной системе цитаты
ставятся всегда по факту retrieval — здесь это упрощение РАДИ НАГЛЯДНОСТИ,
помечено комментарием ниже.
"""

from __future__ import annotations

from ..graph.state import PipelineState
from ..logger import get_logger
from ..models import Citation, Draft
from ..ports import LLMProvider, VectorStore
from ..prompts import render

log = get_logger(__name__)


class GeneratorsAgent:
    name = "generators"

    def __init__(self, llm: LLMProvider, store: VectorStore):
        self.llm = llm
        self.store = store

    def run(self, state: PipelineState) -> str:
        cfg = state.config
        plan = state.content_plan
        assert plan is not None, "Planner должен отработать раньше Generators"

        drafts: list[Draft] = []
        for section in plan.sections:
            # --- Retrieval: ищем фрагменты, релевантные теме раздела ---
            # Хранилище само векторизует текст запроса (RAG за портом VectorStore).
            relevant = self.store.search(section.title, k=3) if state.vector_store else []
            context = "\n---\n".join(c.text for c in relevant) or "(контекст не найден)"

            # Цитаты на найденные фрагменты + пополняем индексы источников.
            citations = [Citation(chunk_id=c.id, locator=c.locator) for c in relevant]
            for c in relevant:
                state.citations_index[c.id] = c.locator
                state.chunk_texts[c.id] = c.text      # текст нужен критику для проверки

            # Системный промт собираем один раз на раздел — он зависит от профиля,
            # а не от типа контента. Тексты промтов лежат в config/prompts/ru/.
            a = cfg.audience
            system = render(
                "generators.system",
                audience_title=a.title, reading_level=a.reading_level, tone=a.tone,
                prior_knowledge=a.prior_knowledge, glossary_policy=a.glossary_policy,
                language=cfg.language,
            )

            for ctype in section.content_types:
                # Имя промта-задачи = generators.<тип>: summary / explanation / edu_material.
                user = render(f"generators.{ctype}",
                              section_title=section.title, context=context)
                text = self.llm.complete(system=system, user=user)

                # ↓↓↓ ДЕМО-поведение цикла самокоррекции (см. docstring модуля) ↓↓↓
                if ctype == "edu_material" and state.revision_count == 0:
                    draft_citations = []        # первый проход: 'забыли' проставить источники
                else:
                    draft_citations = citations
                # ↑↑↑ В продакшене здесь всегда было бы draft_citations = citations ↑↑↑

                drafts.append(Draft(
                    section_id=section.section_id,
                    content_type=ctype,
                    title=section.title,
                    text=text,
                    citations=draft_citations,
                ))

        state.drafts = drafts
        suffix = " (доработка)" if state.revision_count > 0 else ""
        return f"черновиков: {len(drafts)}{suffix}"
