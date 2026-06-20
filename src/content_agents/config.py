"""
config.py — сборка конфигурации запуска (RunConfig) и загрузка профилей аудитории.

Здесь же читаются переменные окружения, выбирающие бэкенд (yandex или mock).
Сам выбор конкретного адаптера происходит в factories.py — этот модуль только
готовит данные.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml  # PyYAML — для чтения профилей аудитории из *.yaml

from .models import AudienceProfile, RunConfig, SourceRef, Workspace
from .logger import get_logger

log = get_logger(__name__)

# Корень проекта вычисляем относительно этого файла:
# config.py лежит в src/content_agents/, поэтому поднимаемся на 3 уровня вверх.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIENCES_DIR = PROJECT_ROOT / "config" / "audiences"

# Корень с задачами ('рабочий стол'). Путь настраивается переменной окружения
# PROJECTS_ROOT, по умолчанию — папка ./projects (относительно места запуска).
# Так папку с задачами можно вынести куда угодно, даже за пределы репозитория.
DEFAULT_PROJECTS_ROOT = os.environ.get("PROJECTS_ROOT", "projects")


def resolve_workspace(project: str, projects_root: str | None = None,
                      *, create: bool = True) -> Workspace:
    """
    Построить пути одной задачи внутри корня проектов:
        <projects_root>/<project>/data/sources   — входные источники
        <projects_root>/<project>/outputs         — результаты
    Если create=True (по умолчанию) — недостающие папки создаются. Поэтому
    'завести новую задачу' = просто указать новое имя --project: каркас сам
    создаст подпапки, останется положить туда источники.
    """
    base = Path(projects_root or DEFAULT_PROJECTS_ROOT)
    root = base / project
    sources_dir = root / "data" / "sources"
    output_dir = root / "outputs"
    if create:
        sources_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
    return Workspace(name=project, root=str(root),
                     sources_dir=str(sources_dir), output_dir=str(output_dir))


def load_audience_profile(profile_id: str) -> AudienceProfile:
    """
    Загрузить профиль аудитории по id (имя файла без .yaml).
    Например, profile_id="university" → config/audiences/university.yaml.
    """
    path = AUDIENCES_DIR / f"{profile_id}.yaml"
    if not path.exists():
        # Понятная ошибка лучше, чем загадочный traceback на пустом месте.
        available = [p.stem for p in AUDIENCES_DIR.glob("*.yaml")]
        raise FileNotFoundError(
            f"Профиль аудитории '{profile_id}' не найден. Доступны: {available}"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    # **data распаковывает словарь из YAML в именованные аргументы dataclass.
    # Ключи YAML обязаны совпадать с полями AudienceProfile.
    return AudienceProfile(**data)


def discover_sources(sources_dir: str) -> list[SourceRef]:
    """
    Просканировать папку и собрать список источников.
    Тип источника определяем по расширению файла. URL-источники в этом каркасе
    задаются отдельно (см. main.py), здесь — только файлы.
    """
    ext_to_kind = {".md": "markdown", ".markdown": "markdown",
                   ".txt": "text", ".pdf": "pdf",
                   ".png": "image", ".jpg": "image", ".jpeg": "image"}
    refs: list[SourceRef] = []
    for path in sorted(Path(sources_dir).glob("*")):
        kind = ext_to_kind.get(path.suffix.lower())
        if kind:
            refs.append(SourceRef(locator=str(path), kind=kind))
    log.info("Найдено источников: %d в %s", len(refs), sources_dir)
    return refs


def backend(name: str, default: str = "mock") -> str:
    """
    Прочитать выбранный бэкенд из переменных окружения.
    name="LLM" → читает LLM_BACKEND. Если переменной нет — вернёт default ('mock'),
    поэтому проект запускается 'из коробки' без ключей Yandex.
    """
    return os.environ.get(f"{name}_BACKEND", default).strip().lower()


def build_run_config(
    *,
    sources: list[SourceRef],
    audience_id: str,
    outputs: list[str],
    content_types: list[str],
    target_volume: str = "standard",
    max_revisions: int = 3,
    strict_grounding: bool = False,
) -> RunConfig:
    """Удобная фабрика RunConfig: подставляет профиль аудитории по id."""
    return RunConfig(
        sources=sources,
        audience=load_audience_profile(audience_id),
        outputs=outputs,                # type: ignore[arg-type]
        content_types=content_types,    # type: ignore[arg-type]
        target_volume=target_volume,    # type: ignore[arg-type]
        max_revisions=max_revisions,
        strict_grounding=strict_grounding,
    )
