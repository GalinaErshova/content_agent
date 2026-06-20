"""
agents/analysis.py — агент АНАЛИЗА И ИНДЕКСАЦИИ (ядро 'data-driven').

Делает три вещи:
1) режет документы на чанки (через text splitter LangChain, с офлайн-fallback);
2) кладёт чанки в векторное хранилище (RAG-индекс); хранилище САМО считает
   эмбеддинги — поэтому здесь эмбеддер не нужен;
3) выделяет ключевые темы — на их основе Planner построит структуру материала.

Промты вынесены в config/prompts/ru/.
"""

from __future__ import annotations

import re
import uuid

from ..graph.state import PipelineState
from ..logger import get_logger
from ..models import Chunk, Topic
from ..ports import LLMProvider, VectorStore
from ..prompts import render

log = get_logger(__name__)


class AnalysisAgent:
    name = "analysis"

    def __init__(self, llm: LLMProvider, store: VectorStore):
        self.llm = llm
        self.store = store

    def run(self, state: PipelineState) -> str:
        # --- 1. Чанкинг ---
        chunks: list[Chunk] = []
        for doc in state.documents:
            for i, piece in enumerate(_split_text(doc.text), start=1):
                chunks.append(Chunk(
                    id=str(uuid.uuid4())[:8],
                    document_id=doc.id,
                    text=piece,
                    locator=f"{doc.title} — фрагмент {i}",   # 'место' для будущей цитаты
                ))

        # --- 2. Индексация (хранилище само векторизует тексты) ---
        if chunks:
            self.store.add(chunks)
        state.vector_store = self.store

        # --- 3. Темы ---
        # Подаём модели начало корпуса (с заголовками) и просим выделить темы.
        corpus_head = "\n".join(doc.text for doc in state.documents)[:1500]
        raw = self.llm.complete(
            system=render("analysis.system"),
            user=render("analysis.user", context=corpus_head),
        )
        topic_names = [ln.strip("-• ").strip() for ln in raw.splitlines() if ln.strip()]
        state.topics = [Topic(name=n, description="") for n in topic_names[:6]] or \
                       [Topic(name="Основные понятия", description="")]

        return f"чанков: {len(chunks)}, тем: {len(state.topics)}"


def _split_text(text: str, chunk_size: int = 600, overlap: int = 80) -> list[str]:
    """
    Разбить текст на чанки. Если установлен langchain_text_splitters (группа [rag]) —
    используем RecursiveCharacterTextSplitter (умное разбиение по абзацам/предложениям
    с перекрытием). Иначе — простой офлайн-fallback по абзацам.
    Сначала убираем markdown-заголовки (#), чтобы разметка не попадала в контент.
    """
    clean = re.sub(r"(?m)^#{1,6}\s*", "", text)
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        parts = [p.strip() for p in splitter.split_text(clean) if p.strip()]
        return parts or [clean[:chunk_size]]
    except Exception:
        return _manual_split(clean, chunk_size)


def _manual_split(text: str, max_chars: int) -> list[str]:
    """Запасной чанкинг без зависимостей: склеиваем абзацы до ~max_chars."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    buf, out = "", []
    for p in paragraphs:
        if len(buf) + len(p) > max_chars and buf:
            out.append(buf.strip())
            buf = ""
        buf += p + "\n\n"
    if buf.strip():
        out.append(buf.strip())
    return out or [text[:max_chars]]
