from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Mapping, Sequence

from .models import IntentSQLPair, QueryLogRecord, SQLTemplate, TableSchema


# --- Utilities ------------------------------------------------------------


PII_PATTERNS = [
    re.compile(r"\b1[3-9]\d{9}\b"),  # China mainland phone numbers
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b\d{15,18}[Xx]?\b"),  # national IDs
]


def mask_pii(sql: str) -> str:
    """Mask common PII patterns before any LLM step."""

    masked = sql
    for pattern in PII_PATTERNS:
        masked = pattern.sub("<MASKED>", masked)
    return masked


def tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_\u4e00-\u9fff]+", text.lower()) if t]


# --- Phase 1: Filtering ---------------------------------------------------


@dataclass
class SQLLogFilter:
    status_success: str = "SUCCESS"
    min_scanned_rows: int = 1_000
    min_duration_ms: int = 300

    def filter(self, logs: Iterable[QueryLogRecord], authority_whitelist: set[str] | None = None) -> List[QueryLogRecord]:
        """Heuristic physical-layer filter to discard low-value noise."""

        filtered: List[QueryLogRecord] = []
        for log in logs:
            if log.status != self.status_success:
                continue
            if log.scanned_rows < self.min_scanned_rows or log.duration_ms < self.min_duration_ms:
                continue
            if authority_whitelist is not None and log.user not in authority_whitelist:
                # skip low-authority users in the filtering phase
                continue
            sanitized_sql = mask_pii(log.sql)
            filtered.append(
                QueryLogRecord(
                    sql=sanitized_sql,
                    status=log.status,
                    scanned_rows=log.scanned_rows,
                    duration_ms=log.duration_ms,
                    user=log.user,
                    executed_at=log.executed_at,
                )
            )
        return filtered


# --- Phase 2: Structural Fingerprinting ----------------------------------


class SQLTemplateBuilder:
    def __init__(self) -> None:
        self.literal_regex = re.compile(r"'[^']*'|\b\d{4}-\d{2}-\d{2}\b|\b\d+\b")

    def build(self, sql: str) -> SQLTemplate:
        base_sql = self._strip_comments(sql)
        parameters: Dict[str, str] = {}
        counter = 1

        def replace_literal(match: re.Match[str]) -> str:
            nonlocal counter
            placeholder = f"param_{counter}"
            parameters[placeholder] = match.group(0)
            counter += 1
            return f"{{{placeholder}}}"

        templated = self.literal_regex.sub(replace_literal, base_sql)
        tables = self._extract_tables(base_sql)
        normalized = self._normalize_sql(templated)
        fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return SQLTemplate(template=normalized, fingerprint=fingerprint, tables=tables, parameters=parameters)

    def _strip_comments(self, sql: str) -> str:
        return re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.MULTILINE | re.DOTALL).strip()

    def _extract_tables(self, sql: str) -> List[str]:
        matches = re.findall(r"\bfrom\s+([\w\.]+)|\bjoin\s+([\w\.]+)", sql, flags=re.IGNORECASE)
        tables = {m[0] or m[1] for m in matches if m[0] or m[1]}
        return sorted(tables)

    def _normalize_sql(self, sql: str) -> str:
        squashed = re.sub(r"\s+", " ", sql.strip())
        return squashed.lower()


# --- Phase 3: Semantic Reverse Engineering --------------------------------


class SemanticIntentInferer:
    def __init__(self, schemas: Mapping[str, TableSchema] | None = None) -> None:
        self.schemas = {k.lower(): v for k, v in (schemas or {}).items()}

    def infer(self, template: SQLTemplate) -> str:
        tables = template.tables or ["unknown table"]
        measures = self._detect_measures(template.template)
        filters = self._detect_filters(template.template)
        table_descriptions = [self._summarize_table(t) for t in tables]
        parts = []
        if measures:
            parts.append("、".join(measures))
        parts.append("数据来源" + "、".join(table_descriptions))
        if filters:
            parts.append("过滤" + "、".join(filters))
        return "；".join(parts)

    def _summarize_table(self, table: str) -> str:
        schema = self.schemas.get(table.lower())
        if not schema:
            return table
        important_cols = list(schema.columns.items())[:3]
        col_desc = "、".join(f"{col}({desc})" for col, desc in important_cols)
        return f"{schema.table}[{col_desc}]"

    def _detect_measures(self, template_sql: str) -> List[str]:
        measures: List[str] = []
        if "count(distinct" in template_sql:
            measures.append("去重用户数")
        elif "count(" in template_sql:
            measures.append("记录数")
        if "sum(" in template_sql:
            measures.append("金额/求和指标")
        if "avg(" in template_sql:
            measures.append("均值指标")
        return measures or ["常规模型查询"]

    def _detect_filters(self, template_sql: str) -> List[str]:
        filters: List[str] = []
        if "where" not in template_sql:
            return filters
        if "is_new" in template_sql:
            filters.append("新客")
        if "region" in template_sql or "province" in template_sql:
            filters.append("地区筛选")
        if "pay_status" in template_sql:
            filters.append("支付订单")
        return filters


