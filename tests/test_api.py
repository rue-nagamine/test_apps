"""API レベルのテスト。FastAPI の TestClient で HTTP をひととおり通す。"""

import pytest
from fastapi.testclient import TestClient

from app import models
from app.main import app, get_conn


@pytest.fixture
def client(tmp_path):
    """テストごとに使い捨ての SQLite に差し替える。"""
    conn = models.connect(tmp_path / "booking.db")
    app.dependency_overrides[get_conn] = lambda: conn
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    conn.close()


def test_rejects_room_with_zero_capacity(client):
    """定員 0 以下の会議室は登録できない。"""
    res = client.post("/api/rooms", json={"name": "第1会議室", "capacity": 0})
    assert res.status_code == 400

    assert client.get("/api/rooms").json() == []


def test_creates_and_lists_reservations(client):
    """作成した予約が開始時刻の昇順で一覧に並ぶ。

    テスト項目側に対応する ID を置いていないので、台帳では
    「紐づかなかった結果」として出るはず。
    """
    room = client.post("/api/rooms", json={"name": "第1会議室", "capacity": 6}).json()

    late = client.post(
        "/api/reservations",
        json={
            "room_id": room["id"],
            "title": "夕方の打ち合わせ",
            "start": "2026-04-01T16:00",
            "end": "2026-04-01T17:00",
            "attendees": 4,
        },
    )
    assert late.status_code == 201

    early = client.post(
        "/api/reservations",
        json={
            "room_id": room["id"],
            "title": "朝会",
            "start": "2026-04-01T09:30",
            "end": "2026-04-01T10:00",
            "attendees": 5,
        },
    )
    assert early.status_code == 201

    titles = [r["title"] for r in client.get("/api/reservations").json()]
    assert titles == ["朝会", "夕方の打ち合わせ"]
