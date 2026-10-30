import json
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
import zoneinfo

try:
    from loguru import logger as _loguru_logger
    _HAS_LOGURU = True
except ImportError:
    _loguru_logger = None
    _HAS_LOGURU    = False

from app.core.config import settings
from app.core.constants import DEFAULT_TIMEZONE

DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


class INTERCEPT_HANDLER(logging.Handler):
    """
    Intercept standard logging records and redirect them to Loguru.
    """
    def emit(self, record: logging.LogRecord) -> None:
        if not _HAS_LOGURU or _loguru_logger is None:
            return
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        if record.name == "uvicorn.access" and len(record.args) >= 5:
            try:
                _, method, path, http_version, status = record.args[:5]
                message = f'"{method} {path} HTTP/{http_version}" {status}'
                _loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, message)
                return
            except Exception:
                pass

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class TRACE_LOGGER:
    """
    Dedicated structured JSON-lines trace logger writing to logs/trace.log.
    Modeled after templete_api's TRACE_LOGGER.
    """
    def __init__(self, log_dir: Path) -> None:
        self.log_dir    = log_dir
        self.trace_file = self.log_dir / "trace.log"

    def write(self, record: Dict[str, Any]) -> None:
        if not settings.ENABLE_TRACE_LOG:
            return
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, default=str, ensure_ascii=False)
            with open(self.trace_file, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception:
            pass


def setup_logging():
    log_dir     = Path("logs")
    archive_dir = log_dir / "archived"
    log_dir.mkdir(exist_ok=True)
    archive_dir.mkdir(exist_ok=True)

    component = settings.COMPONENT_NAME

    if not _HAS_LOGURU or _loguru_logger is None:
        std_logger = logging.getLogger(component)
        std_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
        if not std_logger.handlers:
            formatter   = logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S")
            stream_hdlr = logging.StreamHandler(sys.stdout)
            stream_hdlr.setFormatter(formatter)
            file_hdlr   = logging.FileHandler(log_dir / "app.log", encoding="utf-8", delay=True)
            file_hdlr.setFormatter(formatter)
            std_logger.addHandler(stream_hdlr)
            std_logger.addHandler(file_hdlr)
        return std_logger

    logging.root.handlers = []

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    _loguru_logger.remove()
    _loguru_logger.add(
        sys.stdout
        , format   = log_format
        , colorize = True
        , diagnose = False
        , catch    = True
    )

    _loguru_logger.add(
        log_dir / f"{component}.log"
        , format    = log_format
        , level     = "DEBUG"
        , catch     = True
        , backtrace = True
        , colorize  = False
        , enqueue   = False
        , rotation  = "10 MB"
        , retention = "14 days"
    )

    _loguru_logger.add(
        log_dir / "app.log"
        , format    = log_format
        , level     = settings.LOG_LEVEL
        , catch     = True
        , backtrace = True
        , colorize  = False
        , enqueue   = False
    )

    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(INTERCEPT_HANDLER())

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvi_logger           = logging.getLogger(name)
        uvi_logger.handlers  = [INTERCEPT_HANDLER()]
        uvi_logger.propagate = False

    return _loguru_logger


def _extract_line_date(line: str) -> str:
    """
    Extract YYYY-MM-DD date from either a standard log line or a JSON trace log line.
    Returns empty string if no date can be parsed.
    """
    stripped = line.strip()
    if not stripped:
        return ""
    match = DATE_PREFIX_RE.match(stripped)
    if match:
        return match.group(1)
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped)
            ts = str(payload.get("timestamp") or payload.get("datetime") or "")
            m = DATE_PREFIX_RE.match(ts)
            if m:
                return m.group(1)
        except Exception:
            pass
    return ""


def rotate_logs(
    log_dir          : Path = Path("logs")
    , retention_days : int  = settings.LOG_RETENTION_DAYS
) -> Dict[str, Any]:
    """
    Archive log lines from dates prior to today into logs/archived/YYYY-MM-DD-{log_type}.log
    and purge archived files older than retention_days.
    """
    tz          = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)
    today_str   = datetime.now(tz).strftime("%Y-%m-%d")
    cutoff_date = (datetime.now(tz) - timedelta(days=retention_days)).strftime("%Y-%m-%d")

    archive_dir = log_dir / "archived"
    log_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_files   : List[str] = []
    archived_lines   : int       = 0
    deleted_archives : List[str] = []

    target_files = [
        ("app", log_dir / "app.log")
        , ("process", log_dir / "process.log")
        , ("trace", log_dir / "trace.log")
        , (settings.COMPONENT_NAME, log_dir / f"{settings.COMPONENT_NAME}.log")
    ]

    seen_paths = set()
    for log_type, file_path in target_files:
        resolved = str(file_path.resolve())
        if resolved in seen_paths or not file_path.exists():
            continue
        seen_paths.add(resolved)

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except Exception:
            continue

        if not lines:
            continue

        buckets      : Dict[str, List[str]] = {}
        remain_lines : List[str]            = []
        current_date : str                  = today_str

        for line in lines:
            line_date = _extract_line_date(line)
            if line_date:
                current_date = line_date

            if current_date < today_str:
                buckets.setdefault(current_date, []).append(line)
            else:
                remain_lines.append(line)

        for archive_date, date_lines in buckets.items():
            archive_file = archive_dir / f"{archive_date}-{log_type}.log"
            try:
                with open(archive_file, "a", encoding="utf-8") as af:
                    af.writelines(date_lines)
                archived_lines += len(date_lines)
                if archive_file.name not in archived_files:
                    archived_files.append(archive_file.name)
            except Exception:
                pass

        if buckets:
            try:
                with open(file_path, "w", encoding="utf-8") as fh:
                    fh.writelines(remain_lines)
            except Exception:
                pass

    for arch_file in archive_dir.glob("*.log"):
        match = DATE_PREFIX_RE.match(arch_file.name)
        if match and match.group(1) < cutoff_date:
            try:
                arch_file.unlink()
                deleted_archives.append(arch_file.name)
            except Exception:
                pass

    return {
        "date"               : today_str
        , "archived_files"   : archived_files
        , "archived_lines"   : archived_lines
        , "deleted_archives" : deleted_archives
    }


logger       = setup_logging()
trace_logger = TRACE_LOGGER(Path("logs"))

