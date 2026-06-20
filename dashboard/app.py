"""
dashboard/app.py — простой дэш на Streamlit (тёмная тема в стиле historygame.ru).

Запуск (из корня проекта):
    pip install streamlit          # или: uv pip install streamlit
    streamlit run dashboard/app.py

Что делает дэш:
1) показывает форму постановки задания (источники, профиль, форматы, ...);
2) по кнопке запускает тот же JobManager, что и CLI;
3) В РЕАЛЬНОМ ВРЕМЕНИ отрисовывает статус каждого агента, читая поток событий
   (PipelineEvent), который отдаёт конвейер. Это и есть 'живой мониторинг' из §15.

Тёмное оформление задаётся двумя вещами:
- файлом .streamlit/config.toml (базовая тема Streamlit);
- блоком CSS ниже (шрифты с засечками, карточки статусов, журнал-консоль).

Задержка между шагами (слайдер) нужна на mock-провайдере: иначе шаги конвейера
проскакивают мгновенно и цепочку не разглядеть.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Делаем пакет content_agents импортируемым при запуске 'streamlit run dashboard/app.py'.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import streamlit as st  # noqa: E402

from content_agents.config import (  # noqa: E402
    AUDIENCES_DIR, build_run_config, discover_sources, resolve_workspace,
)
from content_agents.job_manager import JobManager  # noqa: E402

# Человекочитаемые подписи стадий и их порядок — для отрисовки статусов.
STAGES = [
    ("ingestion", "Ingestion", "сбор источников"),
    ("analysis", "Analysis", "индексация (RAG)"),
    ("planner", "Planner", "план материала"),
    ("generators", "Generators", "генерация контента"),
    ("illustrator", "Illustrator", "иллюстрации"),
    ("critic", "Critic", "проверка фактов"),
    ("finalizer", "Finalizer", "сборка форматов"),
]

# Подписи состояний для каждой стадии (выводятся справа в карточке).
STATE_LABEL = {"idle": "ожидание", "running": "выполняется",
               "done": "готово", "reject": "возврат", "error": "ошибка"}

# --- CSS темы. Внедряется один раз в начало страницы. ---
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=EB+Garamond:ital@0;1&display=swap');

/* Заголовки — благородный шрифт с засечками, цвет золота. */
h1, h2, h3 { font-family: 'Playfair Display', serif !important; color: #d8c074 !important; }
.block-container { padding-top: 2rem; }

/* Шапка дэша в духе сайта. */
.he-header { border-bottom: 1px solid #2a2a33; padding-bottom: .8rem; margin-bottom: 1rem; }
.he-title { font-family:'Playfair Display',serif; font-size: 2.1rem; color:#d8c074;
            letter-spacing:.5px; margin:0; }
.he-sub { font-family:'EB Garamond',serif; color:#9a958a; font-size:1.05rem; margin-top:.2rem; }

/* Карточка одной стадии конвейера. */
.stage { display:flex; align-items:center; gap:.7rem; padding:.55rem .8rem;
         border:1px solid #24242c; border-left:3px solid #3a3a44; border-radius:6px;
         margin-bottom:.5rem; background:#14141b; transition:all .2s; }
.stage .dot { width:10px; height:10px; border-radius:50%; background:#3a3a44; flex:0 0 auto; }
.stage .name { font-weight:600; color:#e7e3d8; }
.stage .desc { color:#8a857a; font-size:.85rem; }
.stage .state { margin-left:auto; font-size:.85rem; color:#6a665d; }

/* Состояния стадии — подсветка слева и точка. */
.stage.running { border-left-color:#c9a227; box-shadow:0 0 12px rgba(201,162,39,.15); }
.stage.running .dot { background:#c9a227; animation:pulse 1s infinite; }
.stage.running .state { color:#c9a227; }
.stage.done { border-left-color:#7faa6e; }
.stage.done .dot { background:#7faa6e; }
.stage.done .state { color:#7faa6e; }
.stage.reject { border-left-color:#b3402f; }
.stage.reject .dot { background:#b3402f; }
.stage.reject .state { color:#d2624f; }
.stage.error { border-left-color:#8b2e22; }
.stage.error .dot { background:#8b2e22; }

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

/* Журнал решений — стиль консоли/донесений. */
.he-log { background:#0a0a0e; border:1px solid #24242c; border-radius:6px;
          padding:.6rem .8rem; font-family:'Courier New',monospace; font-size:.82rem;
          color:#b9b3a4; white-space:pre-wrap; max-height:260px; overflow-y:auto; }
.he-log .rev { color:#c9a227; }
</style>
"""


def available_audiences() -> list[str]:
    """Список id профилей из config/audiences/*.yaml — наполняет выпадающий список."""
    return sorted(p.stem for p in AUDIENCES_DIR.glob("*.yaml"))


