from django.db import models
from django.utils import timezone

from apps.fleet.models import Truck
from apps.loads.models import Load


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

    def save(self, *args, **kwargs):
        if not self.status_history:
            self.status_history = [
                {"status": self.status, "at": timezone.now().isoformat()}
            ]
        super().save(*args, **kwargs)

    def transition_to(self, new_status: str, by: str | None = None):
        allowed = self.TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(f"Cannot transition {self.status} → {new_status}")
        self.status = new_status
        entry = {"status": new_status, "at": timezone.now().isoformat()}
        if by:
            entry["by"] = by
        history = list(self.status_history or [])
        history.append(entry)
        self.status_history = history
        self.save(update_fields=["status", "status_history"])
