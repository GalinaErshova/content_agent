"""
agents/illustrator.py — агент ИЛЛЮСТРАЦИЙ.

Для разделов, помеченных в плане (wants_illustration), составляет текстовый
промпт на основе содержания и просит ImageProvider сгенерировать картинку.
Сохраняет PNG на диск и привязывает к разделу (GeneratedImage).
"""

from __future__ import annotations

import os

from ..graph.state import PipelineState
from ..logger import get_logger
from ..models import GeneratedImage
from ..ports import ImageProvider, LLMProvider
from ..prompts import render

log = get_logger(__name__)


class IllustratorAgent:
    name = "illustrator"

    def __init__(self, llm: LLMProvider, image: ImageProvider, out_dir: str):
        self.llm = llm
        self.image = image
        self.out_dir = out_dir            # куда сохранять PNG (подпапка images/)

    def run(self, state: PipelineState) -> str:
        plan = state.content_plan
        assert plan is not None

        images_dir = os.path.join(self.out_dir, "images")
        os.makedirs(images_dir, exist_ok=True)

        made = 0
        for section in plan.sections:
            if not section.wants_illustration:
                continue

            # Составляем промпт для картинки через внешние шаблоны. Просим у LLM
            # короткое визуальное описание — так иллюстрация будет содержательной.
            prompt = self.llm.complete(
                system=render("illustrator.system"),
                user=render("illustrator.user", section_title=section.title),
            ).strip()[:200]

            png_bytes = self.image.generate(prompt)
            path = os.path.join(images_dir, f"{section.section_id}.png")
            with open(path, "wb") as f:
                f.write(png_bytes)

            state.images.append(GeneratedImage(
                section_id=section.section_id,
                file_path=path,
                caption=f"Иллюстрация: {section.title}",
                prompt=prompt,
            ))
            made += 1

        return f"иллюстраций: {made}"
