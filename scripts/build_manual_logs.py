from __future__ import annotations

from collections import defaultdict
from csv import DictReader, DictWriter
from datetime import date, datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DAILY_WELLNESS_FILE = PROJECT_ROOT / "data" / "manual" / "daily_welness.csv"
STRETCHING_FILE = PROJECT_ROOT / "data" / "manual" / "stretching.csv"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

MANUAL_SUMMARY_FILE = OUTPUT_DIR / "manual_summary.csv"
STRETCHING_PROCESSED_FILE = OUTPUT_DIR / "stretching_processed.csv"
RED_FLAGS_FILE = OUTPUT_DIR / "red_flags.csv"


DAILY_COLUMNS = ["date", "mental_stress_1_5", "caffeine_mg", "pain_0_10", "pain_area", "notes"]
STRETCHING_COLUMNS = ["date", "duration_min", "focus", "mobility_1_5", "notes"]

SUMMARY_COLUMNS = [
    "date",
    "mental_stress_1_5",
    "caffeine_mg",
    "pain_0_10",
    "pain_area",
    "notes",
    "stretching_sessions",
    "stretching_min",
    "mobility_avg",
    "focus_list",
    "wellness_logged",
    "stretching_done",
]

RED_FLAG_COLUMNS = ["date", "flag", "severity", "detail"]


def parse_float(value: object) -> float | None:
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value: object) -> date | None:
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None

    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue

    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def format_date(value: date | None) -> str:
    return value.isoformat() if value is not None else ""


def read_csv_rows(path: Path, columns: list[str]) -> list[dict[str, object]]:
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = DictReader(handle)
        rows = list(reader)
        available_columns = reader.fieldnames or []

    if not rows:
        return []

    if not set(columns).issubset(set(available_columns)):
        for row in rows:
            for column in columns:
                row.setdefault(column, "")

    return [{column: row.get(column, "") for column in columns} for row in rows]


