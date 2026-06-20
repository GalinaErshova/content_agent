"""
factories.py — фабрики, выбирающие конкретный адаптер по конфигурации.

Это единственное место, которое 'знает' про все адаптеры сразу. Агенты же
получают готовый провайдер и работают с ним через порт, не подозревая,
mock это или Yandex.

Выбор управляется переменными окружения:
    LLM_BACKEND=mock|yandex
    EMBEDDING_BACKEND=mock|yandex
    IMAGE_BACKEND=mock|yandex
По умолчанию везде 'mock' — поэтому проект запускается без ключей.
"""

from __future__ import annotations

from .config import backend
from .logger import get_logger
from .ports import EmbeddingProvider, ImageProvider, LLMProvider, VectorStore

log = get_logger(__name__)


def make_llm() -> LLMProvider:
    name = backend("LLM")
    if name == "yandex":
        # Импорт внутри функции: requests/ключи нужны только если реально выбран Yandex.
        from .services.llm.yandex_gpt import YandexGPTAdapter
        log.info("LLM backend: Yandex")
        return YandexGPTAdapter()
    from .services.llm.mock import MockLLMProvider
    log.info("LLM backend: mock (офлайн)")
    return MockLLMProvider()


def make_embedding() -> EmbeddingProvider:
    name = backend("EMBEDDING")
    if name == "yandex":
        from .services.embedding.yandex_emb import YandexEmbeddingAdapter
        log.info("Embedding backend: Yandex")
        return YandexEmbeddingAdapter()
    from .services.embedding.mock import MockEmbeddingProvider
    log.info("Embedding backend: mock (офлайн)")
    return MockEmbeddingProvider()


def make_image() -> ImageProvider:
    name = backend("IMAGE")
    if name == "yandex":
        from .services.image.yandex_art import YandexARTAdapter
        log.info("Image backend: YandexART")
        return YandexARTAdapter()
    from .services.image.mock import MockImageProvider
    log.info("Image backend: mock (офлайн)")
    return MockImageProvider()


def make_vectorstore(embedder: EmbeddingProvider) -> VectorStore:
    """
    Выбрать векторное хранилище по RAG_BACKEND: memory (по умолчанию) или faiss.
    Хранилищу передаётся эмбеддер — оно само векторизует тексты при добавлении/поиске.
    """
    name = backend("RAG", "memory")
    if name == "faiss":
        # Импорт внутри: faiss/langchain нужны только в этом режиме.
        from .services.vectorstore.faiss_store import FaissVectorStore
        log.info("RAG backend: FAISS (LangChain)")
        return FaissVectorStore(embedder)
    from .services.vectorstore.memory import InMemoryVectorStore
    log.info("RAG backend: in-memory (офлайн)")
    return InMemoryVectorStore(embedder)
