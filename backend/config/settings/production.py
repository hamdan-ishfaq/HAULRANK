from .base import *  # noqa: F401,F403

DEBUG = False
if SECRET_KEY == "dev-insecure-change-me":
    raise RuntimeError("DJANGO_SECRET_KEY must be set in production")
