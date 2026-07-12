from .base import *  # noqa: F401,F403

# Compose sets DJANGO_DEBUG=0; bare local defaults to True for DX.
DEBUG = env.bool("DJANGO_DEBUG", default=True)  # noqa: F405
