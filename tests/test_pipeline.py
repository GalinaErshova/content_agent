"""
tests/test_pipeline.py — простой интеграционный тест.

Запуск:
    PYTHONPATH=src python -m pytest tests/         # если установлен pytest
    PYTHONPATH=src python tests/test_pipeline.py    # или просто как скрипт

Тест прогоняет ВЕСЬ конвейер на mock-провайдерах (без сети) и проверяет, что:
- задание завершилось успешно;
- появились все три выходных формата;
- сработал цикл самокоррекции (была хотя бы одна ревизия);
- метрики grounding посчитаны.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Делаем пакет импортируемым и принудительно включаем mock-бэкенды.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ.update(LLM_BACKEND="mock", EMBEDDING_BACKEND="mock", IMAGE_BACKEND="mock")

from content_agents.config import build_run_config  # noqa: E402
from content_agents.job_manager import JobManager  # noqa: E402
from content_agents.models import SourceRef  # noqa: E402


def run_pipeline(tmp_out: str):
    """Прогнать конвейер на встроенном примере источника и вернуть итоговый Job."""
    source = (Path(__file__).resolve().parents[1]
              / "projects" / "demo" / "data" / "sources" / "photosynthesis.md")
    config = build_run_config(
        sources=[SourceRef(locator=str(source), kind="markdown")],
        audience_id="university",
        outputs=["markdown", "html", "slides"],
        content_types=["summary", "explanation", "edu_material"],
    )
    manager = JobManager(out_dir=tmp_out)
    job = None
    revisions_seen = 0
    for job, event in manager.run_job(config):
        revisions_seen = max(revisions_seen, event.revision)
    return job, revisions_seen


def test_pipeline_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        job, revisions = run_pipeline(tmp)

        # 1) Задание завершилось (done или needs_review — но не error).
        assert job.status in ("done", "needs_review"), f"неожиданный статус: {job.status}"

        # 2) Созданы все три формата, и файлы реально существуют.
        formats = {a.fmt for a in job.artifacts}
        assert formats == {"markdown", "html", "slides"}, formats
        for art in job.artifacts:
            assert Path(art.path).exists(), f"нет файла {art.path}"

        # 3) Цикл самокоррекции сработал (демо-поведение генератора).
        assert revisions >= 1, "ожидалась хотя бы одна ревизия (цикл критика)"

        # 4) Метрики grounding посчитаны и в финале всё подтверждено.
        assert job.grounding["total"] > 0
        assert job.grounding["supported"] == job.grounding["total"]

        print("OK: статус =", job.status, "| ревизий =", revisions, "| grounding =", job.grounding)


if __name__ == "__main__":
    test_pipeline_end_to_end()
