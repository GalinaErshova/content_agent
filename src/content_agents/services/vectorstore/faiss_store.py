"""
services/vectorstore/faiss_store.py — векторное хранилище на LangChain + FAISS.

FAISS — быстрая библиотека поиска ближайших векторов от Meta. Здесь используется
обёртка LangChain (langchain_community.vectorstores.FAISS): она сама хранит тексты,
их эмбеддинги и метаданные и умеет similarity_search по тексту запроса.

Реализует наш порт VectorStore, поэтому агенты (Analysis/Generators) работают с
ним так же, как с in-memory хранилищем. Включается переменной RAG_BACKEND=faiss
и требует установки группы зависимостей [rag] (langchain, langchain-community,
faiss-cpu).

Эмбеддинги берутся из нашего EmbeddingProvider через LangchainEmbeddings —
то есть Yandex/mock, а не сторонняя модель.
"""

from __future__ import annotations

from ...models import Chunk
from ...ports import EmbeddingProvider


class FaissVectorStore:
    """Реализует порт VectorStore поверх FAISS из LangChain."""

    def __init__(self, embedder: EmbeddingProvider):
        # Импортируем тяжёлые зависимости здесь, а не на уровне модуля — чтобы
        # офлайн-режим (in-memory) не требовал установленного faiss/langchain.
        try:
            from langchain_community.vectorstores import FAISS
        except ImportError as e:
            raise RuntimeError(
                "RAG_BACKEND=faiss требует зависимостей FAISS. Установите их: "
                'pip install -e ".[rag]"  (или uv pip install -e ".[rag]")'
            ) from e

        from ..embedding.langchain_adapter import LangchainEmbeddings

        self._FAISS = FAISS
        self._embeddings = LangchainEmbeddings(embedder)
        self._db = None  # индекс создаётся при первом add()

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        texts = [c.text for c in chunks]
        # Метаданные несут всё, что нужно восстановить Chunk при поиске:
        # id (для цитаты), document_id и человекочитаемое место (locator).
        metadatas = [
            {"id": c.id, "document_id": c.document_id, "locator": c.locator}
            for c in chunks
        ]
        if self._db is None:
            self._db = self._FAISS.from_texts(texts, self._embeddings, metadatas=metadatas)
        else:
            self._db.add_texts(texts, metadatas=metadatas)

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        if self._db is None:
            return []
        docs = self._db.similarity_search(query, k=k)
        # Восстанавливаем наши Chunk из документов LangChain (текст + метаданные).
        return [
            Chunk(
                id=d.metadata.get("id", ""),
                document_id=d.metadata.get("document_id", ""),
                text=d.page_content,
                locator=d.metadata.get("locator", ""),
            )
            for d in docs
        ]
