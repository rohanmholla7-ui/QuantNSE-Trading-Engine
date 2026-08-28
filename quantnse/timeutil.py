from __future__ import annotations

from datetime import datetime, time

from quantnse.config import IST, get_settings


def now_ist() -> datetime:
    return datetime.now(tz=IST)


def is_time_between(t: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end


def session_bucket_5m(ts: datetime) -> str:
    local = ts.astimezone(IST)
    minute = (local.minute // 5) * 5
    return local.strftime("%H:") + f"{minute:02d}"


def in_entry_window(ts: datetime | None = None) -> bool:
    settings = get_settings()
    t = (ts or now_ist()).astimezone(IST).time()
    return settings.entry_start <= t <= settings.entry_end


def past_square_off(ts: datetime | None = None) -> bool:
    settings = get_settings()
    t = (ts or now_ist()).astimezone(IST).time()
    return t >= settings.square_off


def in_funnel_window(ts: datetime | None = None) -> bool:
    settings = get_settings()
    t = (ts or now_ist()).astimezone(IST).time()
    return settings.session_open <= t < settings.funnel_end


def to_ist(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=IST)
    return ts.astimezone(IST)
