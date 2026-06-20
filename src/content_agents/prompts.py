"""
prompts.py — загрузка промтов из файлов config/prompts/<lang>/<name>.txt.

Профессиональный подход: тексты промтов вынесены из кода в отдельные файлы.
Это даёт сразу несколько выгод:
- промты может править не-программист (методист, редактор), не открывая .py;
- изменения промтов видны в git как изменения ТЕКСТА (удобно ревьюить);
- легко поддерживать несколько языков (папки ru/, en/, ...) и версии промтов.

Шаблоны используют плейсхолдеры вида {{имя}} — они заменяются значениями из
render(). Двойные фигурные скобки выбраны намеренно: одиночные { } внутри промта
(например, в примере JSON-ответа) остаются нетронутыми.

Имена промтов строятся по схеме '<агент>.<роль_или_задача>', например:
    generators.system, generators.summary, planner.user, critic.user
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

# config/prompts/ относительно корня проекта (prompts.py лежит в src/content_agents/).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "config" / "prompts"

# Плейсхолдер вида {{ имя }} (пробелы вокруг имени допускаются).
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@lru_cache(maxsize=None)
def _read(name: str, lang: str) -> str:
    """Прочитать файл промта (с кэшем). Кэш сбрасывается перезапуском процесса."""
    path = PROMPTS_DIR / lang / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Промт не найден: {path}")
    return path.read_text(encoding="utf-8").strip()


def render(name: str, *, lang: str = "ru", **variables) -> str:
    """
    Загрузить промт по имени и подставить переменные.
    Пример: render("generators.summary", section_title="Фотосинтез", context="...").
    Неизвестный плейсхолдер оставляем как есть — это помогает заметить опечатку,
    а не молча подставить пустоту.
    """
    text = _read(name, lang)
    return _PLACEHOLDER.sub(
        lambda m: str(variables.get(m.group(1), m.group(0))), text
    )
