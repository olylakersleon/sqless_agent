from __future__ import annotations

import uuid
from typing import Iterable, List

from .clarification import ClarificationAnswer, ClarificationEngine
from .conflict import ConflictDetector, apply_conflict_option
from .expert import ExpertFeedbackApplier, ExpertRouter
from .gate import UncertaintyGate
from .intent import IntentParser
from .models import Candidate, SessionState
from .sql_generator import SQLGenerator
from .stores import AssetStore, CandidateSelector


class MetricAgent:
    def __init__(
        self,
        store: AssetStore,
        owners: Iterable[str] | None = None,
    ) -> None:
        self.store = store
        self.parser = IntentParser()
        self.selector = CandidateSelector(store)
        self.gate = UncertaintyGate()
        self.clarifier = ClarificationEngine()
        self.sql_generator = SQLGenerator()
        self.expert_router = ExpertRouter(list(owners or []))
        self.expert_feedback = ExpertFeedbackApplier()
        self.conflict_detector = ConflictDetector()

    def start_session(self, query: str, user: str, force_expert: bool = False) -> SessionState:
        intent = self.parser.parse(query)
        session = SessionState(session_id=str(uuid.uuid4()), user=user, intent=intent)
        session.conflict = self.conflict_detector.detect(intent)
        keywords = intent.metrics or [query]
        session.candidates = self.selector.retrieve(keywords)
        self.gate.evaluate(session)
        if session.conflict:
            session.route_expert = True
        if force_expert:
            session.route_expert = True
        return session

    def clarify(self, state: SessionState, answers: Iterable[ClarificationAnswer]) -> None:
        self.clarifier.apply_answers(state, answers)
        if state.candidates:
            state.selected_spec = state.candidates[0].spec

    def generate_sql(self, state: SessionState) -> str:
        if not state.selected_spec:
            raise ValueError("No spec selected; cannot generate SQL")
        return self.sql_generator.render(state.selected_spec, state)

    def route_to_expert(self, state: SessionState) -> List[str]:
        return self.expert_router.route(state)

    def apply_expert_decision(self, state: SessionState, spec: Candidate | None = None) -> None:
        chosen = (spec or state.candidates[0]).spec if state.candidates else None
        if chosen:
            self.expert_feedback.apply(state, chosen)

    def resolve_conflict(self, state: SessionState, option_id: str) -> None:
        if not state.conflict:
            return
        option = next((opt for opt in state.conflict.options if opt.option_id == option_id), None)
        if not option:
            return
        apply_conflict_option(state.intent, option)
        state.conflict = None

    def session_report(self, state: SessionState) -> str:
        lines = [f"会话 {state.session_id} for {state.user}"]
        lines.append(f"原始需求: {state.intent.raw_query}")
        if state.candidates:
            lines.append("候选:")
            for idx, cand in enumerate(state.candidates, start=1):
                lines.append(f" {idx}. {cand.spec.summary()} (score={cand.score:.2f})")
        lines.append(f"置信度: {state.confidence:.2f} | 需要专家: {state.route_expert}")
        if state.clarifications:
            lines.append("澄清结果: " + self.clarifier.summarize_answers(state))
        if state.selected_spec:
            lines.append(
                f"最终采用: {state.selected_spec.meta.name} {state.selected_spec.governance.version}"
            )
        return "\n".join(lines)