# --- Phase 4: Trust Scoring ----------------------------------------------


@dataclass
class TrustScoreWeights:
    frequency: float = 0.3
    authority: float = 0.5
    recency: float = 0.2


class TrustScorer:
    def __init__(self, weights: TrustScoreWeights | None = None) -> None:
        self.weights = weights or TrustScoreWeights()

    def score(self, frequency: int, max_frequency: int, authority: float, recency_days: float) -> float:
        freq_score = min(frequency / max(max_frequency, 1), 1.0)
        authority_score = min(max(authority, 0.0), 1.0)
        recency_score = 1.0 / (1.0 + recency_days / 30.0)
        total = (
            freq_score * self.weights.frequency
            + authority_score * self.weights.authority
            + recency_score * self.weights.recency
        )
        return round(total, 4)

    def recency_days(self, executed_at: datetime) -> float:
        return max((datetime.utcnow() - executed_at).days, 0)


# --- Orchestrator ---------------------------------------------------------


class SQLProvenancePipeline:
    def __init__(self) -> None:
        self.filter = SQLLogFilter()
        self.templater = SQLTemplateBuilder()
        self.scorer = TrustScorer()

    def run(
        self,
        logs: Iterable[QueryLogRecord],
        table_schemas: Mapping[str, TableSchema] | None = None,
        authority_map: Mapping[str, float] | None = None,
    ) -> List[IntentSQLPair]:
        authority_map = authority_map or {}
        authority_whitelist = {u for u, weight in authority_map.items() if weight >= 0.5}
        cleaned_logs = self.filter.filter(logs, authority_whitelist=authority_whitelist)

        templated_records: List[tuple[QueryLogRecord, SQLTemplate]] = []
        for log in cleaned_logs:
            templated_records.append((log, self.templater.build(log.sql)))

        freq_counter = Counter(tpl.fingerprint for _, tpl in templated_records)
        max_freq = max(freq_counter.values()) if freq_counter else 1
        inferer = SemanticIntentInferer(table_schemas)
        best_by_fingerprint: Dict[str, IntentSQLPair] = {}

        for log, tpl in templated_records:
            frequency = freq_counter[tpl.fingerprint]
            authority = authority_map.get(log.user, 0.3 if authority_whitelist else 0.2)
            recency = self.scorer.recency_days(log.executed_at)
            trust = self.scorer.score(frequency, max_freq, authority, recency)
            intent = inferer.infer(tpl)
            entities = {k: v for k, v in tpl.parameters.items() if k.startswith("param_")}
            candidate = IntentSQLPair(
                intent=intent,
                sql_template=tpl,
                raw_sql=log.sql,
                inferred_entities=entities,
                trust_score=trust,
                frequency=frequency,
                authority=authority,
                recency=recency,
            )
            existing = best_by_fingerprint.get(tpl.fingerprint)
            if not existing or candidate.trust_score > existing.trust_score:
                best_by_fingerprint[tpl.fingerprint] = candidate
        return list(best_by_fingerprint.values())


# --- Storage & Retrieval --------------------------------------------------


class IntentSQLStore:
    def __init__(self) -> None:
        self.pairs: List[IntentSQLPair] = []

    def add_pairs(self, pairs: Sequence[IntentSQLPair]) -> None:
        self.pairs.extend(pairs)

    def retrieve(self, query: str, top_k: int = 5) -> List[IntentSQLPair]:
        query_tokens = set(tokenize(query))
        scored: List[tuple[float, IntentSQLPair]] = []
        for pair in self.pairs:
            intent_tokens = set(tokenize(pair.intent))
            overlap = len(query_tokens & intent_tokens)
            intent_score = overlap / (len(query_tokens) + 1)
            total_score = intent_score * 0.6 + pair.trust_score * 0.4
            scored.append((total_score, pair))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [pair for _, pair in scored[:top_k]]
