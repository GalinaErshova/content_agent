"""
services/embedding/yandex_emb.py — настоящие эмбеддинги Yandex Cloud.

У Yandex две модели эмбеддингов:
- text-search-doc   — для индексации документов (наших чанков);
- text-search-query — для поисковых запросов.
Поэтому в порте есть флаг is_query: индексируем документы одной моделью,
ищем — другой. Это рекомендация Yandex для качественного поиска.

Требует сети и ключей. Без них — MockEmbeddingProvider.
"""

from __future__ import annotations

import os

import requests

ENDPOINT = "https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding"


class YandexEmbeddingAdapter:
    """Реализует порт EmbeddingProvider поверх REST API Yandex."""

    def __init__(self, api_key: str | None = None, folder_id: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.environ["YC_API_KEY"]
        self.folder_id = folder_id or os.environ["YC_FOLDER_ID"]
        self.timeout = timeout

    def embed(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        model_name = "text-search-query" if is_query else "text-search-doc"
        model_uri = f"emb://{self.folder_id}/{model_name}/latest"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json",
        }
        vectors: list[list[float]] = []
        # API принимает по одному тексту за вызов, поэтому идём в цикле.
        # (При больших объёмах здесь стоит добавить асинхронность/батчинг — см. образец.)
        for text in texts:
            resp = requests.post(
                ENDPOINT,
                json={"modelUri": model_uri, "text": text},
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            vectors.append(resp.json()["embedding"])
        return vectors
