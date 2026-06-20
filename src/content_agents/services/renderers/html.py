"""
services/renderers/html.py — сборка итогового материала в самостоятельный HTML.

Строим HTML напрямую из структурированных данных (а не конвертируем markdown),
чтобы не тянуть зависимостей. Получается один автономный файл, который можно
открыть в браузере.
"""

from __future__ import annotations

import html
import os

from ...models import Draft, GeneratedImage
from ._common import TYPE_TITLES, group_by_section, image_for_section


class HtmlRenderer:
    fmt = "html"

    def render(self, *, title: str, drafts: list[Draft], images: list[GeneratedImage],
               citations_index: dict[str, str], out_dir: str) -> str:
        # html.escape защищает от того, что спецсимволы из текста (<, >, &)
        # сломают разметку. Это обязательная гигиена при сборке HTML.
        parts: list[str] = [
            "<!DOCTYPE html>",
            "<html lang='ru'><head><meta charset='utf-8'>",
            f"<title>{html.escape(title)}</title>",
            "<style>body{font-family:sans-serif;max-width:760px;margin:2rem auto;"
            "padding:0 1rem;line-height:1.6}img{max-width:100%}h2{margin-top:2rem}"
            "figcaption{color:#666;font-size:.9em}.src{color:#888;font-size:.85em}</style>",
            "</head><body>",
            f"<h1>{html.escape(title)}</h1>",
        ]

        for section_id, section_drafts in group_by_section(drafts):
            parts.append(f"<h2>{html.escape(section_drafts[0].title)}</h2>")

            img = image_for_section(images, section_id)
            if img:
                rel = os.path.relpath(img.file_path, out_dir)
                parts.append(
                    f"<figure><img src='{html.escape(rel)}' alt='{html.escape(img.caption)}'>"
                    f"<figcaption>{html.escape(img.caption)}</figcaption></figure>"
                )

            for d in section_drafts:
                parts.append(f"<h3>{html.escape(TYPE_TITLES.get(d.content_type, d.content_type))}</h3>")
                # Переносы строк из текста превращаем в <br> для читабельности.
                parts.append(f"<p>{html.escape(d.text).replace(chr(10), '<br>')}</p>")
                if d.citations:
                    refs = ", ".join(html.escape(c.locator) for c in d.citations)
                    parts.append(f"<p class='src'>Источники: {refs}</p>")

        parts.append("</body></html>")

        path = os.path.join(out_dir, "summary.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))
        return path
