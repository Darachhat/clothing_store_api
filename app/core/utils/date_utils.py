from datetime import datetime
import zoneinfo
from app.core.constants import DATETIME_FORMAT, DEFAULT_TIMEZONE


def get_current_time(timezone: str = DEFAULT_TIMEZONE) -> datetime:
    tz = zoneinfo.ZoneInfo(timezone)
    return datetime.now(tz)


def format_datetime(dt: datetime, fmt: str = DATETIME_FORMAT) -> str:
    return dt.strftime(fmt)

