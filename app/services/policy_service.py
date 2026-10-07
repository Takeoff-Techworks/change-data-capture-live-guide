from app.ai import assistant_provider
from app.config import settings
from app.models import CareWorkQueue
from app.schemas import AssistantContext, AssistantRequest

from .authorization_service import can_access_patient, persona


def ask_assistant(db, user_id: str, request: AssistantRequest):
    provider = assistant_provider()
    user = persona(db, user_id)
    if request.patient_id and not can_access_patient(db, user, request.patient_id):
        context = AssistantContext(persona_id=user_id, facts=[], freshness=None, stale=False)
        return provider.answer(request, context)
    query = db.query(CareWorkQueue)
    if request.patient_id:
        query = query.filter(CareWorkQueue.patient_id == request.patient_id)
    facts = []
    for row in query.all():
        if can_access_patient(db, user, row.patient_id):
            import json

            facts.append(
                {
                    "patient_id": row.patient_id,
                    "patient_display_name": row.patient_display_name,
                    "priority_score": row.priority_score,
                    "priority_reasons": json.loads(row.priority_reasons_json),
                    "open_task_count": row.open_task_count,
                    "overdue_task_count": row.overdue_task_count,
                    "pending_referral_count": row.pending_referral_count,
                    "latest_appointment_status": row.latest_appointment_status,
                }
            )
    from app.cdc.consumer import refresh_state

    state = refresh_state(db)
    return provider.answer(
        request,
        AssistantContext(
            persona_id=user_id,
            facts=facts,
            freshness=state.projection_freshness_at,
            stale=bool(state.paused or state.pending_event_count),
        ),
    )


def assistant_provider_name() -> str:
    return settings.assistant_provider.lower()
