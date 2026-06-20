"""
main.py — запуск конвейера из командной строки.

Пример:
    python -m content_agents.main \
        --project demo \
        --audience university \
        --outputs markdown html slides \
        --content-types summary explanation edu_material \
        --volume standard

Источники берутся из projects/<project>/data/sources, результат кладётся в
projects/<project>/outputs (папки создаются автоматически). Корень проектов
настраивается флагом --projects-root или переменной окружения PROJECTS_ROOT.

Без ключей Yandex всё работает на mock-провайдерах (см. фабрики). Чтобы
включить Yandex, выставьте переменные окружения LLM_BACKEND=yandex и т.д.
плюс YC_API_KEY / YC_FOLDER_ID.
"""

from __future__ import annotations

import argparse

from .config import build_run_config, discover_sources, resolve_workspace
from .job_manager import JobManager
from .models import SourceRef


def main() -> None:
    parser = argparse.ArgumentParser(description="Генерация образовательного контента из источников")
    parser.add_argument("--projects-root", default=None,
                        help="корень с задачами (по умолчанию ./projects или $PROJECTS_ROOT)")
    parser.add_argument("--project", default="demo",
                        help="имя задачи — подпапка в корне проектов (создаётся автоматически)")
    parser.add_argument("--sources", default=None,
                        help="переопределить папку источников (по умолчанию <project>/data/sources)")
    parser.add_argument("--out", default=None,
                        help="переопределить папку результатов (по умолчанию <project>/outputs)")
    parser.add_argument("--url", action="append", default=[],
                        help="URL-источник (можно указать несколько раз); требует загрузчика URL")
    parser.add_argument("--audience", default="university",
                        help="id профиля аудитории (файл config/audiences/<id>.yaml)")
    parser.add_argument("--outputs", nargs="+", default=["markdown"],
                        choices=["markdown", "html", "slides"])
    parser.add_argument("--content-types", nargs="+", default=["summary", "explanation", "edu_material"],
                        choices=["summary", "explanation", "edu_material"])
    parser.add_argument("--volume", default="standard", choices=["short", "standard", "detailed"])
    parser.add_argument("--max-revisions", type=int, default=3)
    parser.add_argument("--strict-grounding", action="store_true",
                        help="выбрасывать неподтверждённые источниками блоки")
    parser.add_argument("--delay", type=float, default=None,
                        help="пауза между шагами в секундах (для наглядности). "
                             "По умолчанию: 0.6 на mock, 0 на yandex")
    args = parser.parse_args()

    # Определяем рабочее пространство задачи: <projects_root>/<project>/{data,outputs}.
    # Папки создаются автоматически, если их ещё нет.
    ws = resolve_workspace(args.project, args.projects_root)
    sources_dir = args.sources or ws.sources_dir     # можно переопределить флагом
    out_dir = args.out or ws.output_dir

    # Собираем источники: файлы из папки задачи + переданные URL.
    sources = discover_sources(sources_dir)
    sources += [SourceRef(locator=u, kind="url") for u in args.url]

    if not sources:
        print(f"\n⚠ В папке источников пусто: {sources_dir}")
        print("  Положите туда файлы .md/.txt и запустите снова "
              "(или укажите --sources / --url).\n")
        return

    config = build_run_config(
        sources=sources,
        audience_id=args.audience,
        outputs=args.outputs,
        content_types=args.content_types,
        target_volume=args.volume,
        max_revisions=args.max_revisions,
        strict_grounding=args.strict_grounding,
    )

    # Определяем паузу между шагами. Если --delay не задан явно, включаем её
    # автоматически на mock-провайдере (чтобы видеть цепочку), а на Yandex — нет.
    import os
    if args.delay is not None:
        delay = args.delay
    else:
        delay = 0.6 if os.environ.get("LLM_BACKEND", "mock").lower() == "mock" else 0.0

    manager = JobManager(out_dir=out_dir, step_delay=delay)

    print(f"\n▶ Задача '{ws.name}'. Источники: {sources_dir}")
    print(f"  Результаты: {out_dir}")
    print(f"  Профиль: {config.audience.title}. Форматы: {', '.join(config.outputs)}\n")

    job = None
    # Идём по событиям конвейера и печатаем их — это консольный аналог дэша.
    for job, event in manager.run_job(config):
        marker = {"running": "…", "done": "✓", "reject": "↩", "error": "✗"}.get(event.state, " ")
        rev = f" [ревизия {event.revision}]" if event.revision else ""
        line = f"  {marker} {event.stage:<11}{rev}"
        if event.note:
            line += f"  — {event.note}"
        print(line)

    print(f"\n● Статус задания: {job.status}")
    if job.artifacts:
        print("● Готовые файлы:")
        for art in job.artifacts:
            print(f"   - {art.fmt}: {art.path}")
    print()


if __name__ == "__main__":
    main()
