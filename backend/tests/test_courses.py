"""Tests for the course API."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_course(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "Intro to ML"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Intro to ML"
    assert data["description"] is None
    assert "id" in data
    # Verify it's a valid UUID
    uuid.UUID(data["id"])


@pytest.mark.asyncio
async def test_create_course_with_description(client: AsyncClient):
    resp = await client.post(
        "/courses",
        json={"name": "Stats 101", "description": "Introductory statistics"},
    )
    assert resp.status_code == 201
    assert resp.json()["description"] == "Introductory statistics"


@pytest.mark.asyncio
async def test_list_courses(client: AsyncClient):
    # Start empty
    resp = await client.get("/courses")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create two courses
    await client.post("/courses", json={"name": "Course A"})
    await client.post("/courses", json={"name": "Course B"})

    resp = await client.get("/courses")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_course(client: AsyncClient):
    resp = await client.post("/courses", json={"name": "My Course"})
    course_id = resp.json()["id"]

    resp = await client.get(f"/courses/{course_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Course"


@pytest.mark.asyncio
async def test_get_unknown_course(client: AsyncClient):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/courses/{fake_id}")
    assert resp.status_code == 404
