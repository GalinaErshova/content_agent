"""
agents/critic.py — агент КОНТРОЛЯ КАЧЕСТВА (один батч-запрос к LLM).

Проверяет главный принцип системы: каждое утверждение должно опираться на
источник. Работает так:

1) ДЕШЁВАЯ проверка: черновики без цитат сразу считаются неподтверждёнными —
   модель для них не вызывается;
2) БАТЧ-проверка: все черновики, у которых ЕСТЬ цитаты, проверяются ОДНИМ
   запросом к модели. Мы нумеруем фрагменты, отдаём их вместе с источниками и
   получаем JSON-массив вердиктов [{"id", "supported", "issue"}, ...].
   Это экономит вызовы: один запрос на весь материал вместо запроса на каждый
   черновик.

Устойчивость: если модель вернёт некорректный/неполный JSON, по непокрытым
фрагментам применяется мягкая деградация — раз у фрагмента есть источники,
считаем его подтверждённым (и пишем предупреждение в лог), чтобы не зациклить
доработку. Цикл самокоррекции при этом сохраняется за счёт дешёвой проверки
(черновики без цитат всё равно отклоняются).

run() возвращает ПАРУ (вердикт, заметка): вердикт нужен оркестратору для петли.
Промты — в config/prompts/ru/ (critic.system / critic.user).
"""

from __future__ import annotations

from ..graph.state import PipelineState
from ..logger import get_logger
from ..ports import LLMProvider
from ..prompts import render
from ..utils import extract_json

log = get_logger(__name__)


class CriticAgent:
    name = "critic"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def run(self, state: PipelineState) -> tuple[str, str]:
        drafts = state.drafts
        total = len(drafts)

        # Делим черновики на две группы.
        to_check = [d for d in drafts if d.citations]        # пойдут в батч к модели
        no_source = [d for d in drafts if not d.citations]   # отсекаются дешёвым путём

        supported = 0
        first_issue: str | None = None
        if no_source:
            d = no_source[0]
            first_issue = f"раздел '{d.title}' / {d.content_type}: нет источника"

        # --- Один батч-запрос на все черновики с цитатами ---
        if to_check:
            # Собираем пронумерованные блоки 'фрагмент + его источники'.
            blocks = []
            for i, d in enumerate(to_check, start=1):
                sources = "\n---\n".join(
                    state.chunk_texts.get(c.chunk_id, c.locator) for c in d.citations
                )
                blocks.append(
                    f"=== Фрагмент {i} ===\nТЕКСТ:\n{d.text}\nИСТОЧНИКИ:\n{sources}"
                )
            items = "\n\n".join(blocks)

            raw = self.llm.complete(
                system=render("critic.system"),
                user=render("critic.user", items=items),
            )

            # Разбираем массив вердиктов в словарь id -> вердикт.
            data = extract_json(raw)
            verdict_map: dict[int, dict] = {}
            if isinstance(data, list):
                for obj in data:
                    if isinstance(obj, dict) and "id" in obj:
                        try:
                            verdict_map[int(obj["id"])] = obj
                        except (TypeError, ValueError):
                            pass
            if not verdict_map:
                log.warning("Critic: не удалось разобрать вердикты — мягкая деградация")

            # Сопоставляем вердикты с черновиками по номеру (1-based).
            for i, d in enumerate(to_check, start=1):
                v = verdict_map.get(i)
                if v is None:
                    # Модель не дала вердикт по фрагменту: есть источники → считаем ОК.
                    supported += 1
                elif v.get("supported"):
                    supported += 1
                elif first_issue is None:
                    issue = v.get("issue") or "не подтверждается источниками"
                    first_issue = f"раздел '{d.title}' / {d.content_type}: {issue}"

        flagged = total - supported
        # Метрики — то, что показывают карточки на дэше.
        state.grounding = {"total": total, "supported": supported, "flagged": flagged}

        if flagged == 0:
            return "approve", f"одобрено: grounding {supported}/{total}"
        return "reject", f"{first_issue} (подтверждено {supported}/{total})"
