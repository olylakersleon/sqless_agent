from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .models import Candidate, MetricSpec


@dataclass
class AssetStore:
    """In-memory hot/cold asset storage for MetricSpec objects."""

    cold_specs: Dict[str, MetricSpec] = field(default_factory=dict)
    hot_specs: Dict[str, MetricSpec] = field(default_factory=dict)

    def add_cold(self, spec: MetricSpec) -> None:
        self.cold_specs[spec.spec_id] = spec

    def add_hot(self, spec: MetricSpec) -> None:
        self.hot_specs[spec.spec_id] = spec

    def get_all(self) -> Iterable[MetricSpec]:
        yield from self.cold_specs.values()
        yield from self.hot_specs.values()

    def mark_verified(self, spec_id: str) -> None:
        if spec_id in self.hot_specs:
            self.hot_specs[spec_id].meta.status = "verified"

    def bump_usage(self, spec_id: str) -> None:
        spec = self.hot_specs.get(spec_id) or self.cold_specs.get(spec_id)
        if spec:
            spec.meta.usage_count += 1


class CandidateSelector:
    def __init__(self, store: AssetStore) -> None:
        self.store = store

    def retrieve(self, intent_keywords: List[str], top_k: int = 5) -> List[Candidate]:
        scored: List[Tuple[MetricSpec, float]] = []
        keywords = {k.lower() for k in intent_keywords}
        for spec in self.store.get_all():
            score = self._score_spec(spec, keywords)
            scored.append((spec, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [Candidate(spec=s, score=score) for s, score in scored[:top_k]]

    def _score_spec(self, spec: MetricSpec, keywords: set[str]) -> float:
        name_tokens = {spec.meta.name.lower(), *[a.lower() for a in spec.meta.aliases], *spec.meta.tags}
        overlap = len(keywords.intersection(name_tokens))
        freshness = 1.0 if spec.meta.status == "verified" else 0.85
        usage_bonus = min(spec.meta.usage_count / 100.0, 0.1)
        return overlap * 0.6 + freshness * 0.3 + usage_bonus
