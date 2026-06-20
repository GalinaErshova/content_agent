"""
tracing.py — интеграция с LangSmith (трассировка прогонов конвейера).

LangSmith — сервис для наблюдения за LLM-приложениями: показывает дерево вызовов
(граф → узлы → вызовы модели), тайминги, входы/выходы. Удобно для отладки и
эффектно для демонстрации/защиты проекта.

Как включить: задать переменные окружения (см. .env.example):
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=<ключ из smith.langchain.com>
    LANGCHAIN_PROJECT=education-content-agents   # имя проекта в LangSmith (необязательно)
LangGraph и LangChain тогда отправляют трассировку автоматически.

Этот модуль делает две вещи:
1) даёт декоратор @traceable — он добавляет в трассировку наши собственные вызовы
   модели (адаптеры Yandex/mock не являются объектами LangChain, поэтому сами по
   себе в трассировку не попадут). Если пакет langsmith не установлен — декоратор
   превращается в «пустышку» и ничего не делает (код продолжает работать);
2) функция setup_tracing() — печатает в лог, включена ли трассировка.
"""

from __future__ import annotations

import os

from .logger import get_logger

log = get_logger(__name__)

try:
    # Настоящий декоратор из langsmith. Если пакета нет — уходим в except.
    from langsmith import traceable as _traceable
    _HAS_LANGSMITH = True
except Exception:  # noqa: BLE001 — любая проблема импорта = трассировки нет
    _HAS_LANGSMITH = False

    def _traceable(*dargs, **dkwargs):
        """
        Заглушка, повторяющая интерфейс langsmith.traceable. Поддерживает оба
        способа применения: '@traceable' и '@traceable(name=...)'.
        """
        # Случай '@traceable' без скобок: первый аргумент — это сама функция.
        if dargs and callable(dargs[0]) and not dkwargs:
            return dargs[0]
        # Случай '@traceable(name=...)': возвращаем декоратор, который ничего не меняет.
        def decorator(func):
            return func
        return decorator


# Экспортируем под общим именем, чтобы агенты/адаптеры импортировали отсюда.
traceable = _traceable


def tracing_enabled() -> bool:
    """Включена ли трассировка через переменные окружения."""
    return (
        os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
        or os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    )


def setup_tracing() -> None:
    """Сообщить в лог статус трассировки (вызывается при сборке конвейера)."""
    if not tracing_enabled():
        log.info("LangSmith трассировка выключена (LANGCHAIN_TRACING_V2 не задан).")
        return
    if not _HAS_LANGSMITH:
        log.warning("Трассировка включена, но пакет langsmith не установлен: "
                    "pip install langsmith (или uv pip install -e \".[tracing]\").")
        return
    project = (os.environ.get("LANGCHAIN_PROJECT")
               or os.environ.get("LANGSMITH_PROJECT")
               or "education-content-agents")
    log.info("LangSmith трассировка включена. Проект: %s", project)
