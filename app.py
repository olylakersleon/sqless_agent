from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional

from sqless_agent.agent import MetricAgent
from sqless_agent.clarification import ClarificationEngine
from sqless_agent.gate import UncertaintyGate
from sqless_agent.models import ClarificationAnswer, ParsedIntent, SessionState
from sqless_agent.sample_data import build_default_specs
from sqless_agent.stores import AssetStore

# Initialize store and agent with sample data
store = AssetStore()
for spec in build_default_specs():
    store.add_cold(spec)

agent = MetricAgent(store, owners=["owner@datateam.com", "lead@datateam.com"])
clarifier = ClarificationEngine()
uncertainty_gate = UncertaintyGate()

sessions: Dict[str, SessionState] = {}
ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"


def serialize(obj):
    if is_dataclass(obj):
        data = asdict(obj)
    elif isinstance(obj, list):
        return [serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    else:
        return obj

    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        else:
            data[key] = serialize(value)
    return data


def summarize_spec(spec, state=None):
    working_state = state or SessionState(
        session_id="preview",
        user="preview",
        intent=ParsedIntent(raw_query="", metrics=[], dimensions=[], time_range=None, granularity=None),
    )
    sql_preview = agent.sql_generator.render(spec, working_state)
    sql_lines = sql_preview.splitlines()
    friendly_slots = clarifier._slot_values_for_spec(spec)
    return {
        "spec_id": spec.spec_id,
        "name": spec.meta.name,
        "summary": spec.summary(),
        "status": spec.meta.status,
        "owner": spec.meta.owner,
        "version": spec.governance.version,
        "domain": spec.meta.domain,
        "tags": spec.meta.tags,
        "time_granularity": spec.semantics.grain.time_granularity,
        "dimensions": spec.semantics.grain.dimensions,
        "filters": [f.desc or f.expr for f in spec.semantics.filters],
        "data_source": spec.physical.fact_table,
        "time_column": spec.physical.time_column,
        "measure": spec.physical.measure_column,
        "metric_caliber": spec.semantics.metric_caliber,
        "time_semantics": friendly_slots.get("time_semantics", spec.semantics.time_semantics.business_day_rule),
        "industry_mapping": friendly_slots.get("industry_mapping")
        + (f" (v{spec.semantics.industry_mapping.version})" if spec.semantics.industry_mapping else "")
        if friendly_slots.get("industry_mapping")
        else None,
        "sql_snippet": "\n".join(sql_lines[:4]),
    }


def confirmation_payload(state: SessionState):
    if not state.selected_spec:
        return None
    spec = state.selected_spec
    friendly_slots = clarifier._slot_values_for_spec(spec)
    mapping_label = friendly_slots.get("industry_mapping") or "未指定"
    if spec.semantics.industry_mapping:
        mapping_label = f"{mapping_label} (v{spec.semantics.industry_mapping.version})"
    time_label = friendly_slots.get("time_semantics") or spec.semantics.time_semantics.business_day_rule
    return {
        "metric": spec.meta.name,
        "version": spec.governance.version,
        "grain": f"{spec.semantics.grain.time_granularity} × {', '.join(spec.semantics.grain.dimensions) or '无'}",
        "time_range": state.intent.time_range or "未指定",
        "time_semantics": time_label,
        "industry_mapping": mapping_label,
        "filters": [f.desc or f.expr for f in spec.semantics.filters],
        "source": spec.physical.fact_table,
        "owner": spec.meta.owner,
        "caliber": spec.semantics.metric_caliber,
        "clarifications": {k: v.value for k, v in state.clarifications.items()},
    }


def expert_card_payload(state: SessionState):
    if not state.route_expert:
        return None
    top_candidates = state.candidates[:2]
    reason_parts = []
    if state.conflict:
        reason_parts.append(state.conflict.message)
    if state.confidence < uncertainty_gate.clarifying_threshold:
        reason_parts.append("候选置信度较低")
    reason = "；".join(reason_parts) if reason_parts else "需要专家确认口径与数据源"
    options = []
    labels = ["推测 A", "推测 B"]
    for idx, cand in enumerate(top_candidates):
        spec = cand.spec
        friendly_slots = clarifier._slot_values_for_spec(spec)
        options.append(
            {
                "label": labels[idx] if idx < len(labels) else f"推测 {idx + 1}",
                "confidence": round(cand.score, 2),
                "definition": spec.meta.description,
                "business_hint": friendly_slots.get("metric_caliber") or spec.semantics.metric_caliber,
                "source": f"{spec.physical.fact_table}.{spec.physical.measure_column}",
                "filters": [f.desc or f.expr for f in spec.semantics.filters],
                "spec_id": spec.spec_id,
                "snippet": agent.sql_generator.render(spec, state).splitlines()[:4],
            }
        )
    return {
        "title": "\ud83d\udcca 数据口径确认请求",
        "source_user": state.user,
        "original_query": state.intent.raw_query,
        "reason": reason,
        "options": options,
        "owners": agent.expert_router.owners,
        "forwarded_to": state.forwarded_to,
    }


def session_payload(state: SessionState, questions: Optional[List] = None, sql: str | None = None):
    return {
        "session_id": state.session_id,
        "user": state.user,
        "intent": serialize(state.intent),
        "candidates": [
            {
                "score": c.score,
                "spec": summarize_spec(c.spec, state),
            }
            for c in state.candidates
        ],
        "clarifications": serialize(state.clarifications),
        "selected_spec": summarize_spec(state.selected_spec, state) if state.selected_spec else None,
        "confidence": state.confidence,
        "route_expert": state.route_expert,
        "conflict": serialize(state.conflict) if state.conflict else None,
        "expert_card": expert_card_payload(state),
        "questions": serialize(questions) if questions else [],
        "slot_form": clarifier.slot_form(state),
        "confirmation": confirmation_payload(state),
        "sql": sql,
    }


class APIServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.send_error(404, "Unknown API path")
            return

        if self.path == "/":
            self.path = "/static/index.html"
        elif not self.path.startswith("/static/"):
            # Fall back to static directory for unknown assets
            self.path = f"/static{self.path}"
        return super().do_GET()

    # -----------------------------
    # API helpers
    # -----------------------------
    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _json_response(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_start(self, payload):
        query = payload.get("query", "")
        user = payload.get("user", "guest")
        state = agent.start_session(query, user)
        sessions[state.session_id] = state
        questions = clarifier.next_questions(state) if uncertainty_gate.needs_clarification(state) else []
        return session_payload(state, questions=questions)

    def _handle_clarify(self, payload):
        session_id = payload.get("session_id")
        answers_payload = payload.get("answers", [])
        state = sessions.get(session_id)
        if not state:
            return {"error": "session not found"}, 404
        answers = [ClarificationAnswer(slot=a.get("slot"), value=a.get("value")) for a in answers_payload]
        agent.clarify(state, answers)
        questions = clarifier.next_questions(state) if uncertainty_gate.needs_clarification(state) else []
        return session_payload(state, questions=questions), 200

    def _handle_expert_decision(self, payload):
        session_id = payload.get("session_id")
        action = payload.get("action")
        state = sessions.get(session_id)
        if not state:
            return {"error": "session not found"}, 404
        if action == "confirm":
            spec_id = payload.get("spec_id")
            match = next((c for c in state.candidates if c.spec.spec_id == spec_id), None)
            if not match:
                return {"error": "spec not found"}, 400
            agent.apply_expert_decision(state, match)
        elif action == "revise":
            answers_payload = payload.get("answers", [])
            answers = [ClarificationAnswer(slot=a.get("slot"), value=a.get("value")) for a in answers_payload]
            agent.clarify(state, answers)
            state.route_expert = False
        elif action == "forward":
            state.forwarded_to = payload.get("forward_to") or ""
        questions = clarifier.next_questions(state) if uncertainty_gate.needs_clarification(state) else []
        return session_payload(state, questions=questions), 200

    def _handle_resolve_conflict(self, payload):
        session_id = payload.get("session_id")
        option_id = payload.get("option_id")
        state = sessions.get(session_id)
        if not state:
            return {"error": "session not found"}, 404
        agent.resolve_conflict(state, option_id)
        questions = clarifier.next_questions(state) if uncertainty_gate.needs_clarification(state) else []
        return session_payload(state, questions=questions), 200

    def _handle_select(self, payload):
        session_id = payload.get("session_id")
        spec_id = payload.get("spec_id")
        state = sessions.get(session_id)
        if not state:
            return {"error": "session not found"}, 404
        match = next((c for c in state.candidates if c.spec.spec_id == spec_id), None)
        if not match:
            return {"error": "spec not in candidate list"}, 400
        state.selected_spec = match.spec
        store.bump_usage(match.spec.spec_id)
        return session_payload(state, questions=clarifier.next_questions(state)), 200

    def _handle_generate_sql(self, payload):
        session_id = payload.get("session_id")
        state = sessions.get(session_id)
        if not state:
            return {"error": "session not found"}, 404
        sql = agent.generate_sql(state)
        store.bump_usage(state.selected_spec.spec_id)  # type: ignore[arg-type]
        return session_payload(state, sql=sql), 200

    def do_POST(self):
        handlers = {
            "/api/session/start": self._handle_start,
            "/api/session/clarify": self._handle_clarify,
            "/api/session/select_spec": self._handle_select,
            "/api/session/generate_sql": self._handle_generate_sql,
            "/api/session/resolve_conflict": self._handle_resolve_conflict,
            "/api/expert/decision": self._handle_expert_decision,
        }
        handler = handlers.get(self.path)
        if not handler:
            self.send_error(404, "Unknown API path")
            return

        payload = self._read_json()
        result = handler(payload)
        if isinstance(result, tuple):
            body, status = result
        else:
            body, status = result, 200
        self._json_response(body, status=status)


# Entry point

def run(host: str = "0.0.0.0", port: int = 8000):
    server = HTTPServer((host, port), partial(APIServerHandler))
    print(f"Serving SQLess UI at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SQLess Metric Agent demo server.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    run(host=args.host, port=args.port)
