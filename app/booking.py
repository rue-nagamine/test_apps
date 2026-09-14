"""予約の業務ルール。このアプリでテストの差が出るのはここ。

ストレージにも HTTP にも依存させていないので、単体テストは会議室と
既存予約のリストを組み立てて関数を呼ぶだけで書ける。
"""

from datetime import datetime, time, timedelta

from .models import Reservation, Room

# 営業時間。この外側にかかる予約は受け付けない。
BUSINESS_START = time(9, 0)
BUSINESS_END = time(20, 0)

# 開始のこれだけ前を過ぎたらキャンセル不可。
CANCEL_DEADLINE = timedelta(hours=1)


class BookingError(ValueError):
    """業務ルール違反。API 層はこれを 400 に変換する。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """2つの時間帯が重なるか。

    境界は重なりとみなさない。前の予約の終了時刻と次の開始時刻が同じ
    （10:00-11:00 と 11:00-12:00）のは連続利用であって二重予約ではない。
    """
    return a_start < b_end and b_start < a_end


def validate_reservation(
    room: Room,
    start: datetime,
    end: datetime,
    attendees: int,
    existing: list[Reservation],
) -> None:
    """予約を作ってよいか検証する。だめなら BookingError を投げる。

    ``existing`` には同じ会議室の既存予約だけを渡すこと。
    """
    if end <= start:
        raise BookingError("invalid_range", "終了時刻は開始時刻より後にしてください")

    if start.date() != end.date():
        raise BookingError("cross_day", "日をまたぐ予約はできません")

    if attendees < 1:
        raise BookingError("invalid_attendees", "参加人数は1人以上にしてください")

    if attendees > room.capacity:
        raise BookingError(
            "over_capacity",
            f"参加人数 {attendees} 名は「{room.name}」の定員 {room.capacity} 名を超えています",
        )

    if start.time() < BUSINESS_START or end.time() > BUSINESS_END:
        raise BookingError(
            "outside_business_hours",
            f"予約できるのは {BUSINESS_START:%H:%M}〜{BUSINESS_END:%H:%M} の間だけです",
        )

    for other in existing:
        if overlaps(start, end, other.start, other.end):
            raise BookingError(
                "overlap",
                f"「{room.name}」は {other.start:%H:%M}〜{other.end:%H:%M} に"
                f"「{other.title}」の予約が入っています",
            )


def cancel_deadline(reservation: Reservation) -> datetime:
    """この時刻を過ぎるとキャンセルできない。"""
    return reservation.start - CANCEL_DEADLINE


def validate_cancel(reservation: Reservation, now: datetime) -> None:
    """キャンセルしてよいか検証する。だめなら BookingError を投げる。"""
    if now > cancel_deadline(reservation):
        raise BookingError(
            "too_late_to_cancel",
            f"開始 {CANCEL_DEADLINE.seconds // 3600} 時間前を過ぎた予約はキャンセルできません",
        )
