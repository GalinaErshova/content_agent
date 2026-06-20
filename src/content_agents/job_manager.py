"""
job_manager.py — JobManager: тонкая обёртка между интерфейсом и конвейером.

Отвечает за:
1) сборку конвейера (создаёт провайдеров через фабрики и внедряет их в агентов);
2) создание Job и запуск Workflow;
3) ретрансляцию событий наружу (CLI/дэш подписываются на них).

И CLI (main.py), и дэш (dashboard/app.py) работают ЧЕРЕЗ JobManager — это и есть
'единая точка', про которую говорит спецификация (§15). Добавить REST API позже
= сделать ещё одного клиента JobManager, ничего внутри не меняя.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator

from .agents.analysis import AnalysisAgent
from .agents.critic import CriticAgent
from .agents.finalizer import FinalizerAgent
from .agents.generators import GeneratorsAgent
from .agents.illustrator import IllustratorAgent
from .agents.ingestion import IngestionAgent
from .agents.planner import PlannerAgent
from .factories import make_embedding, make_image, make_llm, make_vectorstore
from .graph.state import PipelineState
from .graph.workflow import Workflow
from .logger import get_logger
from .models import Job, PipelineEvent, RunConfig
from .tracing import setup_tracing

log = get_logger(__name__)


class JobManager:
    def __init__(self, out_dir: str = "output", step_delay: float = 0.0):
        # step_delay — искусственная пауза (в секундах) ПОСЛЕ каждого события
        # конвейера. Нужна только для наглядности на mock-провайдерах: без неё
        # шаги проскакивают мгновенно и цепочку не разглядеть. На реальном Yandex
        # ставьте 0 — там и так есть сетевые задержки.
        self.out_dir = out_dir
        self.step_delay = step_delay

    def _build_workflow(self) -> Workflow:
        """
        Собрать конвейер: создать провайдеров (mock или Yandex — решают фабрики)
        и внедрить их в агентов. Обратите внимание: LLM и эмбеддер можно держать
        разными моделями для разных агентов — для простоты здесь общий набор.
        """
        llm = make_llm()
        embedder = make_embedding()
        image = make_image()
        # Векторное хранилище само векторизует тексты — поэтому эмбеддер уходит в него,
        # а не в агентов (RAG_BACKEND выбирает memory или faiss).
        store = make_vectorstore(embedder)

        # Сообщаем в лог статус трассировки LangSmith (включается переменными окружения).
        setup_tracing()

        return Workflow(
            ingestion=IngestionAgent(),
            analysis=AnalysisAgent(llm=llm, store=store),
            planner=PlannerAgent(llm=llm),
            generators=GeneratorsAgent(llm=llm, store=store),
            illustrator=IllustratorAgent(llm=llm, image=image, out_dir=self.out_dir),
            critic=CriticAgent(llm=llm),
            finalizer=FinalizerAgent(out_dir=self.out_dir),
        )

    def run_job(self, config: RunConfig) -> Iterator[tuple[Job, PipelineEvent]]:
        """
        Запустить задание. Это ГЕНЕРАТОР: на каждом шаге отдаёт пару
        (job, event). Job обновляется по ходу (events/status/artifacts),
        поэтому подписчик может и показывать прогресс, и в конце забрать
        готовый Job целиком.
        """
        job = Job(id=str(uuid.uuid4())[:8], config=config, status="running")
        state = PipelineState(config=config)
        workflow = self._build_workflow()

        try:
            for event in workflow.run(state):
                job.events.append(event)
                yield job, event
                # Пауза для наглядности (только если задана). Срабатывает после
                # того, как подписчик (дэш/CLI) показал событие, — поэтому каждый
                # шаг видно по отдельности.
                if self.step_delay:
                    time.sleep(self.step_delay)
            # Конвейер прошёл. Переносим артефакты и метрики в Job, выставляем статус.
            job.artifacts = state.artifacts
            job.grounding = state.grounding
            # Если критик так и не одобрил (остались неподтверждённые) — needs_review.
            job.status = "needs_review" if state.grounding.get("flagged", 0) else "done"
        except Exception as e:                       # noqa: BLE001 — верхнеуровневый перехват
            log.exception("Задание упало")
            job.status = "error"
            job.events.append(PipelineEvent(stage="pipeline", state="error", note=str(e)))
            yield job, job.events[-1]

        return
