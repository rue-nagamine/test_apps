"""会議室予約 API。

業務ルールは booking.py にまとめてあり、ここはその入口と HTTP の作法だけ。
BookingError は 400 に変換して、画面がそのままメッセージを出せるようにする。
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import booking, models

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="会議室予約 API", version="1.0.0")


def get_conn():
    conn = models.connect()
    try:
        yield conn
    finally:
        conn.close()


# --------------------------------------------------------------------------
# リクエストの形
# --------------------------------------------------------------------------

class RoomIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    capacity: int


class ReservationIn(BaseModel):
    room_id: int
    title: str = Field(min_length=1, max_length=100)
    start: datetime
    end: datetime
    attendees: int


# --------------------------------------------------------------------------
# 画面
# --------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


# --------------------------------------------------------------------------
# 会議室
# --------------------------------------------------------------------------

@app.get("/api/rooms")
def get_rooms(conn: sqlite3.Connection = Depends(get_conn)):
    return [room.as_dict() for room in models.list_rooms(conn)]


@app.post("/api/rooms", status_code=201)
def create_room(payload: RoomIn, conn: sqlite3.Connection = Depends(get_conn)):
    if payload.capacity < 1:
        raise HTTPException(400, detail="定員は1名以上にしてください")
    try:
        room = models.add_room(conn, payload.name, payload.capacity)
    except sqlite3.IntegrityError:
        raise HTTPException(400, detail=f"「{payload.name}」はすでに登録されています")
    return room.as_dict()


# --------------------------------------------------------------------------
# 予約
# --------------------------------------------------------------------------

@app.get("/api/reservations")
def get_reservations(conn: sqlite3.Connection = Depends(get_conn)):
    return [r.as_dict() for r in models.list_reservations(conn)]


@app.post("/api/reservations", status_code=201)
def create_reservation(payload: ReservationIn, conn: sqlite3.Connection = Depends(get_conn)):
    room = models.get_room(conn, payload.room_id)
    if room is None:
        raise HTTPException(404, detail="会議室が見つかりません")

    existing = models.reservations_for_room(conn, room.id)
    try:
        booking.validate_reservation(
            room, payload.start, payload.end, payload.attendees, existing
        )
    except booking.BookingError as exc:
        raise HTTPException(400, detail=exc.message)

    reservation = models.add_reservation(
        conn, room.id, payload.title, payload.start, payload.end, payload.attendees
    )
    return reservation.as_dict()


@app.delete("/api/reservations/{reservation_id}", status_code=204)
def cancel_reservation(
    reservation_id: int, conn: sqlite3.Connection = Depends(get_conn)
):
    reservation = models.get_reservation(conn, reservation_id)
    if reservation is None:
        raise HTTPException(404, detail="予約が見つかりません")

    try:
        booking.validate_cancel(reservation, datetime.now())
    except booking.BookingError as exc:
        raise HTTPException(400, detail=exc.message)

    models.delete_reservation(conn, reservation_id)
