"""
graph/workflow.py — ОРКЕСТРАТОР конвейера на LangGraph.

Здесь конвейер собран как настоящий граф состояния LangGraph (StateGraph):
- УЗЛЫ графа — наши агенты (ingestion, analysis, ... , finalizer);
- СОСТОЯНИЕ — PipelineState (общий объект, который узлы читают и дополняют);
- ЛИНЕЙНЫЕ РЁБРА задают порядок: ingestion → analysis → ... → critic;
- УСЛОВНОЕ РЕБРО после критика реализует петлю самокоррекции:
    approve / исчерпан лимит → finalizer → END
    reject (и есть лимит)    → reviser (увеличивает счётчик) → generators → ...

Снаружи остаётся прежний интерфейс: метод run(state) — ГЕНЕРАТОР, который отдаёт
события PipelineEvent (running → done/reject) по мере прохождения графа. Поэтому
дэш и CLI менять не нужно — они как и раньше потребляют поток событий.

Как узлы сообщают о себе: каждый узел кладёт в состояние last_stage (имя агента),
last_note (короткая заметка) и — для критика — last_verdict. Мы стримим состояние
через app.stream(..., stream_mode="values") и на каждом шаге превращаем эти поля
в события.

Трассировка LangSmith включается автоматически переменными окружения (см.
tracing.py): при включённой трассировке весь прогон графа и вложенные вызовы
модели видны в интерфейсе LangSmith.
"""

from __future__ import annotations

from collections.abc import Iterator

from langgraph.graph import END, START, StateGraph

from ..models import PipelineEvent
from ..tracing import tracing_enabled
from .state import PipelineState

# Узлы, которые соответствуют видимым стадиям конвейера (для событий дэша).
# Служебный узел 'reviser' сюда не входит — наружу он не показывается.
AGENT_STAGES = {"ingestion", "analysis", "planner", "generators",
                "illustrator", "critic", "finalizer"}


def _get(chunk, field: str, default=None):
    """
    Прочитать поле из элемента стрима. LangGraph в режиме 'values' отдаёт полное
    состояние; в зависимости от версии это может быть объект-датакласс или dict —
    поддерживаем оба варианта.
    """
    if isinstance(chunk, dict):
        return chunk.get(field, default)
    return getattr(chunk, field, default)


class Workflow:
    """Собирает граф LangGraph из агентов и прогоняет состояние, отдавая события."""

    def __init__(self, *, ingestion, analysis, planner, generators, illustrator, critic, finalizer):
        self.agents = {
            "ingestion": ingestion, "analysis": analysis, "planner": planner,
            "generators": generators, "illustrator": illustrator,
            "critic": critic, "finalizer": finalizer,
        }
        self.app = self._build()

    # --- Узлы графа ---

    def _make_agent_node(self, name: str):
        """
        Обернуть обычного агента в узел графа. Узел вызывает агента (тот мутирует
        состояние и возвращает заметку), записывает служебные поля и возвращает
        состояние обратно в граф.
        """
        agent = self.agents[name]

        def node(state: PipelineState) -> PipelineState:
            note = agent.run(state)
            state.last_stage = name
            state.last_note = note
            return state

        return node

    def _make_critic_node(self):
        """Узел критика отличается: агент возвращает (вердикт, заметку)."""
        critic = self.agents["critic"]

        def node(state: PipelineState) -> PipelineState:
            verdict, note = critic.run(state)
            state.last_stage = "critic"
            state.last_note = note
            state.last_verdict = verdict
            return state

        return node

    @staticmethod
    def _reviser_node(state: PipelineState) -> PipelineState:
        """Служебный узел: увеличивает счётчик ревизий перед повторной генерацией."""
        state.revision_count += 1
        state.last_stage = "reviser"      # помечаем, чтобы не показывать как стадию
        return state

    @staticmethod
    def _route_after_critic(state: PipelineState) -> str:
        """
        Условное ребро после критика: куда идти дальше.
        Возвращает имя следующего узла — это и есть петля самокоррекции.
        """
        if state.last_verdict == "approve":
            return "finalizer"
        if state.revision_count >= state.config.max_revisions:
            return "finalizer"           # лимит ревизий исчерпан — не зацикливаемся
        return "reviser"                  # иначе — на доработку

    def _build(self):
        """Собрать и скомпилировать граф LangGraph."""
        g = StateGraph(PipelineState)

        # Регистрируем узлы.
        for name in ("ingestion", "analysis", "planner", "generators", "illustrator"):
            g.add_node(name, self._make_agent_node(name))
        g.add_node("critic", self._make_critic_node())
        g.add_node("reviser", self._reviser_node)
        g.add_node("finalizer", self._make_agent_node("finalizer"))

        # Линейные рёбра.
        g.add_edge(START, "ingestion")
        g.add_edge("ingestion", "analysis")
        g.add_edge("analysis", "planner")
        g.add_edge("planner", "generators")
        g.add_edge("generators", "illustrator")
        g.add_edge("illustrator", "critic")

        # Условное ребро после критика (петля самокоррекции).
        g.add_conditional_edges("critic", self._route_after_critic,
                                {"reviser": "reviser", "finalizer": "finalizer"})
        g.add_edge("reviser", "generators")     # доработка → снова генерация → ... → критик
        g.add_edge("finalizer", END)

        return g.compile()

    # --- Запуск с выдачей событий ---

    def run(self, state: PipelineState) -> Iterator[PipelineEvent]:
        # recursion_limit с запасом: на каждую ревизию уходит несколько шагов графа.
        config: dict = {"recursion_limit": 50}
        if tracing_enabled():
            # Имя и теги прогона — так его удобно искать в LangSmith.
            config["run_name"] = "education-content-pipeline"
            config["tags"] = ["education-content-agents"]

        # stream_mode='values' отдаёт полное состояние после каждого узла.
        # По last_stage понимаем, какой агент только что отработал.
        for chunk in self.app.stream(state, config=config, stream_mode="values"):
            stage = _get(chunk, "last_stage", "")
            if stage not in AGENT_STAGES:
                continue  # пропускаем стартовое состояние и служебный reviser

            note = _get(chunk, "last_note", "")
            revision = _get(chunk, "revision_count", 0)
            verdict = _get(chunk, "last_verdict", "")

            # Синтезируем пару событий running → done/reject для этой стадии.
            # (Поток LangGraph отдаёт результат ПОСЛЕ узла, но для наглядной
            # анимации на дэше мы показываем обе фазы; пауза между ними — в JobManager.)
            yield PipelineEvent(stage=stage, state="running", revision=revision)
            if stage == "critic" and verdict == "reject":
                yield PipelineEvent(stage="critic", state="reject", note=note, revision=revision)
            else:
                yield PipelineEvent(stage=stage, state="done", note=note, revision=revision)
