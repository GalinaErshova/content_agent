"""
services/renderers/_common.py — общие функции для всех рендереров.

Рендереры (markdown/html/slides) собирают итог из одних и тех же данных
(черновики + картинки + цитаты), поэтому повторяющуюся логику группировки
вынесли сюда.
"""

from __future__ import annotations

from ...models import Draft, GeneratedImage

# Человекочитаемые названия типов контента — для заголовков в материале.
TYPE_TITLES = {
    "summary": "Краткое саммари",
    "explanation": "Подробное объяснение",
    "edu_material": "Учебные материалы",
}


def group_by_section(drafts: list[Draft]) -> list[tuple[str, list[Draft]]]:
    """
    Сгруппировать черновики по разделам, сохраняя порядок появления разделов.
    Возвращает список пар (section_id, [черновики этого раздела]).
    """
    order: list[str] = []
    buckets: dict[str, list[Draft]] = {}
    for d in drafts:
        if d.section_id not in buckets:
            buckets[d.section_id] = []
            order.append(d.section_id)
        buckets[d.section_id].append(d)
    return [(sid, buckets[sid]) for sid in order]


def image_for_section(images: list[GeneratedImage], section_id: str) -> GeneratedImage | None:
    """Найти иллюстрацию для раздела (если Illustrator её сделал)."""
    for img in images:
        if img.section_id == section_id:
            return img
    return None
