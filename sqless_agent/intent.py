from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from .models import ParsedIntent


@dataclass
class IntentParser:
    metric_keywords: List[str] = None

    def parse(self, query: str) -> ParsedIntent:
        keywords = self.metric_keywords or ["gmv", "订单", "转化"]
        metrics = [kw for kw in keywords if kw.lower() in query.lower()]
        dimensions = [match for match in ["行业", "类目", "渠道"] if match in query]
        time_range = self._extract_time_range(query)
        granularity = "天" if "日" in query or "天" in query else None
        return ParsedIntent(
            raw_query=query,
            metrics=metrics,
            dimensions=dimensions,
            time_range=time_range,
            granularity=granularity,
        )

    def _extract_time_range(self, query: str) -> str | None:
        match = re.search(r"(\d{1,2})月", query)
        if match:
            return f"最近的 {match.group(1)} 月"
        return None