def stage_panel_html(status: dict[str, str], revision: int) -> str:
    """Собрать HTML панели статусов агентов по текущему состоянию."""
    rows = []
    for key, name, desc in STAGES:
        cls = status.get(key, "idle")
        rows.append(
            f"<div class='stage {cls}'>"
            f"<span class='dot'></span>"
            f"<span class='name'>{name}</span>"
            f"<span class='desc'>— {desc}</span>"
            f"<span class='state'>{STATE_LABEL.get(cls, '')}</span>"
            f"</div>"
        )
    rows.append(f"<div style='color:#8a857a;font-size:.85rem;margin-top:.4rem'>"
                f"Циклов доработки (ревизий): <b style='color:#c9a227'>{revision}</b></div>")
    return "".join(rows)


def main():
    st.set_page_config(page_title="Education Content Pipeline", layout="wide",
                       page_icon="🏛")
    st.markdown(CSS, unsafe_allow_html=True)

    # Шапка в стиле сайта.
    st.markdown(
        "<div class='he-header'>"
        "<div class='he-title'>🏛 Конвейер образовательного контента</div>"
        "<div class='he-sub'>Постановка задания и живой мониторинг работы агентов</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    form_col, monitor_col = st.columns([1, 1])

    with form_col:
        st.subheader("Новое задание")
        projects_root = st.text_input("Корень проектов", value="projects")
        project = st.text_input("Проект (задача)", value="demo")
        audience = st.selectbox("Профиль аудитории", available_audiences(), index=0)
        outputs = st.multiselect("Форматы вывода", ["markdown", "html", "slides"],
                                  default=["markdown", "html", "slides"])
        content_types = st.multiselect(
            "Типы контента", ["summary", "explanation", "edu_material"],
            default=["summary", "explanation", "edu_material"])
        volume = st.select_slider("Объём", ["short", "standard", "detailed"], value="standard")
        max_rev = st.slider("Лимит ревизий критика", 0, 5, 3)
        # Слайдер задержки — главное для наглядности на mock.
        delay = st.slider("Пауза между шагами, сек (для наглядности на mock)",
                          0.0, 2.0, 0.8, step=0.1)
        strict = st.checkbox("Строгий grounding (выбрасывать неподтверждённое)", value=False)
        backend = st.radio("Бэкенд", ["mock (офлайн)", "yandex"], index=0, horizontal=True)
        run_clicked = st.button("⚔ Запустить конвейер", type="primary")

    with monitor_col:
        st.subheader("Мониторинг")
        stage_panel = st.empty()
        status: dict[str, str] = {k: "idle" for k, _, _ in STAGES}
        stage_panel.markdown(stage_panel_html(status, 0), unsafe_allow_html=True)
        log_box = st.empty()
        log_lines: list[str] = []

    if run_clicked:
        bk = "yandex" if backend.startswith("yandex") else "mock"
        for var in ("LLM_BACKEND", "EMBEDDING_BACKEND", "IMAGE_BACKEND"):
            os.environ[var] = bk

        # Рабочее пространство задачи: <projects_root>/<project>/{data/sources, outputs}.
        ws = resolve_workspace(project, projects_root)
        sources_dir = ws.sources_dir
        out_dir = ws.output_dir
        st.caption(f"Источники: {sources_dir} · Результаты: {out_dir}")

        sources = discover_sources(sources_dir)
        if not sources:
            st.error(f"В папке '{sources_dir}' не найдено источников (.md/.txt). "
                     f"Положите файлы в папку проекта и нажмите снова.")
            st.stop()

        config = build_run_config(
            sources=sources, audience_id=audience, outputs=outputs,
            content_types=content_types, target_volume=volume,
            max_revisions=max_rev, strict_grounding=strict,
        )

        manager = JobManager(out_dir=out_dir, step_delay=delay)
        job = None

        # ГЛАВНЫЙ ЦИКЛ: идём по событиям конвейера и обновляем интерфейс на каждом.
        for job, event in manager.run_job(config):
            status[event.stage] = event.state
            stage_panel.markdown(stage_panel_html(status, event.revision),
                                 unsafe_allow_html=True)
            if event.note:
                rev = f"<span class='rev'>[ревизия {event.revision}]</span> " if event.revision else ""
                log_lines.append(f"{rev}[{event.stage}] {event.note}")
                log_box.markdown("<div class='he-log'>" + "<br>".join(log_lines[-14:]) +
                                 "</div>", unsafe_allow_html=True)

        # --- Итоги ---
        st.success(f"Статус задания: {job.status}")
        g = job.grounding
        c1, c2, c3 = st.columns(3)
        c1.metric("Утверждений", g["total"])
        c2.metric("Подтверждено", g["supported"])
        c3.metric("Требует проверки", g["flagged"])

        st.subheader("Готовые материалы")
        for art in job.artifacts:
            data = Path(art.path).read_bytes()
            st.download_button(f"Скачать {art.fmt}: {Path(art.path).name}",
                               data=data, file_name=Path(art.path).name)


if __name__ == "__main__":
    main()
