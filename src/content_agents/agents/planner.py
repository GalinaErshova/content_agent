"""
agents/planner.py — агент ПЛАНИРОВАНИЯ (через LLM).

Просит модель спроектировать структуру материала: какие разделы делать, какие
типы контента в каждом и где нужна иллюстрация. Модель возвращает JSON, который
мы разбираем. Если модель вернула некорректный ответ (бывает!), срабатывает
ДЕТЕРМИНИРОВАННЫЙ fallback — один раздел на тему. Это делает агент устойчивым:
конвейер не падает из-за капризов генерации.

Промты вынесены в config/prompts/ru/ (planner.system / planner.user).
"""

from __future__ import annotations

from ..graph.state import PipelineState
from ..logger import get_logger
from ..models import ContentPlan, ContentSectionPlan
from ..ports import LLMProvider
from ..prompts import render
from ..utils import extract_json

log = get_logger(__name__)


class PlannerAgent:
    name = "planner"

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def run(self, state: PipelineState) -> str:
        cfg = state.config
        topics = ", ".join(t.name for t in state.topics) or "Основные понятия"

        # 1. Спрашиваем модель (промты — во внешних файлах).
        raw = self.llm.complete(
            system=render("planner.system"),
            user=render(
                "planner.user",
                topics=topics,
                audience_title=cfg.audience.title,
                reading_level=cfg.audience.reading_level,
                volume=cfg.target_volume,
                content_types=", ".join(cfg.content_types),
            ),
        )

        # 2. Разбираем JSON-ответ.
        data = extract_json(raw)
        sections: list[ContentSectionPlan] = []
        if isinstance(data, list):
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or f"Раздел {i + 1}").strip()
                # Оставляем только типы, которые пользователь запросил при запуске.
                types = [t for t in item.get("content_types", []) if t in cfg.content_types]
                types = types or list(cfg.content_types)
                sections.append(ContentSectionPlan(
                    section_id=f"s{i + 1}",
                    title=title,
                    content_types=types,
                    wants_illustration=bool(item.get("wants_illustration", i < 2)),
                ))

        # 3. Fallback, если модель не дала валидного плана.
        if not sections:
            log.warning("Planner: не удалось разобрать план из ответа модели — fallback")
            for i, topic in enumerate(state.topics):
                sections.append(ContentSectionPlan(
                    section_id=f"s{i + 1}",
                    title=topic.name,
                    content_types=list(cfg.content_types),
                    wants_illustration=(i < 2),
                ))

        state.content_plan = ContentPlan(sections=sections)
        log.info("План: %d разделов для профиля '%s'", len(sections), cfg.audience.id)
        return f"разделов: {len(sections)} (профиль: {cfg.audience.title})"
