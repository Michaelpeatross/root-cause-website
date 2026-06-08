"""Central Time for Root Cause reports (Baton Rouge area, 70809)."""
from datetime import datetime
from zoneinfo import ZoneInfo

CENTRAL_TZ = ZoneInfo('America/Chicago')


def central_now():
    return datetime.now(CENTRAL_TZ)


def central_tz_label(dt=None):
    dt = dt or central_now()
    return dt.tzname() or 'CT'


def format_report_datetime(dt=None):
    """e.g. June 07, 2026 at 10:50 PM CDT"""
    dt = dt or central_now()
    return f"{dt.strftime('%B %d, %Y at %I:%M %p')} {central_tz_label(dt)}"


def format_report_date(dt=None):
    """e.g. June 07, 2026"""
    dt = dt or central_now()
    return dt.strftime('%B %d, %Y')


def format_report_stamp(dt=None):
    """Compact stamp for database fields: 2026-06-07 22:50"""
    dt = dt or central_now()
    return dt.strftime('%Y-%m-%d %H:%M')


def format_scan_date(dt=None):
    """Short date for scan cover lines: 06/07/2026"""
    dt = dt or central_now()
    return dt.strftime('%m/%d/%Y')