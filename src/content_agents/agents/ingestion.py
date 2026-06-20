"""
agents/ingestion.py — агент СБОРА И НОРМАЛИЗАЦИИ источников.

Первый шаг конвейера. Берёт список источников (SourceRef) и превращает каждый
в единый Document, перебирая загрузчики из реестра ALL_LOADERS.

Принцип, общий для всех агентов в этом проекте:
- агент получает свои зависимости в __init__ (внедрение зависимостей);
- метод run(state) читает нужные поля состояния, пишет результат обратно
  и возвращает короткую СТРОКУ-ЗАМЕТКУ для журнала/дэша.
"""

from __future__ import annotations

from ..graph.state import PipelineState
from ..logger import get_logger
from ..services.loaders.file_loader import ALL_LOADERS

log = get_logger(__name__)


class IngestionAgent:
    name = "ingestion"

    def __init__(self, loaders=ALL_LOADERS):
        self.loaders = loaders

    def run(self, state: PipelineState) -> str:
        documents = []
        skipped = 0
        for ref in state.config.sources:
            # Находим первый загрузчик, который умеет этот тип источника.
            loader = next((ld for ld in self.loaders if ld.can_load(ref)), None)
            if loader is None:
                log.warning("Нет загрузчика для %s (%s)", ref.locator, ref.kind)
                skipped += 1
                continue
            try:
                documents.append(loader.load(ref))
            except NotImplementedError as e:
                # PDF/URL пока заглушки — не валим весь прогон, просто пропускаем.
                log.warning("Источник пропущен: %s", e)
                skipped += 1
        state.documents = documents

        note = f"загружено документов: {len(documents)}"
        if skipped:
            note += f", пропущено: {skipped}"
        return note
