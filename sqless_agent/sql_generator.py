from __future__ import annotations

from typing import Dict

from .models import MetricSpec, SessionState


class SQLGenerator:
    def render(self, spec: MetricSpec, state: SessionState) -> str:
        slots: Dict[str, str] = {
            "time_bucket": spec.semantics.grain.time_granularity,
            "fact_table": spec.physical.fact_table,
            "time_column": spec.physical.time_column,
            "measure_column": spec.physical.measure_column,
        }
        where_parts = [f.expr for f in spec.semantics.filters]
        if state.intent.time_range:
            where_parts.append(f"-- 时间范围: {state.intent.time_range}")
        if state.clarifications.get("metric_caliber"):
            where_parts.append(f"-- 口径: {state.clarifications['metric_caliber'].value}")
        if state.clarifications.get("industry_mapping"):
            where_parts.append(f"-- 行业映射: {state.clarifications['industry_mapping'].value}")
        if state.clarifications.get("time_semantics"):
            where_parts.append(f"-- 时间口径: {state.clarifications['time_semantics'].value}")
        where_clause = "\n    AND ".join(where_parts) if where_parts else "1=1"
        template = spec.physical.sql_template or (
            "-- Show Your Work: {fact_table} / {time_column} / {measure_column}\n"
            "SELECT {time_bucket} AS time_bucket, SUM({measure_column}) AS metric\n"
            "FROM {fact_table}\n"
            "WHERE {time_column} IS NOT NULL AND {where_clause}\n"
            "GROUP BY {time_bucket}\n"
            "ORDER BY {time_bucket};"
        )
        return template.format(where_clause=where_clause, **slots)
