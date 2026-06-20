"""
utils.py — мелкие утилиты, не зависящие от предметной области.
"""

from __future__ import annotations

import json
import re


def extract_json(text: str):
    """
    Достать первый JSON-массив или объект из ответа модели.
    LLM нередко добавляют текст вокруг JSON ('Вот ваш план: [...]') или
    оборачивают его в ```json ... ```. Эта функция берёт только сам JSON.
    Возвращает разобранный объект (list/dict) или None, если JSON не найден.
    """
    if not text:
        return None
    # Сначала пробуем найти массив [...], затем объект {...}. re.DOTALL —
    # чтобы '.' захватывал и переносы строк (JSON бывает многострочным).
    for pattern in (r"\[.*\]", r"\{.*\}"):
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue
    return None
