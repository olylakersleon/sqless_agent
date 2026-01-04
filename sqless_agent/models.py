from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MetricMeta:
    name: str
    aliases: List[str]
    domain: str
    description: str
    status: str
    owner: str
    verified_by: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    usage_count: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class Grain:
    time_granularity: str
    dimensions: List[str]


@dataclass
class TimeSemantics:
    event_time: str
    timezone: str
    business_day_rule: str


@dataclass
class Filter:
    expr: str
    desc: Optional[str] = None


@dataclass
class IndustryMapping:
    type: str
    version: str
    dim_table: str
    join_key: str


@dataclass
class Attribution:
    mode: str
    desc: Optional[str] = None


@dataclass
class Semantics:
    metric_type: str
    default_measure: str
    grain: Grain
    time_semantics: TimeSemantics
    filters: List[Filter] = field(default_factory=list)
    industry_mapping: Optional[IndustryMapping] = None
    attribution: Optional[Attribution] = None
    metric_caliber: Optional[str] = None


@dataclass
class DimensionJoin:
    dim_table: str
    fact_key: str
    dim_key: str
    select_cols: List[str]


@dataclass
class PhysicalMapping:
    fact_table: str
    time_column: str
    measure_column: str
    dimension_joins: List[DimensionJoin]
    partition_hint: Optional[str] = None
    sql_template: Optional[str] = None


@dataclass
class ChangelogEntry:
    version: str
    change: str
    by: str
    at: datetime


@dataclass
class Governance:
    version: str
    valid_from: datetime
    valid_to: datetime
    changelog: List[ChangelogEntry]
    conflict_policy: str = "prefer_latest_verified"


@dataclass
class Security:
    row_level_policy: Optional[str] = None
    column_masking: List[str] = field(default_factory=list)
    allowed_roles: List[str] = field(default_factory=list)


@dataclass
class QualityRule:
    type: str
    target: Optional[str] = None
    freq: Optional[str] = None
    rule: Optional[str] = None


@dataclass
class Quality:
    validation_rules: List[QualityRule] = field(default_factory=list)


@dataclass
class MetricSpec:
    spec_id: str
    meta: MetricMeta
    semantics: Semantics
    physical: PhysicalMapping
    governance: Governance
    security: Security = field(default_factory=Security)
    quality: Quality = field(default_factory=Quality)

    def summary(self) -> str:
        filters_desc = ", ".join(f.expr for f in self.semantics.filters) or "无"
        dimensions = ", ".join(self.semantics.grain.dimensions) or "无"
        return (
            f"{self.meta.name}（{self.semantics.metric_type}） | "
            f"默认粒度: {self.semantics.grain.time_granularity} | 维度: {dimensions} | "
            f"过滤: {filters_desc} | 数据源: {self.physical.fact_table}"
        )


@dataclass
class Candidate:
    spec: MetricSpec
    score: float


@dataclass
class ParsedIntent:
    raw_query: str
    metrics: List[str]
    dimensions: List[str]
    time_range: Optional[str]
    granularity: Optional[str]
    filters: List[str] = field(default_factory=list)


@dataclass
class ClarificationQuestion:
    slot: str
    question: str
    options: List[str]
    recommended: Optional[str] = None


@dataclass
class ClarificationAnswer:
    slot: str
    value: str


@dataclass
class ConflictOption:
    option_id: str
    label: str
    consequence: str
    apply_granularity: Optional[str] = None
    apply_metric_caliber: Optional[str] = None


@dataclass
class ConflictNotice:
    code: str
    message: str
    options: List[ConflictOption]


@dataclass
class SessionState:
    session_id: str
    user: str
    intent: ParsedIntent
    candidates: List[Candidate] = field(default_factory=list)
    clarifications: Dict[str, ClarificationAnswer] = field(default_factory=dict)
    selected_spec: Optional[MetricSpec] = None
    confidence: float = 0.0
    route_expert: bool = False
    conflict: Optional[ConflictNotice] = None
    forwarded_to: Optional[str] = None


@dataclass
class QueryLogRecord:
    """Raw query log entry prior to cleaning and templating."""

    sql: str
    status: str
    scanned_rows: int
    duration_ms: int
    user: str
    executed_at: datetime


@dataclass
class TableSchema:
    """Minimal schema info for semantic reverse engineering."""

    table: str
    columns: Dict[str, str]


@dataclass
class SQLTemplate:
    template: str
    fingerprint: str
    tables: List[str]
    parameters: Dict[str, str] = field(default_factory=dict)


@dataclass
class IntentSQLPair:
    """Cleaned intent-SQL pairing mined from historical logs."""

    intent: str
    sql_template: SQLTemplate
    raw_sql: str
    inferred_entities: Dict[str, str]
    trust_score: float
    frequency: int
    authority: float
    recency: float
