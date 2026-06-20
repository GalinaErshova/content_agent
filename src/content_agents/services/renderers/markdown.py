"""
services/renderers/markdown.py — сборка итогового материала в Markdown.

Рендерер реализует порт Renderer. Он НЕ генерирует контент — он только красиво
раскладывает уже готовые черновики, картинки и список источников в .md-файл.
"""

from __future__ import annotations

import os

from ...models import Draft, GeneratedImage
from ._common import TYPE_TITLES, group_by_section, image_for_section


class MarkdownRenderer:
    fmt = "markdown"

    def render(self, *, title: str, drafts: list[Draft], images: list[GeneratedImage],
               citations_index: dict[str, str], out_dir: str) -> str:
        lines: list[str] = [f"# {title}", ""]

        # По разделам: заголовок раздела → иллюстрация → блоки контента.
        for section_id, section_drafts in group_by_section(drafts):
            section_title = section_drafts[0].title
            lines.append(f"## {section_title}")
            lines.append("")

            img = image_for_section(images, section_id)
            if img:
                # Относительный путь, чтобы картинка открывалась рядом с .md.
                rel = os.path.relpath(img.file_path, out_dir)
                lines.append(f"![{img.caption}]({rel})")
                lines.append(f"*{img.caption}*")
                lines.append("")

            for d in section_drafts:
                lines.append(f"### {TYPE_TITLES.get(d.content_type, d.content_type)}")
                lines.append("")
                lines.append(d.text)
                # Маркеры цитат в конце блока: [^chunk_id] — простая, читаемая схема.
                if d.citations:
                    refs = " ".join(f"[^{c.chunk_id}]" for c in d.citations)
                    lines.append("")
                    lines.append(f"Источники: {refs}")
                lines.append("")

        # Раздел 'Источники' — расшифровка маркеров [^chunk_id] → откуда взято.
        if citations_index:
            lines.append("## Источники")
            lines.append("")
            for chunk_id, locator in citations_index.items():
                lines.append(f"[^{chunk_id}]: {locator}")
            lines.append("")

        path = os.path.join(out_dir, "summary.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path
