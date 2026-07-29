"""Motor de cálculo de asistencias y horas por sector."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import time
from typing import Any

PUNCH_RE = re.compile(r"(\d{1,2}):(\d{2})")

# Horarios contractuales por sector (minutos desde medianoche / duración esperada)
SECTOR_SCHEDULE: dict[str, dict[str, Any]] = {
    "administracion": {
        "label": "Administración",
        "start": time(8, 0),
        "end": time(16, 0),
        "expected_hours": 8.0,
        "fixed": True,
    },
    "ventas": {
        "label": "Ventas",
        "start": time(8, 0),
        "end": time(14, 0),
        "expected_hours": 6.0,
        "fixed": True,
    },
    "produccion": {
        "label": "Producción",
        "start": time(8, 0),
        "end": time(17, 0),
        "expected_hours": 9.0,
        "fixed": True,
    },
    "maestranza": {
        "label": "Maestranza",
        "start": None,
        "end": None,
        "expected_hours": None,
        "fixed": False,
    },
}


def normalize_department(raw: str) -> str:
    key = (
        (raw or "")
        .strip()
        .lower()
        .replace("ó", "o")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ú", "u")
    )
    aliases = {
        "administracion": "administracion",
        "admin": "administracion",
        "ventas": "ventas",
        "produccion": "produccion",
        "production": "produccion",
        "maestranza": "maestranza",
    }
    return aliases.get(key, key)


def parse_punches(cell: str) -> list[time]:
    """Extrae marcas HH:MM de una celda concatenada tipo '08:0916:18'."""
    if cell is None:
        return []
    text = str(cell).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []
    punches: list[time] = []
    for match in PUNCH_RE.finditer(text):
        hour = int(match.group(1))
        minute = int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            punches.append(time(hour, minute))
    return punches


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def hours_between(start: time, end: time) -> float:
    start_m = _time_to_minutes(start)
    end_m = _time_to_minutes(end)
    if end_m < start_m:
        end_m += 24 * 60
    return round((end_m - start_m) / 60.0, 2)


@dataclass
class DayRecord:
    day: int
    punches: list[str]
    entry: str | None = None
    exit: str | None = None
    hours: float | None = None
    status: str = "sin_marca"
    late_minutes: int | None = None
    overtime_hours: float | None = None
    missing_hours: float | None = None


@dataclass
class EmployeeRecord:
    employee_id: str
    name: str
    department: str
    department_key: str
    period: str
    days: dict[int, DayRecord] = field(default_factory=dict)


def analyze_day(punches: list[time], department_key: str) -> DayRecord:
    schedule = SECTOR_SCHEDULE.get(department_key, SECTOR_SCHEDULE["maestranza"])
    punch_strs = [p.strftime("%H:%M") for p in punches]

    if not punches:
        return DayRecord(day=0, punches=[], status="ausente")

    entry = punches[0]
    if len(punches) == 1:
        late = None
        if schedule["fixed"] and schedule["start"]:
            late = max(0, _time_to_minutes(entry) - _time_to_minutes(schedule["start"]))
        return DayRecord(
            day=0,
            punches=punch_strs,
            entry=entry.strftime("%H:%M"),
            exit=None,
            hours=None,
            status="incompleto",
            late_minutes=late if late and late > 0 else None,
        )

    exit_t = punches[-1]
    worked = hours_between(entry, exit_t)
    late = None
    overtime = None
    missing = None
    status = "completo"

    if schedule["fixed"] and schedule["start"] and schedule["expected_hours"] is not None:
        late_val = _time_to_minutes(entry) - _time_to_minutes(schedule["start"])
        if late_val > 0:
            late = late_val
            status = "tarde"
        expected = float(schedule["expected_hours"])
        diff = round(worked - expected, 2)
        if diff > 0.15:
            overtime = diff
        elif diff < -0.15:
            missing = abs(diff)
            if status == "completo":
                status = "faltante"
    else:
        status = "horas_reales"

    return DayRecord(
        day=0,
        punches=punch_strs,
        entry=entry.strftime("%H:%M"),
        exit=exit_t.strftime("%H:%M"),
        hours=worked,
        status=status,
        late_minutes=late,
        overtime_hours=overtime,
        missing_hours=missing,
    )


def summarize_employee(emp: EmployeeRecord) -> dict[str, Any]:
    schedule = SECTOR_SCHEDULE.get(emp.department_key, SECTOR_SCHEDULE["maestranza"])
    complete_days = [d for d in emp.days.values() if d.hours is not None]
    incomplete = [d for d in emp.days.values() if d.status == "incompleto"]
    absentish = [d for d in emp.days.values() if d.status in {"ausente", "sin_marca"}]
    late_days = [d for d in emp.days.values() if d.late_minutes and d.late_minutes > 0]

    total_hours = round(sum(d.hours or 0 for d in complete_days), 2)
    overtime = round(sum(d.overtime_hours or 0 for d in complete_days), 2)
    missing = round(sum(d.missing_hours or 0 for d in complete_days), 2)
    avg = round(total_hours / len(complete_days), 2) if complete_days else 0.0

    return {
        "employee_id": emp.employee_id,
        "name": emp.name,
        "department": schedule["label"] if emp.department_key in SECTOR_SCHEDULE else emp.department,
        "period": emp.period,
        "days_with_complete_marks": len(complete_days),
        "days_incomplete": len(incomplete),
        "days_with_any_mark": len([d for d in emp.days.values() if d.punches]),
        "late_days": len(late_days),
        "total_hours": total_hours,
        "average_hours_per_complete_day": avg,
        "overtime_hours": overtime if schedule["fixed"] else None,
        "missing_hours": missing if schedule["fixed"] else None,
        "expected_daily_hours": schedule["expected_hours"],
        "fixed_schedule": schedule["fixed"],
    }


def day_to_dict(day: int, record: DayRecord) -> dict[str, Any]:
    return {
        "day": day,
        "punches": record.punches,
        "entry": record.entry,
        "exit": record.exit,
        "hours": record.hours,
        "status": record.status,
        "late_minutes": record.late_minutes,
        "overtime_hours": record.overtime_hours,
        "missing_hours": record.missing_hours,
    }
