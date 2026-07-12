from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.fleet.models import Truck
from apps.loads.models import Load

ACTIVE_STATUSES = ("offered", "accepted", "dispatched")


class Assignment(models.Model):
    class Status(models.TextChoices):
        OFFERED = "offered", "Offered"
        ACCEPTED = "accepted", "Accepted"
        DISPATCHED = "dispatched", "Dispatched"
        DELIVERED = "delivered", "Delivered"

    TRANSITIONS = {
        Status.OFFERED: {Status.ACCEPTED},
        Status.ACCEPTED: {Status.DISPATCHED},
        Status.DISPATCHED: {Status.DELIVERED},
        Status.DELIVERED: set(),
    }

    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name="assignments")
    truck = models.ForeignKey(Truck, on_delete=models.CASCADE, related_name="assignments")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OFFERED
    )
    status_history = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["load"],
                condition=Q(status__in=list(ACTIVE_STATUSES)),
                name="uniq_active_assignment_per_load",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.status_history:
            self.status_history = [
                {"status": self.status, "at": timezone.now().isoformat()}
            ]
        super().save(*args, **kwargs)

    def transition_to(self, new_status: str, by: str | None = None):
        with transaction.atomic():
            # Lock the load row first so concurrent accepts serialize (no deadlock).
            Load.objects.select_for_update().filter(pk=self.load_id).get()
            try:
                locked = Assignment.objects.select_for_update().filter(pk=self.pk).get()
            except Assignment.DoesNotExist as exc:
                # Competing accept already won and deleted this offer.
                raise ValueError("Load already has an active assignment") from exc

            allowed = locked.TRANSITIONS.get(locked.status, set())
            if new_status not in allowed:
                raise ValueError(f"Cannot transition {locked.status} → {new_status}")

            if new_status == Assignment.Status.ACCEPTED:
                # Another truck already won this load
                if (
                    Assignment.objects.filter(
                        load_id=locked.load_id,
                        status__in=[
                            Assignment.Status.ACCEPTED,
                            Assignment.Status.DISPATCHED,
                        ],
                    )
                    .exclude(pk=locked.pk)
                    .exists()
                ):
                    raise ValueError("Load already has an active assignment")
                # Drop competing offers (unique constraint: one active row)
                Assignment.objects.filter(
                    load_id=locked.load_id, status=Assignment.Status.OFFERED
                ).exclude(pk=locked.pk).delete()

            locked.status = new_status
            entry = {"status": new_status, "at": timezone.now().isoformat()}
            if by:
                entry["by"] = by
            history = list(locked.status_history or [])
            history.append(entry)
            locked.status_history = history
            locked.save(update_fields=["status", "status_history"])
            self.status = locked.status
            self.status_history = locked.status_history
