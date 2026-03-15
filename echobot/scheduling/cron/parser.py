from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .types import CronSchedule


def normalize_schedule(schedule: CronSchedule) -> CronSchedule:
    if schedule.kind == "at":
        if not schedule.at:
            raise ValueError("at schedule requires 'at'")
        _parse_datetime(schedule.at)
        return schedule

    if schedule.kind == "every":
        if schedule.every_seconds is None or schedule.every_seconds <= 0:
            raise ValueError("every schedule requires every_seconds > 0")
        return schedule

    if schedule.kind != "cron":
        raise ValueError(f"Unsupported schedule kind: {schedule.kind}")

    if not schedule.expr:
        raise ValueError("cron schedule requires expr")
    if len(schedule.expr.split()) != 5:
        raise ValueError("cron expression must have 5 fields")
    if schedule.timezone:
        _read_timezone(schedule.timezone)
    _CronExpression.parse(schedule.expr)
    return schedule


def compute_next_run(
    schedule: CronSchedule,
    *,
    now: datetime | None = None,
) -> datetime | None:
    now = _ensure_aware(now or datetime.now().astimezone())
    normalized = normalize_schedule(schedule)
    if normalized.kind == "at":
        at_value = _parse_datetime(normalized.at or "")
        return at_value if at_value > now else None

    if normalized.kind == "every":
        return now + timedelta(seconds=normalized.every_seconds or 0)

    timezone = (
        _read_timezone(normalized.timezone)
        if normalized.timezone
        else now.tzinfo
    )
    assert timezone is not None
    cron = _CronExpression.parse(normalized.expr or "")
    candidate = now.astimezone(timezone).replace(second=0, microsecond=0)
    candidate += timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        if cron.matches(candidate):
            return candidate
        candidate += timedelta(minutes=1)
    return None


def describe_schedule(schedule: CronSchedule) -> str:
    if schedule.kind == "at":
        return f"at {schedule.at}"
    if schedule.kind == "every":
        return f"every {schedule.every_seconds}s"
    timezone = f" ({schedule.timezone})" if schedule.timezone else ""
    return f"cron {schedule.expr}{timezone}"


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value
    return value.astimezone()


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return _ensure_aware(parsed)


def _read_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


@dataclass(slots=True)
class _CronExpression:
    minute: set[int]
    hour: set[int]
    day_of_month_any: bool
    day_of_month: set[int]
    month: set[int]
    day_of_week_any: bool
    day_of_week: set[int]

    @classmethod
    def parse(cls, expr: str) -> "_CronExpression":
        minute, hour, day_of_month, month, day_of_week = expr.split()
        return cls(
            minute=_parse_field(minute, 0, 59),
            hour=_parse_field(hour, 0, 23),
            day_of_month_any=day_of_month == "*",
            day_of_month=_parse_field(day_of_month, 1, 31),
            month=_parse_field(month, 1, 12),
            day_of_week_any=day_of_week == "*",
            day_of_week=_parse_field(day_of_week, 0, 7, normalize_weekday=True),
        )

    def matches(self, candidate: datetime) -> bool:
        cron_weekday = (candidate.weekday() + 1) % 7
        day_of_month_match = candidate.day in self.day_of_month
        day_of_week_match = cron_weekday in self.day_of_week
        if self.day_of_month_any and self.day_of_week_any:
            day_match = True
        elif self.day_of_month_any:
            day_match = day_of_week_match
        elif self.day_of_week_any:
            day_match = day_of_month_match
        else:
            day_match = day_of_month_match or day_of_week_match
        return (
            candidate.minute in self.minute
            and candidate.hour in self.hour
            and candidate.month in self.month
            and day_match
        )


def _parse_field(
    raw_value: str,
    minimum: int,
    maximum: int,
    *,
    normalize_weekday: bool = False,
) -> set[int]:
    values: set[int] = set()
    for chunk in raw_value.split(","):
        values.update(
            _parse_chunk(
                chunk.strip(),
                minimum,
                maximum,
                normalize_weekday=normalize_weekday,
            )
        )
    if not values:
        raise ValueError(f"Invalid cron field: {raw_value}")
    return values


def _parse_chunk(
    chunk: str,
    minimum: int,
    maximum: int,
    *,
    normalize_weekday: bool,
) -> set[int]:
    if chunk == "*":
        return {
            _normalize_weekday(value) if normalize_weekday else value
            for value in range(minimum, maximum + 1)
        }

    base, _, step_text = chunk.partition("/")
    step = int(step_text) if step_text else 1
    if step <= 0:
        raise ValueError("Cron step must be positive")

    if base == "*":
        start = minimum
        end = maximum
    elif "-" in base:
        start_text, end_text = base.split("-", maxsplit=1)
        start = int(start_text)
        end = int(end_text)
    else:
        value = _normalize_field_value(
            int(base),
            minimum,
            maximum,
            normalize_weekday=normalize_weekday,
        )
        return {value}

    if start > end:
        raise ValueError(f"Invalid cron range: {chunk}")

    values: set[int] = set()
    for value in range(start, end + 1, step):
        values.add(
            _normalize_field_value(
                value,
                minimum,
                maximum,
                normalize_weekday=normalize_weekday,
            )
        )
    return values


def _normalize_field_value(
    value: int,
    minimum: int,
    maximum: int,
    *,
    normalize_weekday: bool,
) -> int:
    normalized = _normalize_weekday(value) if normalize_weekday else value
    if normalized < minimum or normalized > maximum:
        raise ValueError(f"Value {value} outside range {minimum}-{maximum}")
    return normalized


def _normalize_weekday(value: int) -> int:
    if value == 7:
        return 0
    return value
