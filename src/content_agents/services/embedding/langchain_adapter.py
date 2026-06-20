"""
services/embedding/langchain_adapter.py — мост между нашим EmbeddingProvider и
интерфейсом LangChain Embeddings.

LangChain-компоненты (FAISS и др.) ожидают объект с методами embed_documents /
embed_query. Эта обёртка просто перенаправляет их в наш порт EmbeddingProvider,
поэтому FAISS использует ТЕ ЖЕ эмбеддинги (Yandex или mock), что и остальной код.

Импортируется только в FAISS-режиме (RAG_BACKEND=faiss), поэтому langchain-core
требуется лишь когда установлена группа зависимостей [rag].
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings

from ...ports import EmbeddingProvider


class LangchainEmbeddings(Embeddings):
    """Адаптирует наш EmbeddingProvider к интерфейсу LangChain Embeddings."""

    def __init__(self, provider: EmbeddingProvider):
        self.provider = provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Документы индексируем моделью документов (is_query=False).
        return self.provider.embed(list(texts), is_query=False)

    def embed_query(self, text: str) -> list[float]:
        # Запрос — моделью запросов (is_query=True). У Yandex это разные модели.
        return self.provider.embed([text], is_query=True)[0]
