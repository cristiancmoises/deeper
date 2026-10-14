"""Validated server settings; there are no browser-side dependencies."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    top_sites: int = 500
    site_timeout: float = 10
    search_timeout: float = 180
    max_connections: int = 20
    workers: int = 2
    max_jobs: int = 64
    max_jobs_per_session: int = 2
    retention: float = 900
    cache_ttl: float = 60
    worker_max_jobs: int = 25
    worker_idle_timeout: float = 120
    secret_key: str = ""
    secure_cookie: bool = False

    def __post_init__(self):
        for name in (
            "site_timeout",
            "search_timeout",
            "max_connections",
            "workers",
            "max_jobs",
            "max_jobs_per_session",
            "retention",
            "worker_max_jobs",
            "worker_idle_timeout",
        ):
            value = getattr(self, name)
            if not 0 < value < float("inf"):
                raise ValueError(f"{name} must be a finite positive number")
        if self.top_sites < 0:
            raise ValueError("top_sites must be zero (all sites) or positive")
        if not 0 <= self.cache_ttl < float("inf"):
            raise ValueError("cache_ttl must be finite and nonnegative")
        for name in (
            "top_sites",
            "max_connections",
            "workers",
            "max_jobs",
            "max_jobs_per_session",
            "worker_max_jobs",
        ):
            if not isinstance(getattr(self, name), int):
                raise ValueError(f"{name} must be an integer")  # noqa: TRY004 - public settings contract

    @classmethod
    def from_env(cls):
        fields = {
            "top_sites": ("DEEPER_TOP_SITES", int),
            "site_timeout": ("DEEPER_SITE_TIMEOUT", float),
            "search_timeout": ("DEEPER_SEARCH_TIMEOUT", float),
            "max_connections": ("DEEPER_CONNECTIONS", int),
            "workers": ("DEEPER_WORKERS", int),
            "max_jobs": ("DEEPER_MAX_JOBS", int),
            "max_jobs_per_session": ("DEEPER_MAX_JOBS_PER_SESSION", int),
            "retention": ("DEEPER_RETENTION", float),
            "cache_ttl": ("DEEPER_CACHE_TTL", float),
            "worker_max_jobs": ("DEEPER_WORKER_MAX_JOBS", int),
            "worker_idle_timeout": ("DEEPER_WORKER_IDLE_TIMEOUT", float),
        }
        values = {
            name: convert(os.environ[key])
            for name, (key, convert) in fields.items()
            if key in os.environ
        }
        values["secret_key"] = os.getenv("DEEPER_SECRET_KEY", "")
        values["secure_cookie"] = os.getenv("DEEPER_SECURE_COOKIE", "0") == "1"
        return cls(**values)
