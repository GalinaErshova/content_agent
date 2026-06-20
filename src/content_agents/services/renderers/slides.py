"""
services/renderers/slides.py — сборка слайдов в формате Marp.

Marp — это обычный Markdown, где '---' разделяет слайды, а в начале файла
стоит блок настроек ('marp: true'). Такой .md открывается как презентация
в VS Code (расширение Marp) или конвертируется в PDF/HTML командой marp-cli.

Мы выбрали Marp, потому что слайды получаются из того же контента почти
бесплатно: один раздел → один-два слайда. .pptx — в дорожной карте (python-pptx).
"""

from __future__ import annotations

import os

from ...models import Draft, GeneratedImage
from ._common import TYPE_TITLES, group_by_section, image_for_section


class SlidesRenderer:
    fmt = "slides"

    def render(self, *, title: str, drafts: list[Draft], images: list[GeneratedImage],
               citations_index: dict[str, str], out_dir: str) -> str:
        # Front-matter Marp + титульный слайд.
        lines: list[str] = ["---", "marp: true", "paginate: true", "---", "",
                            f"# {title}", "", "---", ""]

        for section_id, section_drafts in group_by_section(drafts):
            section_title = section_drafts[0].title

            # Слайд раздела: заголовок + (если есть) иллюстрация.
            lines.append(f"## {section_title}")
            img = image_for_section(images, section_id)
            if img:
                rel = os.path.relpath(img.file_path, out_dir)
                lines.append(f"![w:480]({rel})")
            lines.append("")
            lines.append("---")
            lines.append("")

            # На слайды кладём компактные версии: для саммари — текст целиком,
            # для остального — первые строки, чтобы не перегружать слайд.
            for d in section_drafts:
                lines.append(f"### {section_title} — {TYPE_TITLES.get(d.content_type, d.content_type)}")
                lines.append("")
                snippet = d.text if d.content_type == "summary" else _shorten(d.text)
                lines.append(snippet)
                lines.append("")
                lines.append("---")
                lines.append("")

        path = os.path.join(out_dir, "slides.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path


def _shorten(text: str, max_lines: int = 5) -> str:
    """Оставить первые несколько строк — слайд не должен быть простынёй текста."""
    rows = [r for r in text.splitlines() if r.strip()]
    return "\n".join(rows[:max_lines])
