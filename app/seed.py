from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Appointment, CareTask, CareTeamAssignment, Patient, Provider, Referral, User


def utcnow() -> datetime:
    return datetime.now(UTC)


def seed_demo(db: Session) -> None:
    if db.scalar(select(User).limit(1)):
        return
    now = utcnow()
    users = [
        User(user_id="admin", role="admin", full_name="Avery Morgan", team_id="operations"),
        User(
            user_id="reception-1", role="receptionist", full_name="Morgan Lee", team_id="front-desk"
        ),
        User(
            user_id="reception-2",
            role="receptionist",
            full_name="Casey Rowan",
            team_id="front-desk",
        ),
        User(user_id="nurse-a", role="nurse", full_name="Riley Chen", team_id="team-a"),
        User(user_id="nurse-b", role="nurse", full_name="Jordan Blake", team_id="team-b"),
        User(user_id="doctor-a", role="doctor", full_name="Taylor Quinn", team_id="team-a"),
        User(user_id="pa-b", role="pa", full_name="Cameron Patel", team_id="team-b"),
    ]
    db.add_all(users)
    providers = [
        Provider(
            provider_id="prov-a",
            user_id="doctor-a",
            specialty="Primary Care",
            clinic_location="Northstar East",
        ),
        Provider(
            provider_id="prov-b",
            user_id="pa-b",
            specialty="Primary Care",
            clinic_location="Northstar West",
        ),
    ]
    db.add_all(providers)
    patients = [
        Patient(
            patient_id=f"p{i}",
            display_name=name,
            birth_year=1980 + i,
            contact_preference="portal",
            created_at=now,
            updated_at=now,
        )
        for i, name in enumerate(
            [
                "Arden Vale",
                "Briar Finch",
                "Cedar North",
                "Dara Sol",
                "Ember Lake",
                "Flint Gray",
                "Gale Winter",
                "Harbor Reed",
                "Indigo Moss",
                "Juniper Hale",
            ],
            1,
        )
    ]
    db.add_all(patients)
    # Persist referenced rows before adding appointments, referrals, and tasks.
    db.flush()
    db.add_all(
        [
            CareTeamAssignment(
                assignment_id=f"a{i}",
                patient_id=f"p{i}",
                nurse_user_id="nurse-a" if i <= 5 else "nurse-b",
                provider_id="prov-a" if i <= 5 else "prov-b",
                assigned_at=now,
                updated_at=now,
            )
            for i in range(1, 11)
        ]
    )
    statuses = [
        "completed",
        "no_show",
        "scheduled",
        "canceled",
        "scheduled",
        "completed",
        "scheduled",
        "scheduled",
        "completed",
        "scheduled",
    ]
    db.add_all(
        [
            Appointment(
                appointment_id=f"appt{i}",
                patient_id=f"p{i}",
                provider_id="prov-a" if i <= 5 else "prov-b",
                scheduled_start_at=now + timedelta(days=i - 5),
                status=statuses[i - 1],
                reason_code="admin_follow_up" if i == 4 else None,
                updated_at=now - timedelta(hours=i),
            )
            for i in range(1, 11)
        ]
    )
    db.add_all(
        [
            Referral(
                referral_id="ref1",
                patient_id="p3",
                requested_by_provider_id="prov-a",
                receiving_specialty="Mobility Services",
                status="pending",
                requested_at=now - timedelta(days=10),
                scheduled_for_at=None,
                updated_at=now,
            ),
            Referral(
                referral_id="ref2",
                patient_id="p4",
                requested_by_provider_id="prov-a",
                receiving_specialty="Scheduling Office",
                status="requested",
                requested_at=now - timedelta(days=2),
                scheduled_for_at=None,
                updated_at=now,
            ),
            Referral(
                referral_id="ref3",
                patient_id="p6",
                requested_by_provider_id="prov-b",
                receiving_specialty="Community Support",
                status="scheduled",
                requested_at=now - timedelta(days=4),
                scheduled_for_at=now + timedelta(days=7),
                updated_at=now,
            ),
            Referral(
                referral_id="ref4",
                patient_id="p7",
                requested_by_provider_id="prov-b",
                receiving_specialty="Mobility Services",
                status="closed",
                requested_at=now - timedelta(days=12),
                scheduled_for_at=None,
                updated_at=now,
            ),
            Referral(
                referral_id="ref5",
                patient_id="p8",
                requested_by_provider_id="prov-b",
                receiving_specialty="Scheduling Office",
                status="pending",
                requested_at=now - timedelta(days=8),
                scheduled_for_at=None,
                updated_at=now,
            ),
            Referral(
                referral_id="ref6",
                patient_id="p1",
                requested_by_provider_id="prov-a",
                receiving_specialty="Community Support",
                status="closed",
                requested_at=now - timedelta(days=3),
                scheduled_for_at=None,
                updated_at=now,
            ),
        ]
    )
    task_data = [
        ("p2", "appt2", "reschedule", "open", "nurse-a", -2),
        ("p3", None, "referral_follow_up", "open", "nurse-a", 2),
        ("p4", "appt4", "contact_patient", "completed", "nurse-a", -1),
        ("p5", None, "follow_up", "open", "nurse-a", 0),
        ("p6", None, "follow_up", "open", "nurse-b", 3),
        ("p7", None, "contact_patient", "in_progress", "nurse-b", 1),
        ("p8", None, "referral_follow_up", "open", "nurse-b", -3),
        ("p9", None, "follow_up", "completed", "nurse-b", -2),
        ("p10", None, "contact_patient", "open", "nurse-b", 1),
        ("p1", None, "follow_up", "completed", "nurse-a", -5),
    ]
    db.add_all(
        [
            CareTask(
                task_id=f"task{i}",
                patient_id=p,
                appointment_id=appt,
                referral_id=None,
                task_type=kind,
                status=status,
                assigned_to_user_id=nurse,
                due_at=now + timedelta(days=due),
                priority="high" if due < 0 else "normal",
                priority_reason="seed scenario",
                created_at=now,
                updated_at=now,
            )
            for i, (p, appt, kind, status, nurse, due) in enumerate(task_data, 1)
        ]
    )
    db.commit()
