"""
services/loaders/file_loader.py — загрузчики источников.

Каждый загрузчик реализует порт SourceLoader: умеет сказать, может ли он
обработать источник (can_load), и прочитать его в Document (load).

В MVP полностью работает загрузка markdown/txt. PDF и URL оставлены явными
заглушками с понятными TODO — это точки расширения из спецификации (§9.1).
Добавление нового формата = новый класс-загрузчик, агенты не трогаем.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from ...models import Document, SourceRef


class TextFileLoader:
    """Загружает .md / .markdown / .txt — то, что читается как обычный текст."""

    def can_load(self, ref: SourceRef) -> bool:
        return ref.kind in ("markdown", "text")

    def load(self, ref: SourceRef) -> Document:
        path = Path(ref.locator)
        text = path.read_text(encoding="utf-8")
        # Заголовок: первая markdown-строка '# ...' или имя файла.
        title = path.stem
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        return Document(
            id=str(uuid.uuid4())[:8],
            title=title,
            text=text,
            source=ref,
            meta={"chars": len(text)},
        )


class PdfFileLoader:
    """
    ЗАГЛУШКА для PDF. В реальной реализации здесь будет извлечение текста
    через pymupdf/pypdf с сохранением номеров страниц (для точных цитат).
    """

    def can_load(self, ref: SourceRef) -> bool:
        return ref.kind == "pdf"

    def load(self, ref: SourceRef) -> Document:
        # TODO: import fitz (pymupdf); пройти по страницам; собрать текст и
        #       класть номер страницы в locator чанков (см. agents/analysis.py).
        raise NotImplementedError(
            "Загрузка PDF ещё не реализована. Установите pymupdf и допишите этот метод. "
            "Для запуска каркаса используйте .md/.txt источники."
        )


class UrlLoader:
    """
    ЗАГЛУШКА для веб-страниц. В реальной реализации — requests + trafilatura
    (или readability) для извлечения основного текста без меню и рекламы.
    """

    def can_load(self, ref: SourceRef) -> bool:
        return ref.kind == "url"

    def load(self, ref: SourceRef) -> Document:
        # TODO: requests.get(ref.locator) → trafilatura.extract(html) → text.
        raise NotImplementedError(
            "Загрузка URL ещё не реализована. Установите trafilatura и допишите этот метод."
        )


# Реестр всех доступных загрузчиков. Ingestion перебирает их и берёт первый
# подходящий (can_load == True). Чтобы добавить формат — просто допишите класс
# и добавьте его сюда.
ALL_LOADERS = [TextFileLoader(), PdfFileLoader(), UrlLoader()]
