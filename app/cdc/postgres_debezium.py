from .normalizer import debezium_event

ADAPTER_LABEL = "PostgreSQL + Debezium fixture/ingestion mode"


def normalize(payload: dict):
    return debezium_event(payload)
