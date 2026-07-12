import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.compliance.service import poll_all_drivers
from apps.fleet.models import Carrier, Driver, Truck
from apps.loads.models import Load

User = get_user_model()


@pytest.fixture
def carrier_fleet(db):
    user = User.objects.create_user(username="c1", password="x")
    carrier = Carrier.objects.create(name="C", owner=user)
    truck = Truck.objects.create(
        carrier=carrier,
        equipment_type="dry_van",
        current_lat=30.0,
        current_lon=-97.0,
        mpg=6.5,
    )
    driver = Driver.objects.create(
        truck=truck,
        hos_hours_remaining=10.0,
        home_base_lat=30.0,
        home_base_lon=-97.0,
        preferred_markets=["TX"],
        no_go_markets=[],
        hos_violations_90d=4,
        inspection_pass_rate=0.70,
        on_time_pct=0.60,
    )
    return user, carrier, truck, driver


@pytest.mark.django_db
def test_poll_transitions_to_restricted(carrier_fleet):
    user, _carrier, truck, driver = carrier_fleet
    assert driver.compliance_state == "clear"
    summary = poll_all_drivers(owner=user)
    assert summary["changed"] == 1
    driver.refresh_from_db()
    assert driver.compliance_state == "restricted"
    assert driver.compliance_checked_at is not None
    assert len(driver.compliance_history) == 1


@pytest.mark.django_db
def test_rank_refuses_suspended(carrier_fleet):
    user, _carrier, truck, driver = carrier_fleet
    Driver.objects.filter(pk=driver.pk).update(
        hos_violations_90d=6,
        compliance_state="suspended",
        compliance_reason="test",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(f"/api/rank/?truck_id={truck.id}")
    assert resp.status_code == 403
    assert resp.data["compliance_state"] == "suspended"


@pytest.mark.django_db
def test_assignment_blocks_suspended(carrier_fleet):
    user, _carrier, truck, driver = carrier_fleet
    Driver.objects.filter(pk=driver.pk).update(compliance_state="suspended")
    now = timezone.now()
    load = Load.objects.create(
        origin_lat=30.0,
        origin_lon=-97.0,
        dest_lat=32.0,
        dest_lon=-96.0,
        dest_market="TX",
        miles=200,
        rate_usd=800,
        equipment_type="dry_van",
        pickup_window_start=now,
        pickup_window_end=now,
        est_transit_hours=4.0,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        "/api/assignments/",
        {"load": load.id, "truck": truck.id},
        format="json",
    )
    assert resp.status_code == 400
    assert "suspended" in str(resp.data).lower()