def clean_daily_wellness(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []

    for row in rows:
        row_date = parse_date(row.get("date"))
        if row_date is None:
            continue

        cleaned.append(
            {
                "date": row_date,
                "mental_stress_1_5": parse_float(row.get("mental_stress_1_5")),
                "caffeine_mg": parse_float(row.get("caffeine_mg")),
                "pain_0_10": parse_float(row.get("pain_0_10")),
                "pain_area": str(row.get("pain_area", "")).strip(),
                "notes": str(row.get("notes", "")).strip(),
            }
        )

    cleaned.sort(key=lambda row: row["date"])
    return cleaned


def clean_stretching(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []

    for row in rows:
        row_date = parse_date(row.get("date"))
        if row_date is None:
            continue

        cleaned.append(
            {
                "date": row_date,
                "duration_min": parse_float(row.get("duration_min")) or 0,
                "focus": str(row.get("focus", "")).strip(),
                "mobility_1_5": parse_float(row.get("mobility_1_5")),
                "notes": str(row.get("notes", "")).strip(),
            }
        )

    cleaned.sort(key=lambda row: row["date"])
    return cleaned


def build_stretching_daily(stretching: list[dict[str, object]]) -> list[dict[str, object]]:
    if not stretching:
        return []

    grouped: dict[date, dict[str, object]] = defaultdict(lambda: {"stretching_sessions": 0, "stretching_min": 0.0, "mobility_values": [], "focus_values": set()})

    for row in stretching:
        bucket = grouped[row["date"]]
        bucket["stretching_sessions"] += 1
        bucket["stretching_min"] += float(row["duration_min"] or 0)
        if row["mobility_1_5"] is not None:
            bucket["mobility_values"].append(float(row["mobility_1_5"]))
        focus = str(row["focus"]).strip()
        if focus:
            bucket["focus_values"].add(focus)

    rows: list[dict[str, object]] = []
    for row_date, bucket in grouped.items():
        mobility_values = bucket["mobility_values"]
        mobility_avg = round(sum(mobility_values) / len(mobility_values), 2) if mobility_values else None
        rows.append(
            {
                "date": row_date,
                "stretching_sessions": bucket["stretching_sessions"],
                "stretching_min": round(float(bucket["stretching_min"]), 2),
                "mobility_avg": mobility_avg,
                "focus_list": ", ".join(sorted(bucket["focus_values"])),
            }
        )

    rows.sort(key=lambda row: row["date"])
    return rows


def build_date_range(daily: list[dict[str, object]], stretching_daily: list[dict[str, object]]) -> list[date]:
    today = date.today()
    default_start = today - timedelta(days=29)

    all_dates = [row["date"] for row in daily] + [row["date"] for row in stretching_daily]
    if all_dates:
        start_date = min(min(all_dates), default_start)
        end_date = max(max(all_dates), today)
    else:
        start_date = default_start
        end_date = today

    dates: list[date] = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)

    return dates


def build_manual_summary(daily: list[dict[str, object]], stretching_daily: list[dict[str, object]]) -> list[dict[str, object]]:
    calendar = build_date_range(daily, stretching_daily)

    daily_by_date = {row["date"]: row for row in daily}
    stretching_by_date = {row["date"]: row for row in stretching_daily}

    summary: list[dict[str, object]] = []

    for row_date in calendar:
        daily_row = daily_by_date.get(row_date, {})
        stretching_row = stretching_by_date.get(row_date, {})

        stretching_sessions = int(stretching_row.get("stretching_sessions", 0) or 0)
        stretching_min = float(stretching_row.get("stretching_min", 0) or 0)
        mobility_avg = stretching_row.get("mobility_avg")
        pain_value = daily_row.get("pain_0_10")
        stress_value = daily_row.get("mental_stress_1_5")

        summary.append(
            {
                "date": row_date,
                "mental_stress_1_5": stress_value,
                "caffeine_mg": daily_row.get("caffeine_mg"),
                "pain_0_10": pain_value,
                "pain_area": daily_row.get("pain_area", ""),
                "notes": daily_row.get("notes", ""),
                "stretching_sessions": stretching_sessions,
                "stretching_min": int(stretching_min) if stretching_min.is_integer() else round(stretching_min, 2),
                "mobility_avg": round(float(mobility_avg), 2) if mobility_avg is not None else None,
                "focus_list": stretching_row.get("focus_list", ""),
                "wellness_logged": stress_value is not None or pain_value is not None,
                "stretching_done": stretching_min > 0,
            }
        )

    return summary


def build_red_flags(summary: list[dict[str, object]]) -> list[dict[str, object]]:
    if not summary:
        return []

    latest = summary[-1]
    latest_date = latest["date"]
    flags: list[dict[str, object]] = []

    mental_stress = latest.get("mental_stress_1_5")
    pain = latest.get("pain_0_10")
    caffeine = latest.get("caffeine_mg")
    mobility = latest.get("mobility_avg")

    if mental_stress is not None:
        if mental_stress >= 5:
            flags.append({"date": latest_date, "flag": "Stress mentale molto alto", "severity": "red", "detail": f"Stress mentale segnato a {mental_stress}/5."})
        elif mental_stress >= 4:
            flags.append({"date": latest_date, "flag": "Stress mentale alto", "severity": "yellow", "detail": f"Stress mentale segnato a {mental_stress}/5."})

    if pain is not None:
        if pain >= 7:
            flags.append({"date": latest_date, "flag": "Dolore alto", "severity": "red", "detail": f"Dolore segnato a {pain}/10."})
        elif pain >= 5:
            flags.append({"date": latest_date, "flag": "Dolore moderato", "severity": "yellow", "detail": f"Dolore segnato a {pain}/10."})

    if caffeine is not None and caffeine >= 400:
        flags.append({"date": latest_date, "flag": "Caffeina alta", "severity": "yellow", "detail": f"Caffeina segnata a {caffeine} mg."})

    recent_4_days = [row for row in summary if row["date"] >= latest_date - timedelta(days=3)]
    stretching_minutes_4_days = sum(float(row.get("stretching_min", 0) or 0) for row in recent_4_days)

    if stretching_minutes_4_days == 0:
        flags.append({"date": latest_date, "flag": "Stretching assente negli ultimi 4 giorni", "severity": "yellow", "detail": "Nessuna seduta di stretching registrata negli ultimi 4 giorni."})

    if mobility is not None and mobility <= 2:
        flags.append({"date": latest_date, "flag": "Mobilità percepita bassa", "severity": "yellow", "detail": f"Mobilità percepita media: {mobility}/5."})

    if not flags:
        flags.append({"date": latest_date, "flag": "Nessuna red flag manuale attiva", "severity": "green", "detail": "Stress, dolore, caffeina e stretching non mostrano criticità manuali evidenti."})

    return flags


def write_csv_rows(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: format_value(row.get(column)) for column in columns})


def format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}" if not value.is_integer() else str(int(value))
    return str(value)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    daily = clean_daily_wellness(read_csv_rows(DAILY_WELLNESS_FILE, DAILY_COLUMNS))
    stretching = clean_stretching(read_csv_rows(STRETCHING_FILE, STRETCHING_COLUMNS))

    stretching_daily = build_stretching_daily(stretching)
    summary = build_manual_summary(daily, stretching_daily)
    red_flags = build_red_flags(summary)

    write_csv_rows(STRETCHING_PROCESSED_FILE, stretching, STRETCHING_COLUMNS)
    write_csv_rows(MANUAL_SUMMARY_FILE, summary, SUMMARY_COLUMNS)
    write_csv_rows(RED_FLAGS_FILE, red_flags, RED_FLAG_COLUMNS)

    print(f"Creato: {MANUAL_SUMMARY_FILE}")
    print(f"Creato: {STRETCHING_PROCESSED_FILE}")
    print(f"Creato: {RED_FLAGS_FILE}")


if __name__ == "__main__":
    main()
