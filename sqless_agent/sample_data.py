from __future__ import annotations

from datetime import datetime

from .models import (
    Attribution,
    ChangelogEntry,
    DimensionJoin,
    Filter,
    Governance,
    Grain,
    IndustryMapping,
    MetricMeta,
    MetricSpec,
    PhysicalMapping,
    Quality,
    QualityRule,
    QueryLogRecord,
    Security,
    Semantics,
    TableSchema,
    TimeSemantics,
)


def build_default_specs() -> list[MetricSpec]:
    gmv_semantics = Semantics(
        metric_type="amount",
        default_measure="pay_gmv_amt",
        metric_caliber="支付",
        grain=Grain(time_granularity="day", dimensions=["industry_id"]),
        time_semantics=TimeSemantics(
            event_time="pay_time", timezone="Asia/Shanghai", business_day_rule="natural_day"
        ),
        filters=[
            Filter(expr="is_risk_order = 0", desc="剔除风控单"),
            Filter(expr="is_refund = 0", desc="剔除退款单"),
        ],
        industry_mapping=IndustryMapping(
            type="category_tree", version="v3", dim_table="dim_category_industry_v3", join_key="category_id"
        ),
        attribution=Attribution(mode="none", desc="不做渠道归因"),
    )
    gmv_spec = MetricSpec(
        spec_id="spec_pay_gmv_v2",
        meta=MetricMeta(
            name="行业GMV",
            aliases=["GMV", "成交额", "行业成交额"],
            domain="commerce.trade",
            description="支付口径 GMV，默认剔除退款与风控单",
            status="verified",
            owner="owner@datateam.com",
            verified_by="lead@datateam.com",
            tags=["gmv", "industry", "trend"],
        ),
        semantics=gmv_semantics,
        physical=PhysicalMapping(
            fact_table="dws_trade_order_day",
            time_column="pay_date",
            measure_column="pay_gmv_amt",
            dimension_joins=[
                DimensionJoin(
                    dim_table="dim_category_industry_v3",
                    fact_key="category_id",
                    dim_key="category_id",
                    select_cols=["industry_id", "industry_name"],
                )
            ],
            partition_hint="pay_date",
            sql_template=None,
        ),
        governance=Governance(
            version="v2",
            valid_from=datetime(2025, 10, 1),
            valid_to=datetime(2099, 12, 31),
            changelog=[
                ChangelogEntry(
                    version="v2",
                    change="剔除退款与风控单",
                    by="lead@datateam.com",
                    at=datetime(2026, 1, 2),
                )
            ],
        ),
        security=Security(row_level_policy="org_scope", allowed_roles=["analyst", "biz_ops"]),
        quality=Quality(validation_rules=[QualityRule(type="sanity", rule="gmv>=0")]),
    )

    order_semantics = Semantics(
        metric_type="count",
        default_measure="order_cnt",
        metric_caliber="下单",
        grain=Grain(time_granularity="day", dimensions=["industry_id"]),
        time_semantics=TimeSemantics(
            event_time="order_time", timezone="Asia/Shanghai", business_day_rule="natural_day"
        ),
        filters=[Filter(expr="is_risk_order = 0", desc="剔除风控单")],
        industry_mapping=IndustryMapping(
            type="category_tree", version="v2", dim_table="dim_category_industry_v2", join_key="category_id"
        ),
    )
    order_spec = MetricSpec(
        spec_id="spec_order_cnt_v1",
        meta=MetricMeta(
            name="订单量",
            aliases=["订单数"],
            domain="commerce.trade",
            description="按行业统计订单量，默认剔除风控单",
            status="draft",
            owner="owner@datateam.com",
            verified_by=None,
            tags=["order", "industry"],
        ),
        semantics=order_semantics,
        physical=PhysicalMapping(
            fact_table="dws_trade_order_day",
            time_column="order_date",
            measure_column="order_cnt",
            dimension_joins=[
                DimensionJoin(
                    dim_table="dim_category_industry_v2",
                    fact_key="category_id",
                    dim_key="category_id",
                    select_cols=["industry_id", "industry_name"],
                )
            ],
            partition_hint="order_date",
            sql_template=None,
        ),
        governance=Governance(
            version="v1",
            valid_from=datetime(2024, 1, 1),
            valid_to=datetime(2099, 12, 31),
            changelog=[
                ChangelogEntry(
                    version="v1",
                    change="初始版本",
                    by="owner@datateam.com",
                    at=datetime(2024, 1, 1),
                )
            ],
        ),
        security=Security(row_level_policy="org_scope", allowed_roles=["analyst", "biz_ops"]),
        quality=Quality(validation_rules=[QualityRule(type="reconcile", target="official_dashboard", freq="weekly")]),
    )

    settle_semantics = Semantics(
        metric_type="amount",
        default_measure="settle_gmv_amt",
        metric_caliber="结算",
        grain=Grain(time_granularity="week", dimensions=["industry_id"]),
        time_semantics=TimeSemantics(
            event_time="settle_time", timezone="Asia/Shanghai", business_day_rule="settlement_day"
        ),
        filters=[Filter(expr="is_risk_order = 0", desc="剔除风控单")],
        industry_mapping=IndustryMapping(
            type="category_tree", version="v3", dim_table="dim_category_industry_v3", join_key="category_id"
        ),
    )

    settle_spec = MetricSpec(
        spec_id="spec_settle_gmv_v1",
        meta=MetricMeta(
            name="行业GMV（结算口径）",
            aliases=["结算GMV", "行业结算额"],
            domain="commerce.finance",
            description="按结算口径统计的行业 GMV，周粒度，默认剔除风控单",
            status="draft",
            owner="finance@datateam.com",
            verified_by=None,
            tags=["gmv", "settle", "industry"],
        ),
        semantics=settle_semantics,
        physical=PhysicalMapping(
            fact_table="dws_trade_settle_week",  # fictitious
            time_column="settle_week",
            measure_column="settle_gmv_amt",
            dimension_joins=[
                DimensionJoin(
                    dim_table="dim_category_industry_v3",
                    fact_key="category_id",
                    dim_key="category_id",
                    select_cols=["industry_id", "industry_name"],
                )
            ],
            partition_hint="settle_week",
        ),
        governance=Governance(
            version="v1",
            valid_from=datetime(2025, 1, 1),
            valid_to=datetime(2099, 12, 31),
            changelog=[
                ChangelogEntry(
                    version="v1",
                    change="结算口径初版",
                    by="finance@datateam.com",
                    at=datetime(2025, 1, 2),
                )
            ],
        ),
        security=Security(row_level_policy="org_scope", allowed_roles=["finance", "analyst"]),
        quality=Quality(
            validation_rules=[QualityRule(type="reconcile", target="finance_dashboard", freq="monthly")]
        ),
    )

    pay_raw_semantics = Semantics(
        metric_type="amount",
        default_measure="pay_gmv_amt",
        metric_caliber="支付",
        grain=Grain(time_granularity="day", dimensions=["industry_id"]),
        time_semantics=TimeSemantics(
            event_time="pay_time", timezone="Asia/Shanghai", business_day_rule="natural_day"
        ),
        filters=[Filter(expr="is_risk_order = 0", desc="剔除风控单")],
        industry_mapping=IndustryMapping(
            type="category_tree", version="v2", dim_table="dim_category_industry_v2", join_key="category_id"
        ),
        attribution=Attribution(mode="content_channel", desc="按内容渠道归因"),
    )

    pay_raw_spec = MetricSpec(
        spec_id="spec_pay_gmv_v1",
        meta=MetricMeta(
            name="行业GMV（支付含退款）",
            aliases=["支付GMV（含退款）"],
            domain="commerce.trade",
            description="支付口径 GMV，包含退款以便对账",
            status="verified",
            owner="owner@datateam.com",
            verified_by="lead@datateam.com",
            tags=["gmv", "industry", "attribution"],
        ),
        semantics=pay_raw_semantics,
        physical=PhysicalMapping(
            fact_table="dws_trade_order_day",
            time_column="pay_date",
            measure_column="pay_gmv_amt",
            dimension_joins=[
                DimensionJoin(
                    dim_table="dim_category_industry_v2",
                    fact_key="category_id",
                    dim_key="category_id",
                    select_cols=["industry_id", "industry_name"],
                )
            ],
            partition_hint="pay_date",
        ),
        governance=Governance(
            version="v1",
            valid_from=datetime(2024, 6, 1),
            valid_to=datetime(2099, 12, 31),
            changelog=[
                ChangelogEntry(
                    version="v1",
                    change="支付含退款版本",  # allows clash with v2 filtered one
                    by="owner@datateam.com",
                    at=datetime(2024, 6, 2),
                )
            ],
        ),
        security=Security(row_level_policy="org_scope", allowed_roles=["analyst", "biz_ops"]),
        quality=Quality(validation_rules=[QualityRule(type="sanity", rule="gmv>=0")]),
    )

    return [gmv_spec, pay_raw_spec, settle_spec, order_spec]


