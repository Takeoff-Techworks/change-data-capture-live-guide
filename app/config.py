import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("APP_DATABASE_URL", "sqlite:///./northstar.db")
    cdc_mode: str = os.getenv("CDC_MODE", "simulated")
    auto_process: bool = _bool("CDC_AUTO_PROCESS", True)
    artificial_delay_ms: int = int(os.getenv("CDC_ARTIFICIAL_DELAY_MS", "500"))
    consumer_paused: bool = _bool("CDC_CONSUMER_PAUSED", False)
    failure_mode: str = os.getenv("CDC_FAILURE_MODE", "none")
    assistant_provider: str = os.getenv("ASSISTANT_PROVIDER", "deterministic")
    reset_on_start: bool = _bool("DEMO_RESET_ON_START", False)


settings = Settings()
