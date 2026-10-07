from datetime import UTC, datetime, timedelta


def score(tasks, referrals, latest_appointment):
    now = datetime.now(UTC)

    def aware(value):
        return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value

    reasons, value = [], 0
    if any(aware(t.due_at) and aware(t.due_at) < now for t in tasks):
        value += 50
        reasons.append("Open task overdue (+50)")
    if any(
        r.status in {"requested", "pending"} and aware(r.requested_at) < now - timedelta(days=7)
        for r in referrals
    ):
        value += 30
        reasons.append("Referral pending more than 7 days (+30)")
    if (
        latest_appointment
        and latest_appointment.status == "no_show"
        and not any(t.task_type == "reschedule" for t in tasks)
    ):
        value += 20
        reasons.append("No-show has no active reschedule task (+20)")
    if any(aware(t.due_at) and now <= aware(t.due_at) <= now + timedelta(hours=24) for t in tasks):
        value += 10
        reasons.append("Open task due within 24 hours (+10)")
    return value, reasons