def sample_query_logs() -> list[QueryLogRecord]:
    """Synthetic historical logs used for provenance mining demo."""

    now = datetime.utcnow()
    return [
        QueryLogRecord(
            sql="""
            SELECT date, region, sum(pay_gmv_amt) AS gmv
            FROM dws_trade_order_day
            WHERE region = '华东' AND date BETWEEN '2025-06-01' AND '2025-06-30' AND pay_status = 1
            GROUP BY date, region
        """,
            status="SUCCESS",
            scanned_rows=120_000,
            duration_ms=2100,
            user="analyst@datateam.com",
            executed_at=now,
        ),
        QueryLogRecord(
            sql="""
            SELECT date, count(distinct user_id) AS new_pay_users
            FROM dws_trade_order_day
            WHERE province = 'beijing' AND is_new = 1 AND pay_status = 1
            GROUP BY date
        """,
            status="SUCCESS",
            scanned_rows=240_000,
            duration_ms=3300,
            user="lead@datateam.com",
            executed_at=now,
        ),
        QueryLogRecord(
            sql="""
            SELECT settle_week, industry_id, sum(settle_gmv_amt)
            FROM dws_trade_settle_week
            WHERE settle_week BETWEEN '2025-05-01' AND '2025-06-30'
            GROUP BY settle_week, industry_id
        """,
            status="SUCCESS",
            scanned_rows=310_000,
            duration_ms=4500,
            user="finance@datateam.com",
            executed_at=now,
        ),
        QueryLogRecord(
            sql="""
            SELECT * FROM tmp_debug LIMIT 10
        """,
            status="SUCCESS",
            scanned_rows=10,
            duration_ms=50,
            user="random@corp.com",
            executed_at=now,
        ),
    ]


def sample_table_schemas() -> dict[str, TableSchema]:
    return {
        "dws_trade_order_day": TableSchema(
            table="dws_trade_order_day",
            columns={
                "pay_gmv_amt": "支付GMV金额",
                "user_id": "用户ID",
                "province": "省份",
                "region": "大区",
                "pay_status": "支付状态",
                "is_new": "是否新客",
            },
        ),
        "dws_trade_settle_week": TableSchema(
            table="dws_trade_settle_week",
            columns={
                "settle_gmv_amt": "结算金额",
                "industry_id": "行业ID",
                "settle_week": "结算周",
            },
        ),
    }


def sample_authority_map() -> dict[str, float]:
    return {
        "lead@datateam.com": 0.9,
        "analyst@datateam.com": 0.7,
        "finance@datateam.com": 0.6,
    }
