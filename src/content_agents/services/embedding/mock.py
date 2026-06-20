"""
services/embedding/mock.py — поддельный эмбеддер (без сети).

Превращает текст в вектор детерминированно, на основе хешей слов. Это НЕ
семантика (синонимы не сблизятся), но для запуска и проверки конвейера хватает:
поиск по совпадающим словам работает. Настоящие эмбеддинги Yandex понимают смысл.
"""

from __future__ import annotations

import hashlib
import re

DIM = 64  # размерность вектора — небольшая, для скорости


class MockEmbeddingProvider:
    """Реализует порт EmbeddingProvider. is_query здесь не важен (один способ)."""

    def embed(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        # 'Мешок слов' → вектор: каждое слово прибавляет 1 в позицию hash(word) % DIM.
        vec = [0.0] * DIM
        for word in re.findall(r"\w+", text.lower()):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM
            vec[h] += 1.0
        # Нормируем, чтобы косинусная близость корректно сравнивала тексты разной длины.
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]
