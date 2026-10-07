from app.ai.deterministic import DeterministicAssistantProvider
from app.schemas import AssistantContext, AssistantRequest


def test_clinical_question_is_rejected():
    answer = DeterministicAssistantProvider().answer(
        AssistantRequest(question="What treatment is needed?"),
        AssistantContext(persona_id="nurse-a", facts=[]),
    )
    assert "administrative coordination only" in answer.answer


def test_denied_context_does_not_reveal_record():
    answer = DeterministicAssistantProvider().answer(
        AssistantRequest(question="Why is p9 on the queue?", patient_id="p9"),
        AssistantContext(persona_id="nurse-a", facts=[]),
    )
    assert answer.facts_used == [] and "unavailable" in answer.answer
