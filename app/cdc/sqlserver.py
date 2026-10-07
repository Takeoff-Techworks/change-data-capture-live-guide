from .normalizer import sqlserver_event

ADAPTER_LABEL = "SQL Server adapter fixture/ingestion mode"


def normalize(payload: dict):
    return sqlserver_event(payload)
