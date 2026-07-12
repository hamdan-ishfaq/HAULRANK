from .base import *  # noqa: F401,F403

DEBUG = False
if SECRET_KEY == "dev-insecure-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")

# Force stdout logging so Render/Docker captures every line.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "corsheaders": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "haulrank": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "haulrank.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Optional Sentry — set SENTRY_DSN on Render to enable crash/tracing emails.
_sentry_dsn = env("SENTRY_DSN", default="")  # noqa: F405
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(env("SENTRY_TRACES_SAMPLE_RATE", default="0.2")),  # noqa: F405
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production"),  # noqa: F405
    )
