from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import Session
from app.main import app
from app.models import Booking, Desk, Location, Wallet
from app.reminders import claim_due_reminders


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def workspace(client):
    city = f"Test city {uuid4().hex}"

    async def create_workspace():
        async with Session.begin() as session:
            location = Location(name="Test hub", address="Test street", city=city)
            session.add(location)
            await session.flush()
            desk = Desk(
                name="Test desk",
                location_id=location.id,
                kind="open_space",
                hourly_rate=Decimal("120.00"),
            )
            session.add(desk)
            await session.flush()
            return desk.id, city

    return client.portal.call(create_workspace)


def register(client, funds=None):
    email = f"{uuid4().hex}@example.com"
    password = "test-password-123"
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    response = client.post("/auth/token", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    if funds is not None:
        response = client.post("/wallet/top-up", headers=headers, json={"amount": funds})
        assert response.status_code == 200, response.text
    return user_id, headers


def booking_payload(desk_id, start=None):
    if start is None:
        start = datetime.now(timezone.utc) + timedelta(days=2)
    return {
        "desk_id": desk_id,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
    }


async def booking_state(desk_id, user_id):
    async with Session() as session:
        wallet = await session.get(Wallet, user_id)
        bookings = await session.scalars(
            select(Booking.id).where(Booking.desk_id == desk_id)
        )
        return wallet.balance, len(bookings.all())


def test_rejects_booking_with_insufficient_funds(client, workspace):
    desk_id, _ = workspace
    user_id, headers = register(client, funds="20.00")

    response = client.post("/bookings", headers=headers, json=booking_payload(desk_id))

    assert response.status_code == 409
    assert response.json()["detail"] == "Insufficient funds"
    assert client.portal.call(booking_state, desk_id, user_id) == (Decimal("20.00"), 0)


def test_rejects_partial_overlap_without_another_charge(client, workspace):
    desk_id, _ = workspace
    user_id, headers = register(client, funds="300.00")
    starts_at = datetime.now(timezone.utc) + timedelta(days=2)
    first = client.post("/bookings", headers=headers, json=booking_payload(desk_id, starts_at))
    assert first.status_code == 201, first.text

    second = client.post(
        "/bookings",
        headers=headers,
        json=booking_payload(desk_id, starts_at + timedelta(minutes=30)),
    )

    assert second.status_code == 409
    assert second.json()["detail"] == "Desk is already booked"
    assert client.portal.call(booking_state, desk_id, user_id) == (Decimal("180.00"), 1)


def test_concurrent_requests_charge_only_one_booking(client, workspace):
    desk_id, _ = workspace
    user_id, headers = register(client, funds="300.00")
    payload = booking_payload(desk_id)

    def reserve():
        return client.post("/bookings", headers=headers, json=payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(reserve) for _ in range(2)]
        statuses = sorted(request.result().status_code for request in pending)

    assert statuses == [201, 409]
    assert client.portal.call(booking_state, desk_id, user_id) == (Decimal("180.00"), 1)


def test_only_owner_can_cancel_and_refund_is_applied_once(client, workspace):
    desk_id, _ = workspace
    owner_id, owner = register(client, funds="200.00")
    _, other_user = register(client)
    payload = booking_payload(desk_id)
    booking = client.post("/bookings", headers=owner, json=payload)
    assert booking.status_code == 201, booking.text
    cancel_url = f"/bookings/{booking.json()['id']}/cancel"

    assert client.post(cancel_url, headers=other_user).status_code == 404
    assert client.post(cancel_url, headers=owner).status_code == 200
    assert client.post(cancel_url, headers=owner).status_code == 409
    assert client.portal.call(booking_state, desk_id, owner_id) == (Decimal("200.00"), 1)
    assert client.post("/bookings", headers=owner, json=payload).status_code == 201


def test_availability_excludes_overlaps_and_caches_results(client, workspace):
    desk_id, city = workspace
    _, headers = register(client, funds="200.00")
    start = datetime.now(timezone.utc) + timedelta(days=2)
    payload = booking_payload(desk_id, start)
    response = client.post("/bookings", headers=headers, json=payload)
    assert response.status_code == 201, response.text

    def search(window):
        return client.get(
            "/availability",
            params={"city": city, "starts_at": window["starts_at"], "ends_at": window["ends_at"]},
        )

    busy = search(payload)
    assert busy.status_code == 200, busy.text
    assert busy.json() == []
    adjacent_window = booking_payload(desk_id, start + timedelta(hours=1))
    free = search(adjacent_window)
    assert free.status_code == 200, free.text
    assert [desk["id"] for desk in free.json()] == [desk_id]
    assert search(adjacent_window).json() == free.json()

    async def cached_results():
        cache = app.state.availability_cache
        return [await cache.get(key) async for key in cache.scan_iter("availability:v1:*")]

    assert any(
        any(desk["id"] == desk_id for desk in json.loads(result))
        for result in client.portal.call(cached_results)
        if result is not None
    )


def test_reminder_is_due_one_hour_before_start_and_claimed_once(client, workspace):
    desk_id, _ = workspace
    _, headers = register(client, funds="200.00")
    start = datetime.now(timezone.utc) + timedelta(days=2)
    response = client.post("/bookings", headers=headers, json=booking_payload(desk_id, start))
    assert response.status_code == 201, response.text
    booking_id = response.json()["id"]
    due = start - timedelta(hours=1)

    def claimed_ids(now):
        return [row[0] for row in client.portal.call(claim_due_reminders, now)]

    assert booking_id not in claimed_ids(due - timedelta(microseconds=1))
    assert booking_id in claimed_ids(due)
    assert booking_id not in claimed_ids(due)
