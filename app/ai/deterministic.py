from app.schemas import AssistantAnswer, AssistantContext, AssistantRequest

CLINICAL_RESPONSE = "This synthetic demo supports administrative coordination only and cannot provide clinical guidance."


class DeterministicAssistantProvider:
    def answer(self, request: AssistantRequest, context: AssistantContext) -> AssistantAnswer:
        question = request.question.lower()
        if any(
            word in question
            for word in ("diagnos", "treatment", "medication", "symptom", "clinical", "risk score")
        ):
            return AssistantAnswer(
                answer=CLINICAL_RESPONSE,
                facts_used=[],
                freshness=context.freshness,
                may_be_stale=context.stale,
            )
        if not context.facts:
            return AssistantAnswer(
                answer="Access is unavailable for that administrative record.",
                facts_used=[],
                freshness=context.freshness,
                may_be_stale=context.stale,
            )
        if "overdue" in question:
            rows = [f for f in context.facts if f.get("overdue_task_count", 0)]
            message = f"You have {sum(f['overdue_task_count'] for f in rows)} overdue administrative task(s) across {len(rows)} visible patient record(s)."
        elif "referral" in question and "seven" in question:
            rows = [f for f in context.facts if f.get("pending_referral_count", 0)]
            message = (
                f"{len(rows)} visible patient record(s) have pending referral coordination work."
            )
        elif "current" in question or "projection" in question:
            message = (
                "The coordination projection is current."
                if not context.stale
                else "The coordination projection may be stale while pending events remain."
            )
        else:
            top = context.facts[0]
            message = (
                f"{top['patient_display_name']} is on the coordination queue with priority {top['priority_score']}: "
                + "; ".join(top.get("priority_reasons", []) or ["no active priority rules"])
            )
        return AssistantAnswer(
            answer=message,
            facts_used=context.facts,
            freshness=context.freshness,
            may_be_stale=context.stale,
        )
