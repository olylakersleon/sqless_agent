from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .models import MetricSpec, SessionState


@dataclass
class ExpertRouter:
    owners: List[str]

    def route(self, state: SessionState) -> List[str]:
        """Return recommended experts for the session."""
        return self.owners[:3]


class ExpertFeedbackApplier:
    def apply(self, state: SessionState, spec: MetricSpec) -> None:
        state.selected_spec = spec
        state.route_expert = False
