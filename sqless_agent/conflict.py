from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .models import ConflictNotice, ConflictOption, ParsedIntent


@dataclass
class ConflictDetector:
    """Simple heuristic conflict detector for ambiguous/contradictory asks."""

    def detect(self, intent: ParsedIntent) -> Optional[ConflictNotice]:
        lowered = intent.raw_query.lower()
        granular = intent.granularity or ""
        has_settlement = "结算" in intent.raw_query
        wants_daily = any(token in intent.raw_query for token in ["当日", "当天", "日", "天"]) or granular in {"天", "日"}
        if has_settlement and wants_daily:
            return ConflictNotice(
                code="settle_vs_daily",
                message="检测到潜在冲突：结算口径通常有延迟，按天看波动可能不准确。",
                options=[
                    ConflictOption(
                        option_id="settle_weekly",
                        label="保持结算口径，粒度改为周",
                        consequence="将时间粒度调整为周以匹配结算滞后",
                        apply_granularity="周",
                    ),
                    ConflictOption(
                        option_id="switch_pay",
                        label="保持日粒度，改用支付口径",
                        consequence="改为支付/下单口径以获得当日数据",
                        apply_metric_caliber="支付",
                    ),
                ],
            )
        return None


def apply_conflict_option(intent: ParsedIntent, option: ConflictOption) -> None:
    if option.apply_granularity:
        intent.granularity = option.apply_granularity
    if option.apply_metric_caliber:
        # Patch clarifying slot in intent; actual slot stored in clarifications downstream
        if intent.filters is None:
            intent.filters = []
        # keep track via filters comment to show in confirmation
        intent.filters.append(f"口径调整为{option.apply_metric_caliber}")
