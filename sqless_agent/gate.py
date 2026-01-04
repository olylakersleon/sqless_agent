from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import Candidate, SessionState


@dataclass
class UncertaintyGate:
    high_conf_threshold: float = 0.85
    clarifying_threshold: float = 0.65

    def evaluate(self, state: SessionState) -> None:
        if not state.candidates:
            state.route_expert = True
            state.confidence = 0.0
            return
        top = state.candidates[0]
        second_score = state.candidates[1].score if len(state.candidates) > 1 else 0.0
        state.confidence = top.score
        if top.score >= self.high_conf_threshold and (top.score - second_score) >= 0.15:
            state.selected_spec = top.spec
            state.route_expert = False
        elif top.score >= self.clarifying_threshold:
            state.route_expert = False
        else:
            state.route_expert = True

    @staticmethod
    def needs_clarification(state: SessionState) -> bool:
        # Show clarification cards whenever没有确定口径，哪怕已建议走专家模式，前端也能继续用选择题/表单补齐槽位
        return state.selected_spec is None
