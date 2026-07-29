"""Lectura y parseo de la planilla de asistencias (sin pandas)."""

from __future__ import annotations

import csv
import io
import re
from threading import Lock
from typing import Any

import httpx

from app.config import get_settings
from app.services.attendance_calc import (
    DayRecord,
    EmployeeRecord,
    analyze_day,
    day_to_dict,
    normalize_department,
    parse_punches,
    summarize_employee,
)

_cache_lock = Lock()
_employees: list[EmployeeRecord] = []
_period: str = ""
_loaded: bool = False


def _export_urls(sheet_id: str) -> list[str]:
    return [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv",
    ]


def _fetch_csv(sheet_id: str) -> str:
    last_error: Exception | None = None
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FabricaAsistencias/1.0)"}
    with httpx.Client(follow_redirects=True, timeout=30.0, headers=headers) as client:
        for url in _export_urls(sheet_id):
            try:
                resp = client.get(url)
                if resp.status_code == 200 and resp.text.strip():
                    if "<html" in resp.text[:200].lower():
                        last_error = RuntimeError(
                            "La planilla no es pública. Compartila con 'Cualquiera con el enlace'."
                        )
                        continue
                    return resp.text
                last_error = RuntimeError(f"HTTP {resp.status_code} al leer la planilla")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
    raise RuntimeError(str(last_error) if last_error else "No se pudo leer la planilla")


def _read_rows(csv_text: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(csv_text))
    return [[(c or "").strip() for c in row] for row in reader]


def _find_header_row(rows: list[list[str]]) -> int:
    for idx in range(min(15, len(rows))):
        joined = " ".join(rows[idx]).lower()
        if "employee" in joined and "name" in joined:
            return idx
        if "employee id" in joined or ("nombre" in joined and "departamento" in joined):
            return idx
    return 4


def _extract_period(rows: list[list[str]]) -> str:
    for row in rows[:8]:
        for val in row:
            match = re.search(r"(\d{4}/\d{2}/\d{2})\s*-\s*(\d{4}/\d{2}/\d{2})", val)
            if match:
                return f"{match.group(1)}-{match.group(2)}"
            match2 = re.search(r"Made Date:(.+)", val, re.I)
            if match2:
                return match2.group(1).strip()
    return "periodo desconocido"


def _parse_dataframe(csv_text: str) -> tuple[list[EmployeeRecord], str]:
    rows = _read_rows(csv_text)
    if not rows:
        return [], "periodo desconocido"

    header_idx = _find_header_row(rows)
    period = _extract_period(rows)
    header = rows[header_idx]
    body = rows[header_idx + 1 :]

    day_cols: dict[int, int] = {}
    for col_idx, name in enumerate(header):
        if re.fullmatch(r"\d{1,2}", str(name).strip()):
            day_cols[int(str(name).strip())] = col_idx

    if not day_cols:
        for col_idx in range(3, len(header)):
            day_cols[col_idx - 2] = col_idx

    employees: list[EmployeeRecord] = []
    for row in body:
        if len(row) < 3:
            continue
        emp_id = row[0].strip()
        name = row[1].strip()
        dept = row[2].strip()
        if not emp_id or not name or not re.match(r"^\d+$", emp_id):
            continue

        dept_key = normalize_department(dept)
        emp = EmployeeRecord(
            employee_id=emp_id,
            name=name,
            department=dept,
            department_key=dept_key,
            period=period,
        )
        for day, col_idx in sorted(day_cols.items()):
            cell = row[col_idx].strip() if col_idx < len(row) else ""
            punches = parse_punches(cell)
            analyzed = analyze_day(punches, dept_key)
            analyzed.day = day
            if punches or cell:
                emp.days[day] = analyzed
            else:
                emp.days[day] = DayRecord(day=day, punches=[], status="sin_marca")
        employees.append(emp)

    return employees, period


