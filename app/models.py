"""SQLite のストレージ層。テーブル2つ分の薄いラッパ。

日時は ISO 8601 の文字列で持つ。SQLite に日時型はないので、素直に並べ替え
られる形式で入れておくのが一番わかりやすい。
"""

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "booking.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE,
    capacity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id   INTEGER NOT NULL REFERENCES rooms(id),
    title     TEXT    NOT NULL,
    start     TEXT    NOT NULL,
    "end"     TEXT    NOT NULL,
    attendees INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reservations_room ON reservations(room_id, start);
"""


@dataclass
class Room:
    id: int | None
    name: str
    capacity: int

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "capacity": self.capacity}


@dataclass
class Reservation:
    id: int | None
    room_id: int
    title: str
    start: datetime
    end: datetime
    attendees: int

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "title": self.title,
            "start": self.start.isoformat(timespec="minutes"),
            "end": self.end.isoformat(timespec="minutes"),
            "attendees": self.attendees,
        }


def db_path() -> Path:
    """テストは BOOKING_DB で一時ファイルに差し替える。"""
    return Path(os.environ.get("BOOKING_DB") or DEFAULT_DB)


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI は同期のエンドポイントをスレッドプールで動かすので、接続を
    # 作ったスレッドと実際に使うスレッドが一致しない。
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# --------------------------------------------------------------------------
# 会議室
# --------------------------------------------------------------------------

def add_room(conn: sqlite3.Connection, name: str, capacity: int) -> Room:
    cur = conn.execute(
        "INSERT INTO rooms (name, capacity) VALUES (?, ?)", (name.strip(), capacity)
    )
    conn.commit()
    return Room(id=cur.lastrowid, name=name.strip(), capacity=capacity)


def list_rooms(conn: sqlite3.Connection) -> list[Room]:
    rows = conn.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    return [Room(id=r["id"], name=r["name"], capacity=r["capacity"]) for r in rows]


def get_room(conn: sqlite3.Connection, room_id: int) -> Room | None:
    row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return Room(id=row["id"], name=row["name"], capacity=row["capacity"]) if row else None


# --------------------------------------------------------------------------
# 予約
# --------------------------------------------------------------------------

def _to_reservation(row: sqlite3.Row) -> Reservation:
    return Reservation(
        id=row["id"],
        room_id=row["room_id"],
        title=row["title"],
        start=datetime.fromisoformat(row["start"]),
        end=datetime.fromisoformat(row["end"]),
        attendees=row["attendees"],
    )


def add_reservation(
    conn: sqlite3.Connection,
    room_id: int,
    title: str,
    start: datetime,
    end: datetime,
    attendees: int,
) -> Reservation:
    cur = conn.execute(
        'INSERT INTO reservations (room_id, title, start, "end", attendees)'
        " VALUES (?, ?, ?, ?, ?)",
        (room_id, title.strip(), start.isoformat(), end.isoformat(), attendees),
    )
    conn.commit()
    return Reservation(cur.lastrowid, room_id, title.strip(), start, end, attendees)


def list_reservations(conn: sqlite3.Connection) -> list[Reservation]:
    rows = conn.execute("SELECT * FROM reservations ORDER BY start, id").fetchall()
    return [_to_reservation(r) for r in rows]


def reservations_for_room(conn: sqlite3.Connection, room_id: int) -> list[Reservation]:
    rows = conn.execute(
        "SELECT * FROM reservations WHERE room_id = ? ORDER BY start", (room_id,)
    ).fetchall()
    return [_to_reservation(r) for r in rows]


def get_reservation(conn: sqlite3.Connection, reservation_id: int) -> Reservation | None:
    row = conn.execute(
        "SELECT * FROM reservations WHERE id = ?", (reservation_id,)
    ).fetchone()
    return _to_reservation(row) if row else None


def delete_reservation(conn: sqlite3.Connection, reservation_id: int) -> None:
    conn.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
    conn.commit()
