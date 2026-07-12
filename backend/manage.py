#!/usr/bin/env python
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")


def main():
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
