"""
services/llm/yandex_gpt.py — настоящий адаптер YandexGPT.

Реализован на чистом requests (нативный REST), потому что requests уже есть в
окружении и не тянет лишних зависимостей. В репозитории-образце
(pueraeternis/yandex-gpt-api) показан и второй путь — через библиотеку openai
(Yandex совместим с OpenAI API). Если установите `openai`, сможете переписать
этот адаптер на OpenAI SDK, не меняя ничего в агентах.

Документы Yandex Cloud: модель задаётся URI вида
    gpt://<folder_id>/yandexgpt-lite/latest
Аутентификация — заголовок 'Authorization: Api-Key <ключ>' и 'x-folder-id'.

ВАЖНО: этот адаптер требует сети и ключей. Без них используйте MockLLMProvider.
"""

from __future__ import annotations

import os

import requests

from ...logger import get_logger
from ...tracing import traceable

log = get_logger(__name__)

# Эндпоинт синхронной генерации текста YandexGPT.
ENDPOINT = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


class YandexGPTAdapter:
    """Реализует порт LLMProvider поверх REST API Yandex Cloud."""

    def __init__(
        self,
        api_key: str | None = None,
        folder_id: str | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        timeout: int = 60,
    ):
        # Читаем ключи из окружения, если не переданы явно (12-factor стиль).
        self.api_key = api_key or os.environ["YC_API_KEY"]
        self.folder_id = folder_id or os.environ["YC_FOLDER_ID"]
        # modelUri: какую модель и из какого каталога вызывать.
        # yandexgpt-lite — быстрее/дешевле (генерация); yandexgpt — умнее (Planner/Critic).
        self.model = model or f"gpt://{self.folder_id}/yandexgpt-lite/latest"
        self.temperature = temperature
        self.timeout = timeout

    @traceable(name="YandexGPT.complete", run_type="llm")
    def complete(self, system: str, user: str, **opts) -> str:
        """Отправить два сообщения (system + user) и вернуть текст ответа."""
        payload = {
            "modelUri": opts.get("model", self.model),
            "completionOptions": {
                "stream": False,
                "temperature": opts.get("temperature", self.temperature),
                "maxTokens": str(opts.get("max_tokens", 2000)),
            },
            "messages": [
                {"role": "system", "text": system},
                {"role": "user", "text": user},
            ],
        }
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }
        resp = requests.post(ENDPOINT, json=payload, headers=headers, timeout=self.timeout)
        resp.raise_for_status()  # бросит исключение на 4xx/5xx — лучше явная ошибка
        data = resp.json()
        # Структура ответа Yandex: result.alternatives[0].message.text
        return data["result"]["alternatives"][0]["message"]["text"]
