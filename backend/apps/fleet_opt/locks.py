"""Brownfield locked assignments (accepted/dispatched) for fleet optimize."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from apps.assignments.models import Assignment


# Committed plan — offered is soft; brownfield locks use accepted/dispatched
LOCKED_STATUSES = ("accepted", "dispatched")


def locked_pairs_for_carrier(owner: AbstractBaseUser) -> list[tuple[int, int]]:
    """Return (truck_id, load_id) pairs already committed for this carrier."""
    qs = (
        Assignment.objects.filter(
            truck__carrier__owner=owner,
            status__in=LOCKED_STATUSES,
        )
        .values_list("truck_id", "load_id")
        .order_by("id")
    )
    return [(int(t), int(l)) for t, l in qs]
