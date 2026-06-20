"""
ports.py — ПОРТЫ (интерфейсы) гексагональной архитектуры.

Идея Ports & Adapters простыми словами:
- ПОРТ — это контракт ("что должен уметь поставщик"), описанный как Protocol.
- АДАПТЕР — конкретная реализация порта (Yandex, mock, локальная модель...).

Агенты зависят ТОЛЬКО от портов (от этих интерфейсов), а не от конкретных
адаптеров. Поэтому, чтобы заменить mock на настоящий Yandex, не нужно менять
ни одной строчки в агентах — достаточно подсунуть другой адаптер.

Protocol (из typing) — это "структурный интерфейс": класс считается реализующим
порт, если у него есть нужные методы, даже без явного наследования. Это и есть
"утиная типизация", но проверяемая инструментами вроде mypy.
"""

from __future__ import annotations

from typing import Protocol

from .models import Chunk, Document, SourceRef


class LLMProvider(Protocol):
    """Порт текстовой модели. Любой адаптер (Yandex/mock/локальный) реализует это."""

    def complete(self, system: str, user: str, **opts) -> str:
        """
        Принять системную и пользовательскую инструкции, вернуть ответ модели.
        system — роль/правила ("ты редактор учебных материалов..."),
        user   — собственно запрос с данными.
        """
        ...


class EmbeddingProvider(Protocol):
    """Порт модели эмбеддингов (превращает текст в вектор для семантического поиска)."""

    def embed(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
        """
        Вернуть по вектору на каждый входной текст.
        is_query различает индексацию документов и поисковый запрос — у Yandex
        для этого разные модели (text-search-doc / text-search-query).
        """
        ...


class ImageProvider(Protocol):
    """Порт генерации изображений (YandexART / mock / локальная диффузия)."""

    def generate(self, prompt: str, **opts) -> bytes:
        """Принять текстовый промпт, вернуть байты картинки (PNG)."""
        ...


class VectorStore(Protocol):
    """
    Порт векторного хранилища (RAG). Хранилище само отвечает за эмбеддинги:
    при добавлении оно векторизует тексты чанков, при поиске — текст запроса.
    Благодаря этому агенты работают с понятными текстами, а не с векторами.

    Реализации: InMemoryVectorStore (numpy, офлайн) и FaissVectorStore
    (LangChain + FAISS). Переключаются переменной RAG_BACKEND, агенты не меняются.
    """

    def add(self, chunks: list[Chunk]) -> None:
        """Добавить чанки в индекс (хранилище само посчитает их эмбеддинги)."""
        ...

    def search(self, query: str, k: int = 4) -> list[Chunk]:
        """Вернуть k наиболее близких по смыслу чанков для текстового запроса."""
        ...


class SourceLoader(Protocol):
    """Порт загрузчика источников. Под каждый тип (md, pdf, url) — свой адаптер."""

    def can_load(self, ref: SourceRef) -> bool:
        """Умеет ли этот загрузчик обрабатывать данный источник."""
        ...

    def load(self, ref: SourceRef) -> Document:
        """Прочитать источник и вернуть нормализованный Document."""
        ...


class Renderer(Protocol):
    """Порт рендерера выходного формата (markdown / html / slides)."""

    fmt: str                                        # "markdown" | "html" | "slides"

    def render(self, *, title: str, drafts, images, citations_index, out_dir: str) -> str:
        """Собрать финальный файл и вернуть путь к нему."""
        ...
