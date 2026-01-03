from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List

from .models import ClarificationAnswer, ClarificationQuestion, SessionState


class ClarificationEngine:
    """Generates low-friction clarification questions and applies answers."""

    QUESTION_BANK: List[ClarificationQuestion] = [
        ClarificationQuestion(
            slot="metric_caliber",
            question="请选择 GMV 口径",
            options=["下单", "支付", "结算"],
            recommended="支付",
        ),
        ClarificationQuestion(
            slot="industry_mapping",
            question="请选择行业定义",
            options=["类目行业", "商家行业", "内容行业"],
            recommended="类目行业",
        ),
        ClarificationQuestion(
            slot="time_semantics",
            question="请选择时间口径",
            options=["自然日(UTC+8)", "业务日"],
            recommended="自然日(UTC+8)",
        ),
    ]

    def __init__(self, max_questions: int = 3) -> None:
        self.max_questions = max_questions

    def _slot_values_for_spec(self, spec) -> Dict[str, str]:  # type: ignore[override]
        values: Dict[str, str] = {}
        if spec.semantics.metric_caliber:
            values["metric_caliber"] = spec.semantics.metric_caliber
        if spec.semantics.industry_mapping:
            dim_table = spec.semantics.industry_mapping.dim_table
            values["industry_mapping"] = (
                "商家行业" if "merchant" in dim_table or "shop" in dim_table else "类目行业"
            )
        if spec.semantics.time_semantics:
            rule = spec.semantics.time_semantics.business_day_rule
            values["time_semantics"] = "自然日(UTC+8)" if "natural" in rule else "业务日"
        return values

    def _recommended_value(self, slot: str, state: SessionState) -> str | None:
        if state.selected_spec:
            selected_values = self._slot_values_for_spec(state.selected_spec)
            if slot in selected_values:
                return selected_values[slot]
        counts: Counter[str] = Counter()
        for candidate in state.candidates:
            slot_values = self._slot_values_for_spec(candidate.spec)
            if slot_values.get(slot):
                counts[slot_values[slot]] += 1
        if counts:
            return counts.most_common(1)[0][0]
        for question in self.QUESTION_BANK:
            if question.slot == slot:
                return question.recommended
        return None

    def next_questions(self, state: SessionState) -> List[ClarificationQuestion]:
        asked_slots = set(state.clarifications.keys())
        ranked: List[tuple[int, ClarificationQuestion]] = []
        for question in self.QUESTION_BANK:
            if question.slot in asked_slots:
                continue
            values = set()
            for candidate in state.candidates:
                slot_values = self._slot_values_for_spec(candidate.spec)
                if question.slot in slot_values:
                    values.add(slot_values[question.slot])
            info_gain = len(values)
            if info_gain == 0 and state.selected_spec:
                # Allow confirmation question even if not differentiating
                info_gain = 1
            if info_gain > 0:
                recommended = self._recommended_value(question.slot, state)
                ranked.append((info_gain, ClarificationQuestion(
                    slot=question.slot,
                    question=question.question,
                    options=question.options,
                    recommended=recommended,
                )))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in ranked[: self.max_questions]]

    def apply_answers(self, state: SessionState, answers: Iterable[ClarificationAnswer]) -> None:
        for ans in answers:
            state.clarifications[ans.slot] = ans

    def summarize_answers(self, state: SessionState) -> str:
        if not state.clarifications:
            return "暂无澄清答案"
        parts = [f"{slot}: {ans.value}" for slot, ans in state.clarifications.items()]
        return " | ".join(parts)

    def slot_form(self, state: SessionState) -> List[Dict[str, str | List[str] | None]]:
        form = []
        for question in self.QUESTION_BANK:
            form.append(
                {
                    "slot": question.slot,
                    "label": question.question,
                    "options": question.options,
                    "value": state.clarifications.get(question.slot, None).value
                    if state.clarifications.get(question.slot)
                    else self._recommended_value(question.slot, state),
                }
            )
        return form
