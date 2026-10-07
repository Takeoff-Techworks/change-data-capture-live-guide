from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareTeamAssignment, Patient, Provider, User


def persona(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise PermissionError("Unknown demo persona")
    return user


def can_access_patient(db: Session, user: User, patient_id: str) -> bool:
    if user.role in {"admin", "receptionist"}:
        return True
    assignment = db.scalar(
        select(CareTeamAssignment).where(CareTeamAssignment.patient_id == patient_id)
    )
    if not assignment:
        return False
    if user.role == "nurse":
        return assignment.nurse_user_id == user.user_id
    if user.role in {"doctor", "pa"}:
        provider = db.scalar(select(Provider).where(Provider.user_id == user.user_id))
        return bool(provider and assignment.provider_id == provider.provider_id)
    return False


def visible_patients(db: Session, user: User):
    query = select(Patient)
    if user.role in {"admin", "receptionist"}:
        return list(db.scalars(query))
    assignments = select(CareTeamAssignment.patient_id)
    if user.role == "nurse":
        assignments = assignments.where(CareTeamAssignment.nurse_user_id == user.user_id)
    else:
        provider = db.scalar(select(Provider).where(Provider.user_id == user.user_id))
        if not provider:
            return []
        assignments = assignments.where(CareTeamAssignment.provider_id == provider.provider_id)
    return list(db.scalars(query.where(Patient.patient_id.in_(assignments))))
