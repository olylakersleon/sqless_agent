from sqless_agent.agent import MetricAgent
from sqless_agent.clarification import ClarificationAnswer
from sqless_agent.provenance import IntentSQLStore, SQLProvenancePipeline
from sqless_agent.sample_data import (
    build_default_specs,
    sample_authority_map,
    sample_query_logs,
    sample_table_schemas,
)
from sqless_agent.stores import AssetStore


def main() -> None:
    store = AssetStore()
    for spec in build_default_specs():
        store.add_cold(spec)

    agent = MetricAgent(store=store, owners=["owner@datateam.com", "lead@datateam.com"])
    session = agent.start_session("12月行业GMV走势", user="alice")

    if session.route_expert:
        experts = agent.route_to_expert(session)
        print("专家路由:", experts)
        agent.apply_expert_decision(session)

    if agent.gate.needs_clarification(session):
        questions = agent.clarifier.next_questions(session)
        print("需澄清的问题:")
        for q in questions:
            print(f"- {q.question} 可选: {', '.join(q.options)} (推荐: {q.recommended})")
        answers = [
            ClarificationAnswer(slot=q.slot, value=q.recommended or q.options[0])
            for q in questions
        ]
        agent.clarify(session, answers)

    sql = agent.generate_sql(session)
    print(agent.session_report(session))
    print("\n生成的 SQL:\n", sql)

    # --- SQL Provenance Mining demo ---------------------------------
    pipeline = SQLProvenancePipeline()
    mined_pairs = pipeline.run(
        logs=sample_query_logs(),
        table_schemas=sample_table_schemas(),
        authority_map=sample_authority_map(),
    )
    kb = IntentSQLStore()
    kb.add_pairs(mined_pairs)

    print("\n=== SQL Provenance Mining: 高质量意图-SQL 对 ===")
    for pair in mined_pairs:
        print(
            f"- {pair.intent} | trust={pair.trust_score} | freq={pair.frequency} | template={pair.sql_template.template}"
        )

    retrieved = kb.retrieve("北京 新客 成交数")
    print("\n检索 Top 意图-SQL：")
    for pair in retrieved:
        print(f"* {pair.intent} | trust={pair.trust_score} | tables={pair.sql_template.tables}")


if __name__ == "__main__":
    main()
