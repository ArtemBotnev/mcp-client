import re
from dataclasses import dataclass
from datetime import datetime, timedelta


LAST_NUMBERED_PERIOD_RE = re.compile(
    r"(?:за\s+)?последн(?:ие|их|ий|юю|ее)\s+(\d+)\s+"
    r"(минут(?:у|ы)?|час(?:а|ов)?|д(?:ень|ня|ней)|сут(?:ки|ок)|"
    r"недел(?:ю|и|ь)|месяц(?:а|ев)?|год(?:а|ов)?)",
)


@dataclass(frozen=True)
class TimeInterval:
    label: str
    start: datetime
    end: datetime

    @property
    def start_iso(self) -> str:
        return self.start.isoformat(timespec="seconds")

    @property
    def end_iso(self) -> str:
        return self.end.isoformat(timespec="seconds")


def with_normalized_time_context(user_message: str, *, now: datetime | None = None) -> str:
    current_time = now or datetime.now().astimezone()
    interval = find_time_interval(user_message, now=current_time)
    if interval is None:
        return user_message

    return (
        f"{user_message}\n\n"
        "[Контекст клиента]\n"
        f"Текущая дата и время: {current_time.isoformat(timespec='seconds')}.\n"
        "Пользователь указал период человеческим языком. "
        f"Нормализованный интервал: {interval.label}; "
        f"from={interval.start_iso}; to={interval.end_iso}.\n"
        "Если нужен отчет за период, используй эти значения для ISO-8601 полей from/to, "
        "а при сохранении отчета также для reportFrom/reportTo."
    )


def find_time_interval(text: str, *, now: datetime) -> TimeInterval | None:
    normalized = _normalize_text(text)

    numbered_period = _find_last_numbered_period(normalized, now)
    if numbered_period is not None:
        return numbered_period

    today_start = _start_of_day(now)
    yesterday_start = today_start - timedelta(days=1)

    if _contains_any(normalized, ("сегодня", "текущий день", "этот день", "за день")):
        return TimeInterval("сегодня", today_start, now)

    if "позавчера" in normalized:
        return TimeInterval("позавчера", today_start - timedelta(days=2), yesterday_start)

    if _contains_any(normalized, ("вчера", "прошлый день")):
        return TimeInterval("вчера", yesterday_start, today_start)

    if _contains_any(
        normalized,
        ("последние сутки", "последних суток", "последний день", "за сутки"),
    ):
        return TimeInterval("последние сутки", now - timedelta(days=1), now)

    week_start = today_start - timedelta(days=today_start.weekday())
    if _contains_any(
        normalized,
        ("эта неделя", "эту неделю", "текущая неделя", "текущую неделю"),
    ):
        return TimeInterval("текущая неделя", week_start, now)

    if _contains_any(
        normalized,
        (
            "прошлая неделя",
            "прошлую неделю",
            "прошедшая неделя",
            "прошедшую неделю",
            "предыдущая неделя",
            "предыдущую неделю",
        ),
    ):
        previous_week_start = week_start - timedelta(days=7)
        return TimeInterval("прошлая неделя", previous_week_start, week_start)

    if _contains_any(normalized, ("за неделю", "последняя неделя", "последнюю неделю")):
        return TimeInterval("последние 7 дней", now - timedelta(days=7), now)

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if _contains_any(normalized, ("этот месяц", "текущий месяц")):
        return TimeInterval("текущий месяц", month_start, now)

    if _contains_any(normalized, ("прошлый месяц", "прошедший месяц", "предыдущий месяц")):
        previous_month_start = _add_months(month_start, -1)
        return TimeInterval("прошлый месяц", previous_month_start, month_start)

    if _contains_any(normalized, ("за месяц", "последний месяц")):
        return TimeInterval("последний месяц", _add_months(now, -1), now)

    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if _contains_any(normalized, ("этот год", "текущий год")):
        return TimeInterval("текущий год", year_start, now)

    if _contains_any(normalized, ("прошлый год", "прошедший год", "предыдущий год")):
        previous_year_start = year_start.replace(year=year_start.year - 1)
        return TimeInterval("прошлый год", previous_year_start, year_start)

    if _contains_any(normalized, ("за год", "последний год")):
        return TimeInterval("последний год", _add_months(now, -12), now)

    return None


def _find_last_numbered_period(text: str, now: datetime) -> TimeInterval | None:
    match = LAST_NUMBERED_PERIOD_RE.search(text)
    if match is None:
        return None

    count = int(match.group(1))
    unit = match.group(2)
    if count <= 0:
        return None

    if unit.startswith("минут"):
        start = now - timedelta(minutes=count)
    elif unit.startswith("час"):
        start = now - timedelta(hours=count)
    elif unit.startswith(("д", "сут")):
        start = now - timedelta(days=count)
    elif unit.startswith("недел"):
        start = now - timedelta(weeks=count)
    elif unit.startswith("месяц"):
        start = _add_months(now, -count)
    elif unit.startswith("год"):
        start = _add_months(now, -12 * count)
    else:
        return None

    return TimeInterval(f"последние {count} {unit}", start, now)


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _start_of_day(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return value.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day
