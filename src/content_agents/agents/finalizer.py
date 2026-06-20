"""
agents/finalizer.py — агент ФИНАЛЬНОЙ СБОРКИ.

Берёт одобренные черновики, иллюстрации и индекс источников и собирает итог
в форматы, выбранные при запуске (markdown/html/slides). Каждый формат рисует
свой рендерер; finalizer лишь раздаёт им данные и собирает пути к файлам.

Учитывает strict_grounding: если включён строгий режим, неподтверждённые
черновики в финал не попадают (выбрасываются). Иначе — попадают как есть
(они уже помечены критиком в метриках).
"""

from __future__ import annotations

from ..graph.state import PipelineState
from ..logger import get_logger
from ..models import OutputArtifact
from ..services.renderers.html import HtmlRenderer
from ..services.renderers.markdown import MarkdownRenderer
from ..services.renderers.slides import SlidesRenderer

log = get_logger(__name__)

# Реестр рендереров по имени формата.
RENDERERS = {
    "markdown": MarkdownRenderer(),
    "html": HtmlRenderer(),
    "slides": SlidesRenderer(),
}


class FinalizerAgent:
    name = "finalizer"

    def __init__(self, out_dir: str):
        self.out_dir = out_dir

    def run(self, state: PipelineState) -> str:
        cfg = state.config

        drafts = state.drafts
        if cfg.strict_grounding:
            # Строгий режим: оставляем только подтверждённые источниками черновики.
            drafts = [d for d in drafts if d.citations]

        title = state.documents[0].title if state.documents else "Учебный материал"

        artifacts: list[OutputArtifact] = []
        for fmt in cfg.outputs:
            renderer = RENDERERS.get(fmt)
            if renderer is None:
                log.warning("Нет рендерера для формата %s", fmt)
                continue
            path = renderer.render(
                title=title,
                drafts=drafts,
                images=state.images,
                citations_index=state.citations_index,
                out_dir=self.out_dir,
            )
            artifacts.append(OutputArtifact(fmt=fmt, path=path))  # type: ignore[arg-type]

        # Сохраняем артефакты в состоянии — их заберёт JobManager/дэш.
        state.artifacts.extend(artifacts)

        return f"собрано форматов: {len(artifacts)} ({', '.join(a.fmt for a in artifacts)})"
