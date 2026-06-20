"""
services/vectorstore/memory.py — векторное хранилище В ПАМЯТИ (офлайн, без LangChain).

Это запасной/учебный вариант RAG: хранилище само векторизует тексты через
EmbeddingProvider и ищет ближайшие по косинусной близости на numpy. Никаких
внешних RAG-зависимостей — поэтому каркас запускается офлайн (RAG_BACKEND=memory,
значение по умолчанию). Для масштаба переключитесь на FaissVectorStore.
"""

from __future__ import annotations

import numpy as np

from ...models import Chunk
from ...ports import EmbeddingProvider


class InMemoryVectorStore:
    """Реализует порт VectorStore. Эмбеддинги считает сам, поиск — косинус на numpy."""

    def __init__(self, embedder: EmbeddingProvider):
        self.embedder = embedder
        self._chunks: list[Chunk] = []
        self._matrix: np.ndarray | None = None     # матрица [N, DIM] эмбеддингов чанков

    def add(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        # Векторизуем тексты чанков (режим документов, не запроса).
        vectors = self.embedder.embed([c.text for c in chunks], is_query=False)
        for c, v in zip(chunks, vectors):
            c.embedding = v
        self._chunks.extend(chunks)
        # Складываем все эмбеддинги в одну матрицу — поиск делается одним
        # матричным умножением, а не циклом по чанкам.
        self._matrix = np.array([c.embedding for c in self._chunks], dtype=np.float32)

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        if not self._chunks:
            return []
        # Векторизуем запрос (режим запроса) и считаем близость со всеми чанками.
        q = np.array(self.embedder.embed([query], is_query=True)[0], dtype=np.float32)
        # Эмбеддинги нормированы → косинус = скалярное произведение.
        scores = self._matrix @ q
        top_idx = np.argsort(scores)[::-1][:k]
        return [self._chunks[i] for i in top_idx]
