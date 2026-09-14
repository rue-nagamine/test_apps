"""予約ロジックの単体テスト。重複・定員・営業時間・境界値。

ストレージを介さず booking.validate_reservation を直接叩く。
"""

from datetime import datetime, timedelta

import pytest

from app import booking
from app.booking import BookingError
from app.models import Reservation, Room

ROOM = Room(id=1, name="第1会議室", capacity=6)


def at(hour: int, minute: int = 0) -> datetime:
    """テスト用の固定日（2026-04-01）の時刻。"""
    return datetime(2026, 4, 1, hour, minute)


def existing(start: datetime, end: datetime, room_id: int = 1) -> Reservation:
    return Reservation(
        id=1, room_id=room_id, title="既存の定例会", start=start, end=end, attendees=3
    )


def test_rejects_overlapping_reservation():
    """10:00-11:00 が埋まっているところへ 10:30-11:30 は入れられない。"""
    with pytest.raises(BookingError) as exc:
        booking.validate_reservation(
            ROOM, at(10, 30), at(11, 30), 3, [existing(at(10), at(11))]
        )
    assert exc.value.code == "overlap"


def test_allows_back_to_back_reservation():
    """境界: 前の予約の終了時刻 = 次の開始時刻は重複ではない。"""
    booking.validate_reservation(ROOM, at(11), at(12), 3, [existing(at(10), at(11))])


def test_rejects_over_capacity():
    """定員 6 名の部屋に 7 名は入れない。"""
    with pytest.raises(BookingError) as exc:
        booking.validate_reservation(ROOM, at(10), at(11), 7, [])
    assert exc.value.code == "over_capacity"


def test_allows_exact_capacity():
    """境界: 定員ちょうどは予約できる。"""
    booking.validate_reservation(ROOM, at(10), at(11), ROOM.capacity, [])


def test_rejects_outside_business_hours():
    """営業時間 9:00-20:00 をはみ出す予約は前後どちらも不可。"""
    with pytest.raises(BookingError) as before:
        booking.validate_reservation(ROOM, at(8, 30), at(9, 30), 3, [])
    assert before.value.code == "outside_business_hours"

    with pytest.raises(BookingError) as after:
        booking.validate_reservation(ROOM, at(19, 30), at(20, 30), 3, [])
    assert after.value.code == "outside_business_hours"


def test_allows_reservation_ending_at_closing_time():
    """境界: 終了時刻が営業終了ちょうど（20:00）なら予約できる。"""
    booking.validate_reservation(ROOM, at(19), at(20), 3, [])


# 台帳は classname / name の中から項目 ID を拾って auto_ref なしでも突合する。
# 関数名に続けて _TC_RSV_009 と書くと単語境界が立たず拾われないので、
# pytest のパラメータ ID として付ける（JUnit XML の name が
# "test_rejects_non_positive_duration[TC-RSV-009]" になる）。
@pytest.mark.parametrize("case_id", ["TC-RSV-009"])
def test_rejects_non_positive_duration(case_id):
    """end <= start は不正。同時刻も逆転も弾く。"""
    with pytest.raises(BookingError) as same:
        booking.validate_reservation(ROOM, at(10), at(10), 3, [])
    assert same.value.code == "invalid_range"

    with pytest.raises(BookingError):
        booking.validate_reservation(ROOM, at(11), at(10), 3, [])


def test_rejects_reservation_longer_than_four_hours():
    """長時間の占有を防ぐため 4 時間を超える予約は受け付けない。

    ※ この上限はまだ booking.py に実装されていない。意図的に失敗させて、
       台帳側で fail がどう出るかを確認するためのテスト。
    """
    with pytest.raises(BookingError):
        booking.validate_reservation(ROOM, at(10), at(15), 3, [])


@pytest.mark.skip(reason="仕様確認中")
def test_allows_same_slot_in_different_room():
    """別の会議室なら同じ時間帯でも予約できる。"""
    other = Room(id=2, name="第2会議室", capacity=4)
    booking.validate_reservation(other, at(10), at(11), 3, [])


def test_rejects_cancel_after_deadline():
    """開始 1 時間前を過ぎたキャンセルは不可。

    テスト項目側に対応する ID を置いていないので、台帳では
    「紐づかなかった結果」として出るはず。
    """
    start = datetime(2026, 4, 1, 14, 0)
    reservation = existing(start, start + timedelta(hours=1))

    booking.validate_cancel(reservation, start - timedelta(minutes=61))

    with pytest.raises(BookingError) as exc:
        booking.validate_cancel(reservation, start - timedelta(minutes=59))
    assert exc.value.code == "too_late_to_cancel"
