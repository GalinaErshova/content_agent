"""
services/llm/mock.py — поддельная (mock) текстовая модель.

Зачем нужна: чтобы весь конвейер можно было запустить и изучить БЕЗ интернета,
ключей и платных вызовов. Mock не 'думает' — он возвращает осмысленные заглушки
на основе входного текста. Этого достаточно, чтобы увидеть, как данные текут
по агентам и как работает цикл самокоррекции.

Когда подключите настоящий Yandex (services/llm/yandex_gpt.py), интерфейс
останется тем же — агенты не заметят разницы.
"""

from __future__ import annotations

import json
import re

from ...tracing import traceable


class MockLLMProvider:
    """Реализует порт LLMProvider (метод complete). Без сети."""

    @traceable(name="MockLLM.complete", run_type="llm")
    def complete(self, system: str, user: str, **opts) -> str:
        """
        Очень простая эвристика вместо настоящей модели:
        - critic: возвращает JSON-вердикт 'подтверждено';
        - planner: возвращает JSON-план по перечисленным темам;
        - темы / саммари / объяснение / вопросы — простые заглушки.
        Реальная модель, разумеется, делает это осмысленно.

        ВАЖНО: ветки critic и planner проверяются ПЕРВЫМИ, потому что их промты
        содержат данные (тексты черновиков, темы), в которых могут случайно
        встретиться слова-триггеры других веток.
        """
        u = user.lower()

        # --- Critic (батч): нумерованные фрагменты → JSON-массив вердиктов ---
        # mock считает подтверждённым всё, что дошло до батча (т.е. имеет источники).
        if "json" in u and "supported" in u:
            ids = [int(x) for x in re.findall(r"фрагмент\s+(\d+)", user, re.IGNORECASE)]
            if not ids:
                ids = [1]
            verdicts = [{"id": i, "supported": True, "issue": ""} for i in ids]
            return json.dumps(verdicts, ensure_ascii=False)

        # --- Planner: список тем → JSON-массив разделов ---
        if "json" in u and "план" in u:
            topics = []
            m = re.search(r"темы:\s*(.+)", user, re.IGNORECASE)
            if m:
                topics = [t.strip() for t in m.group(1).split(",") if t.strip()]
            topics = topics or ["Основные понятия"]
            plan = [
                {"title": t,
                 "content_types": ["summary", "explanation", "edu_material"],
                 "wants_illustration": i < 2}
                for i, t in enumerate(topics)
            ]
            return json.dumps(plan, ensure_ascii=False)

        if ("выдели" in u and "темы" in u) or "topics" in u:
            # Берём ТОЛЬКО полезную часть (после 'КОНТЕКСТ:'), не саму инструкцию.
            payload = _extract_payload(user)
            # Предпочитаем заголовки markdown (# ...) — это естественные 'темы'.
            headings = [ln.lstrip("# ").strip() for ln in payload.splitlines()
                        if ln.lstrip().startswith("#")]
            if headings:
                picked = headings[:5]
            else:
                # Иначе — короткие строки (заголовки/первые фразы).
                picked = [ln.strip() for ln in payload.splitlines()
                          if 0 < len(ln.strip()) <= 40][:4]
            picked = picked or ["Основные понятия", "Применение"]
            return "\n".join(f"- {p}" for p in picked)

        if "саммари" in u or "summary" in u or "кратко" in u:
            sentences = re.split(r"(?<=[.!?])\s+", _extract_payload(user))
            return " ".join(sentences[:2]).strip() or "Краткое изложение материала."

        if "объясн" in u or "explain" in u:
            payload = _extract_payload(user)
            return (
                f"Разберём подробнее. {payload[:300]} "
                "Иными словами, ключевая идея в том, что приведённые факты связаны между собой "
                "и помогают понять тему на практике."
            ).strip()

        if "вопрос" in u or "карточк" in u or "quiz" in u or "edu" in u:
            return (
                "1. Что является ключевым понятием темы?\n"
                "2. Приведите пример применения.\n"
                "3. Почему это важно для практики?"
            )

        # На любой другой запрос — мягкая переформулировка.
        return _extract_payload(user)[:400] or "…"


def _extract_payload(user: str) -> str:
    """
    Достаём 'полезную часть' промпта — то, что идёт после маркера КОНТЕКСТ:.
    Агенты складывают данные источника в этот блок (см. agents/generators.py).
    """
    marker = "КОНТЕКСТ:"
    if marker in user:
        return user.split(marker, 1)[1].strip()
    return user.strip()
