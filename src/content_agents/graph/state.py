"""
graph/state.py — СОСТОЯНИЕ конвейера.

PipelineState — это 'общая тетрадь', которую агенты передают по цепочке.
Каждый агент читает нужные поля и дописывает свои результаты. К концу
прохода тетрадь содержит всё: от исходных документов до готовых артефактов.

Так в LangGraph и устроено: узлы графа читают и обновляют единый объект
состояния. Наш мини-оркестратор (workflow.py) повторяет эту идею.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models import (
    ContentPlan, Document, Draft, GeneratedImage, OutputArtifact, RunConfig, Topic,
)
from ..ports import VectorStore


@dataclass
class PipelineState:
    config: RunConfig                                   # параметры запуска (что и для кого делаем)

    documents: list[Document] = field(default_factory=list)        # после Ingestion
    vector_store: VectorStore | None = None                        # после Analysis (индекс RAG)
    topics: list[Topic] = field(default_factory=list)              # после Analysis
    content_plan: ContentPlan | None = None                        # после Planner
    drafts: list[Draft] = field(default_factory=list)              # после Generators
    images: list[GeneratedImage] = field(default_factory=list)     # после Illustrator
    artifacts: list[OutputArtifact] = field(default_factory=list)  # после Finalizer

    revision_count: int = 0                             # сколько раз критик возвращал на доработку
    # Метрики grounding (заполняет Critic) — это то, что видно на дэше:
    # сколько утверждений, сколько подтверждено источником, сколько помечено.
    grounding: dict = field(default_factory=lambda: {"total": 0, "supported": 0, "flagged": 0})

    # Индекс цитат для финального раздела 'Источники': chunk_id → человекочитаемое место.
    citations_index: dict[str, str] = field(default_factory=dict)
    # Тексты использованных фрагментов: chunk_id → текст. Нужны критику, чтобы
    # показать модели сам источник и проверить, подтверждается ли им утверждение.
    chunk_texts: dict[str, str] = field(default_factory=dict)

    # Служебные поля для оркестрации LangGraph: через них узлы графа сообщают
    # наружу, какой агент только что отработал (last_stage), его короткую заметку
    # (last_note) и вердикт критика (last_verdict). Оркестратор читает их и
    # формирует события PipelineEvent для дэша/CLI.
    last_stage: str = ""
    last_note: str = ""
    last_verdict: str = ""