def refresh_sheet() -> dict[str, Any]:
    global _employees, _period, _loaded
    settings = get_settings()
    csv_text = _fetch_csv(settings.google_sheet_id)
    employees, period = _parse_dataframe(csv_text)
    with _cache_lock:
        _employees = employees
        _period = period
        _loaded = True
    return {
        "ok": True,
        "period": period,
        "employee_count": len(employees),
        "employees": [
            {"id": e.employee_id, "name": e.name, "department": e.department} for e in employees
        ],
    }


def ensure_loaded() -> None:
    global _loaded
    if not _loaded:
        refresh_sheet()


def get_employees() -> list[EmployeeRecord]:
    ensure_loaded()
    with _cache_lock:
        return list(_employees)


def get_period() -> str:
    ensure_loaded()
    with _cache_lock:
        return _period


def find_employee(query: str) -> EmployeeRecord | None:
    ensure_loaded()
    q = (query or "").strip().lower()
    if not q:
        return None
    with _cache_lock:
        for emp in _employees:
            if emp.employee_id == q:
                return emp
        for emp in _employees:
            if emp.name.lower() == q:
                return emp
        matches = [emp for emp in _employees if q in emp.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if matches:
            starts = [emp for emp in matches if emp.name.lower().startswith(q)]
            return starts[0] if starts else matches[0]
    return None


def list_employees_tool() -> dict[str, Any]:
    employees = get_employees()
    return {
        "period": get_period(),
        "employees": [
            {"id": e.employee_id, "name": e.name, "department": e.department} for e in employees
        ],
    }


def get_attendance_tool(
    employee_query: str, day_from: int | None = None, day_to: int | None = None
) -> dict[str, Any]:
    emp = find_employee(employee_query)
    if not emp:
        return {"error": f"No encontré a nadie que coincida con '{employee_query}'."}

    days = []
    for day, record in sorted(emp.days.items()):
        if day_from is not None and day < day_from:
            continue
        if day_to is not None and day > day_to:
            continue
        if record.punches or record.status not in {"sin_marca"}:
            days.append(day_to_dict(day, record))

    return {
        "employee_id": emp.employee_id,
        "name": emp.name,
        "department": emp.department,
        "period": emp.period,
        "days": days,
        "summary": summarize_employee(emp),
    }


def calculate_hours_tool(
    employee_query: str, day_from: int | None = None, day_to: int | None = None
) -> dict[str, Any]:
    emp = find_employee(employee_query)
    if not emp:
        return {"error": f"No encontré a nadie que coincida con '{employee_query}'."}

    if day_from is not None or day_to is not None:
        filtered = EmployeeRecord(
            employee_id=emp.employee_id,
            name=emp.name,
            department=emp.department,
            department_key=emp.department_key,
            period=emp.period,
            days={
                d: r
                for d, r in emp.days.items()
                if (day_from is None or d >= day_from) and (day_to is None or d <= day_to)
            },
        )
        summary = summarize_employee(filtered)
        detail = [
            day_to_dict(d, r)
            for d, r in sorted(filtered.days.items())
            if r.hours is not None or r.status == "incompleto"
        ]
        return {"summary": summary, "detail": detail}

    return {"summary": summarize_employee(emp)}


def summarize_department_tool(department: str) -> dict[str, Any]:
    key = normalize_department(department)
    employees = [e for e in get_employees() if e.department_key == key]
    if not employees:
        employees = [
            e for e in get_employees() if key in e.department_key or key in e.department.lower()
        ]
    if not employees:
        return {"error": f"No hay gente en el sector '{department}'."}

    people = [summarize_employee(e) for e in employees]
    total_hours = round(sum(p["total_hours"] for p in people), 2)
    return {
        "department": department,
        "period": get_period(),
        "employee_count": len(people),
        "total_hours": total_hours,
        "people": people,
    }


def refresh_sheet_tool() -> dict[str, Any]:
    return refresh_sheet()
