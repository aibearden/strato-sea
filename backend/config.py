from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT_DIR / ".env", _BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    aisstream_api_key: str = ""
    aisstream_url: str = "wss://stream.aisstream.io/v0/stream"

    vessel_ttl_seconds: int = 600
    stale_sweep_interval_seconds: float = 30.0
    broadcast_interval_seconds: float = 0.25

    # AISStream allows at most one subscription update per second.
    subscription_min_interval_seconds: float = 1.05

    # Expand the visible map slightly so ships do not vanish at the edge.
    viewport_buffer_ratio: float = 0.12

    # Zoom / span strategy: never subscribe to the entire world.
    min_zoom_for_stream: float = 5.0
    max_viewport_span_deg: float = 35.0

    cors_origins: str = "http://localhost:5173"
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
