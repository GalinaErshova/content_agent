"""
models.py — доменные модели (структуры данных) всей системы.

Здесь нет никакой бизнес-логики и никаких зависимостей от внешних библиотек.
Это просто "словарь типов": какими объектами оперируют агенты, передавая их
друг другу по конвейеру. Такой подход (отделить данные от логики) делает код
понятным и облегчает тестирование.

Все классы — это @dataclass. dataclass автоматически создаёт __init__,
__repr__ и т.п., поэтому нам не нужно писать их руками.
"""

from __future__ import annotations  # позволяет ссылаться на типы "вперёд" в аннотациях

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ---------------------------------------------------------------------------
# 1. ИСТОЧНИКИ И ИЗВЛЕЧЁННЫЙ ТЕКСТ
# ---------------------------------------------------------------------------

@dataclass
class SourceRef:
    """Ссылка на один проверенный источник (то, что даёт пользователь)."""
    locator: str                                   # путь к файлу или URL
    kind: Literal["pdf", "markdown", "text", "url", "image"]


@dataclass
class Document:
    """
    Источник, приведённый к единому виду агентом Ingestion.
    Любой формат (PDF, веб-страница, txt) после загрузки становится Document —
    дальше агенты работают только с этой структурой, не зная исходный формат.
    """
    id: str
    title: str
    text: str
    source: SourceRef
    meta: dict = field(default_factory=dict)       # автор, дата, число страниц и т.п.


@dataclass
class Chunk:
    """
    Фрагмент документа. Длинные тексты режут на чанки, потому что:
    1) модель эмбеддингов работает с короткими кусками;
    2) цитата должна указывать на конкретное место (страницу/абзац), а не на весь файл.
    """
    id: str
    document_id: str
    text: str
    locator: str                                   # человекочитаемое место: "стр. 3", "Введение" и т.п.
    embedding: list[float] | None = None           # вектор; заполняется агентом Analysis


# ---------------------------------------------------------------------------
# 2. АНАЛИЗ И ПЛАН
# ---------------------------------------------------------------------------

@dataclass
class Topic:
    """Ключевая тема/понятие, выделенное из источников (для построения плана)."""
    name: str
    description: str
    related_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ContentSectionPlan:
    """План одного раздела будущего материала: о чём он и что для него генерировать."""
    section_id: str
    title: str
    content_types: list[Literal["summary", "explanation", "edu_material"]]
    wants_illustration: bool = False


@dataclass
class ContentPlan:
    """Полный план материала — список разделов."""
    sections: list[ContentSectionPlan] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. СГЕНЕРИРОВАННЫЙ КОНТЕНТ
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """Ссылка на источник для конкретного утверждения (основа 'data-driven')."""
    chunk_id: str
    locator: str                                   # как показать читателю: "sample.md, Введение"


@dataclass
class Draft:
    """
    Черновик одного куска контента (например, саммари раздела 2).
    Поле citations — ключевое: каждое содержательное утверждение должно
    опираться на источник. Если citations пуст — критик это пометит.
    """
    section_id: str
    content_type: Literal["summary", "explanation", "edu_material"]
    title: str
    text: str
    citations: list[Citation] = field(default_factory=list)


@dataclass
class GeneratedImage:
    """Иллюстрация, сгенерированная агентом Illustrator."""
    section_id: str
    file_path: str                                 # куда сохранили PNG
    caption: str                                   # подпись/alt-текст
    prompt: str                                    # промпт, по которому сгенерировали (для прозрачности)


@dataclass
class Critique:
    """Вердикт критика и список замечаний (фидбэк для повторной генерации)."""
    verdict: Literal["approve", "reject"]
    issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 4. КОНФИГУРАЦИЯ ЗАПУСКА (то, что задаётся при старте — CLI или дэш)
# ---------------------------------------------------------------------------

@dataclass
class AudienceProfile:
    """
    Профиль аудитории. Загружается из YAML (config/audiences/*.yaml).
    Влияет на промпты: глубину объяснений, стиль, нужно ли пояснять термины.
    """
    id: str
    title: str
    reading_level: str
    tone: str
    prior_knowledge: str
    glossary_policy: str


@dataclass
class RunConfig:
    """
    Все параметры одного запуска. Собирается из аргументов командной строки
    (main.py) или из формы дэша — в обоих случаях это один и тот же объект.
    """
    sources: list[SourceRef]
    audience: AudienceProfile
    outputs: list[Literal["markdown", "html", "slides"]]
    content_types: list[Literal["summary", "explanation", "edu_material"]]
    target_volume: Literal["short", "standard", "detailed"] = "standard"
    language: str = "ru"
    max_revisions: int = 3                          # сколько раз критик может вернуть на доработку
    strict_grounding: bool = False                  # True = выбрасывать неподтверждённое, False = помечать


@dataclass
class OutputArtifact:
    """Готовый файл-результат (например, итоговый markdown)."""
    fmt: Literal["markdown", "html", "slides"]
    path: str


@dataclass
class Workspace:
    """
    Рабочее пространство одной задачи: где брать источники и куда класть результат.
    Каждая задача — отдельная подпапка в корне проектов (см. config.resolve_workspace).
    """
    name: str
    root: str           # <projects_root>/<name>
    sources_dir: str    # <root>/data/sources
    output_dir: str     # <root>/outputs


# ---------------------------------------------------------------------------
# 5. ЗАДАНИЕ И СОБЫТИЯ (для управления конвейером и дэша — раздел 15 спецификации)
# ---------------------------------------------------------------------------

@dataclass
class PipelineEvent:
    """
    Одно событие прохождения конвейера. Конвейер 'выплёвывает' такие события
    после каждого шага, а дэш/CLI их показывают. Это и есть живой мониторинг.
    """
    stage: str                                      # ingestion | analysis | ... | finalizer
    state: Literal["running", "done", "reject", "error"]
    note: str = ""                                  # короткая 'запись решения' агента
    revision: int = 0                               # номер ревизии (для петли самокоррекции)
    ts: datetime = field(default_factory=datetime.now)


@dataclass
class Job:
    """
    Одно задание. JobManager создаёт Job, запускает конвейер и наполняет
    events/artifacts. status меняется по ходу выполнения.
    """
    id: str
    config: RunConfig
    status: Literal["queued", "running", "needs_review", "done", "error"] = "queued"
    created_at: datetime = field(default_factory=datetime.now)
    events: list[PipelineEvent] = field(default_factory=list)
    artifacts: list[OutputArtifact] = field(default_factory=list)
    # Метрики проверки фактов (заполняются после критика) — для дэша и отчёта.
    grounding: dict = field(default_factory=lambda: {"total": 0, "supported": 0, "flagged": 0})
