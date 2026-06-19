from __future__ import annotations

from collections import Counter
from csv import DictReader, DictWriter
from datetime import datetime, timedelta
from hashlib import md5
from pathlib import Path
import csv
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]

HEVY_FILE = PROJECT_ROOT / "data" / "raw" / "hevy" / "workouts.csv"
ATHLETE_PROFILE_FILE = PROJECT_ROOT / "data" / "manual" / "athlete_profile.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

STRENGTH_SETS_FILE = OUTPUT_DIR / "strength_sets.csv"
STRENGTH_WORKOUTS_FILE = OUTPUT_DIR / "strength_workouts.csv"
STRENGTH_WEEKLY_FILE = OUTPUT_DIR / "strength_weekly.csv"
STRENGTH_PRS_FILE = OUTPUT_DIR / "strength_prs.csv"


ITALIAN_MONTHS = {
    "gen": "Jan",
    "gennaio": "Jan",
    "feb": "Feb",
    "febbraio": "Feb",
    "mar": "Mar",
    "marzo": "Mar",
    "apr": "Apr",
    "aprile": "Apr",
    "mag": "May",
    "maggio": "May",
    "giu": "Jun",
    "giugno": "Jun",
    "lug": "Jul",
    "luglio": "Jul",
    "ago": "Aug",
    "agosto": "Aug",
    "set": "Sep",
    "sett": "Sep",
    "settembre": "Sep",
    "ott": "Oct",
    "ottobre": "Oct",
    "nov": "Nov",
    "novembre": "Nov",
    "dic": "Dec",
    "dicembre": "Dec",
}

TARGET_PATTERNS = {
    "bench_press": ["bench press", "panca"],
    "weighted_pullup": ["pull up", "chin up", "weighted pull", "trazione"],
    "power_clean": ["power clean"],
    "squat": ["squat"],
    "deadlift": ["deadlift", "stacco"],
}

SET_COLUMNS = [
    "set_id",
    "workout_id",
    "date",
    "week",
    "title",
    "start_datetime",
    "end_datetime",
    "exercise_title",
    "exercise_category",
    "set_index",
    "set_type",
    "is_warmup",
    "is_working_set",
    "weight_kg",
    "reps",
    "volume_kg",
    "bodyweight_kg",
    "is_weighted_pullup",
    "external_load_kg",
    "total_load_kg",
    "e1rm_kg",
    "total_e1rm_kg",
    "external_e1rm_kg",
    "distance_km",
    "duration_seconds",
    "rpe",
    "exercise_notes",
]

WORKOUT_COLUMNS = [
    "workout_id",
    "date",
    "week",
    "title",
    "start_datetime",
    "end_datetime",
    "duration_min",
    "total_sets",
    "working_sets",
    "exercises",
    "total_volume_kg",
]

WEEKLY_COLUMNS = [
    "week",
    "workouts",
    "duration_min",
    "total_sets",
    "total_volume_kg",
    "bench_sets",
    "pullup_sets",
    "power_clean_sets",
]

PR_COLUMNS = [
    "exercise_category",
    "pr_type",
    "date",
    "exercise_title",
    "weight_kg",
    "reps",
    "e1rm_kg",
    "total_load_kg",
    "total_e1rm_kg",
]


def normalize_datetime_text(value: str) -> str:
    text = str(value).strip().lower()
    text = text.replace(",", "")
    text = re.sub(r"\s+", " ", text)

    for ita, eng in ITALIAN_MONTHS.items():
        text = re.sub(rf"\b{ita}\b", eng, text)

    return text


def parse_hevy_datetime(value: str) -> datetime:
    normalized = normalize_datetime_text(value)

    for pattern in ("%d %b %Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Data Hevy non valida: {value!r}") from exc


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


def parse_int(value: object) -> int | None:
    number = parse_float(value)
    if number is None:
        return None
    return int(number)


def as_csv_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def as_csv_date(value: datetime) -> str:
    return value.date().isoformat()


def as_week_label(value: datetime) -> str:
    week_start = value.date() - timedelta(days=value.weekday())
    week_end = week_start + timedelta(days=6)
    return f"{week_start.isoformat()}/{week_end.isoformat()}"


def format_number(value: object, digits: int | None = None) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "True" if value else "False"

    if isinstance(value, datetime):
        return as_csv_datetime(value)

    if hasattr(value, "isoformat") and not isinstance(value, (int, float, str)):
        return value.isoformat()

    if isinstance(value, (int, float)) and digits is not None:
        return f"{value:.{digits}f}"

    return str(value)


def write_csv_rows(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            output_row = {column: format_number(row.get(column)) for column in columns}
            writer.writerow(output_row)


def read_hevy_export() -> list[dict[str, str]]:
    if not HEVY_FILE.exists():
        raise FileNotFoundError(
            f"File non trovato: {HEVY_FILE}\n"
            "Metti l'export Hevy in data/raw/hevy/workouts.csv"
        )

    with HEVY_FILE.open(newline="", encoding="utf-8-sig") as handle:
        reader = DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []

    expected_columns = {
        "title",
        "start_time",
        "end_time",
        "exercise_title",
        "set_index",
        "set_type",
        "weight_kg",
        "reps",
        "distance_km",
        "duration_seconds",
        "rpe",
    }

    missing_columns = expected_columns - set(columns)

    if missing_columns:
        raise ValueError(f"Colonne mancanti nell'export Hevy: {missing_columns}")

    return rows


def read_current_bodyweight() -> float:
    if not ATHLETE_PROFILE_FILE.exists():
        return 85.1

    with ATHLETE_PROFILE_FILE.open(newline="", encoding="utf-8-sig") as handle:
        reader = DictReader(handle)
        for row in reader:
            if str(row.get("key", "")).strip() == "bodyweight":
                bodyweight = parse_float(row.get("value"))
                if bodyweight is not None:
                    return bodyweight

    return 85.1


def classify_exercise(exercise_title: str) -> str:
    name = str(exercise_title).lower()

    for category, patterns in TARGET_PATTERNS.items():
        if any(pattern in name for pattern in patterns):
            return category

    return "other"


def is_weighted_pullup(exercise_category: str, exercise_title: str) -> bool:
    name = str(exercise_title).lower()

    if exercise_category == "weighted_pullup":
        return True

    return any(term in name for term in ["pull up", "chin up", "trazione"])


def estimate_1rm(weight: float | None, reps: float | None) -> float | None:
    if weight is None or reps is None:
        return None

    if weight <= 0 or reps <= 0:
        return None

    if reps > 12:
        return None

    return weight * (1 + reps / 30)


def make_workout_id(title: str, start_time: str, end_time: str) -> str:
    raw = f"{title}|{start_time}|{end_time}"
    return md5(raw.encode("utf-8")).hexdigest()[:12]


def build_strength_sets(raw_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    bodyweight = read_current_bodyweight()
    rows: list[dict[str, object]] = []

    for raw in raw_rows:
        title = str(raw.get("title", "")).strip()
        start_time_text = str(raw.get("start_time", "")).strip()
        end_time_text = str(raw.get("end_time", "")).strip()
        exercise_title = str(raw.get("exercise_title", "")).strip()
        set_type = str(raw.get("set_type", "normal")).strip().lower() or "normal"
        exercise_category = classify_exercise(exercise_title)
        start_datetime = parse_hevy_datetime(start_time_text)
        end_datetime = parse_hevy_datetime(end_time_text)
        workout_id = make_workout_id(title, start_time_text, end_time_text)

        set_index = parse_int(raw.get("set_index"))
        weight_kg = parse_float(raw.get("weight_kg"))
        reps = parse_float(raw.get("reps"))
        distance_km = parse_float(raw.get("distance_km"))
        duration_seconds = parse_float(raw.get("duration_seconds"))
        rpe = parse_float(raw.get("rpe"))
        exercise_notes = str(raw.get("exercise_notes", "")).strip()

        is_warmup = "warm" in set_type
        is_working_set = not is_warmup
        volume_kg = (weight_kg or 0) * (reps or 0)
        is_weighted = is_weighted_pullup(exercise_category, exercise_title)
        external_load_kg = weight_kg
        total_load_kg = weight_kg

        if is_weighted and weight_kg is not None:
            total_load_kg = weight_kg + bodyweight

        e1rm_kg = estimate_1rm(weight_kg, reps)
        total_e1rm_kg = estimate_1rm(total_load_kg, reps)
        external_e1rm_kg = e1rm_kg

        if is_weighted and total_e1rm_kg is not None:
            external_e1rm_kg = total_e1rm_kg - bodyweight

        set_slug = re.sub(r"[^a-z0-9]+", "_", exercise_title.lower()).strip("_")
        set_id = f"{workout_id}_{set_slug}_{set_index or 0}"

        rows.append(
            {
                "set_id": set_id,
                "workout_id": workout_id,
                "date": as_csv_date(start_datetime),
                "week": as_week_label(start_datetime),
                "title": title,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
                "exercise_title": exercise_title,
                "exercise_category": exercise_category,
                "set_index": set_index if set_index is not None else 0,
                "set_type": set_type,
                "is_warmup": is_warmup,
                "is_working_set": is_working_set,
                "weight_kg": weight_kg,
                "reps": reps,
                "volume_kg": volume_kg,
                "bodyweight_kg": bodyweight,
                "is_weighted_pullup": is_weighted,
                "external_load_kg": external_load_kg,
                "total_load_kg": total_load_kg,
                "e1rm_kg": e1rm_kg,
                "total_e1rm_kg": total_e1rm_kg,
                "external_e1rm_kg": external_e1rm_kg,
                "distance_km": distance_km,
                "duration_seconds": duration_seconds,
                "rpe": rpe,
                "exercise_notes": exercise_notes,
            }
        )

    rows.sort(key=lambda row: (row["start_datetime"], row["exercise_title"], row["set_index"]))
    return rows


def build_strength_workouts(sets: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}

    for row in sets:
        workout_id = str(row["workout_id"])
        if workout_id not in grouped:
            grouped[workout_id] = {
                "workout_id": workout_id,
                "date": row["date"],
                "week": row["week"],
                "title": row["title"],
                "start_datetime": row["start_datetime"],
                "end_datetime": row["end_datetime"],
                "total_sets": 0,
                "working_sets": 0,
                "exercises_set": set(),
                "total_volume_kg": 0.0,
            }

        grouped_row = grouped[workout_id]
        grouped_row["total_sets"] += 1
        grouped_row["working_sets"] += 1 if row["is_working_set"] else 0
        grouped_row["exercises_set"].add(row["exercise_title"])
        grouped_row["total_volume_kg"] += float(row["volume_kg"] or 0)

    workouts: list[dict[str, object]] = []
    for workout in grouped.values():
        workouts.append(
            {
                "workout_id": workout["workout_id"],
                "date": workout["date"],
                "week": workout["week"],
                "title": workout["title"],
                "start_datetime": workout["start_datetime"],
                "end_datetime": workout["end_datetime"],
                "duration_min": round(
                    (workout["end_datetime"] - workout["start_datetime"]).total_seconds() / 60,
                    1,
                ),
                "total_sets": workout["total_sets"],
                "working_sets": workout["working_sets"],
                "exercises": len(workout["exercises_set"]),
                "total_volume_kg": round(workout["total_volume_kg"], 1),
            }
        )

    workouts.sort(key=lambda row: row["start_datetime"])
    return workouts


def build_strength_weekly(sets: list[dict[str, object]], workouts: list[dict[str, object]]) -> list[dict[str, object]]:
    working_sets = [row for row in sets if row["is_working_set"]]

    weekly_sets: dict[str, dict[str, object]] = {}
    for row in working_sets:
        week = str(row["week"])
        if week not in weekly_sets:
            weekly_sets[week] = {
                "week": week,
                "total_sets": 0,
                "total_volume_kg": 0.0,
                "bench_sets": 0,
                "pullup_sets": 0,
                "power_clean_sets": 0,
            }

        bucket = weekly_sets[week]
        bucket["total_sets"] += 1
        bucket["total_volume_kg"] += float(row["volume_kg"] or 0)
        if row["exercise_category"] == "bench_press":
            bucket["bench_sets"] += 1
        if row["exercise_category"] == "weighted_pullup":
            bucket["pullup_sets"] += 1
        if row["exercise_category"] == "power_clean":
            bucket["power_clean_sets"] += 1

    weekly_workouts: dict[str, dict[str, object]] = {}
    for row in workouts:
        week = str(row["week"])
        if week not in weekly_workouts:
            weekly_workouts[week] = {"week": week, "workouts": 0, "duration_min": 0.0}

        bucket = weekly_workouts[week]
        bucket["workouts"] += 1
        bucket["duration_min"] += float(row["duration_min"] or 0)

    weeks = sorted(set(weekly_sets) | set(weekly_workouts))
    rows: list[dict[str, object]] = []

    for week in weeks:
        row = {
            "week": week,
            "workouts": 0,
            "duration_min": 0.0,
            "total_sets": 0,
            "total_volume_kg": 0.0,
            "bench_sets": 0,
            "pullup_sets": 0,
            "power_clean_sets": 0,
        }

        if week in weekly_workouts:
            row.update(weekly_workouts[week])
        if week in weekly_sets:
            row.update(weekly_sets[week])

        row["duration_min"] = round(float(row["duration_min"] or 0), 1)
        row["total_volume_kg"] = round(float(row["total_volume_kg"] or 0), 1)
        rows.append(row)

    rows.sort(key=lambda row: row["week"])
    return rows


def build_strength_prs(sets: list[dict[str, object]]) -> list[dict[str, object]]:
    working = [
        row
        for row in sets
        if row["is_working_set"]
        and row["weight_kg"] is not None
        and row["reps"] is not None
        and row["reps"] > 0
    ]

    prs: list[dict[str, object]] = []
    target_categories = ["bench_press", "weighted_pullup", "power_clean", "squat", "deadlift"]

    for category in target_categories:
        subset = [row for row in working if row["exercise_category"] == category]
        if not subset:
            continue

        if category == "weighted_pullup":
            load_col = "external_load_kg"
            e1rm_col = "external_e1rm_kg"
            total_col = "total_load_kg"
            total_e1rm_col = "total_e1rm_kg"
        else:
            load_col = "weight_kg"
            e1rm_col = "e1rm_kg"
            total_col = "weight_kg"
            total_e1rm_col = "e1rm_kg"

        max_load_row = sorted(subset, key=lambda row: (row[load_col], row["reps"]), reverse=True)[0]
        prs.append(
            {
                "exercise_category": category,
                "pr_type": "max_load",
                "date": max_load_row["date"],
                "exercise_title": max_load_row["exercise_title"],
                "weight_kg": round(float(max_load_row[load_col]), 2),
                "reps": int(max_load_row["reps"]),
                "e1rm_kg": round(float(max_load_row[e1rm_col]), 2) if max_load_row[e1rm_col] is not None else None,
                "total_load_kg": round(float(max_load_row[total_col]), 2) if max_load_row[total_col] is not None else None,
                "total_e1rm_kg": round(float(max_load_row[total_e1rm_col]), 2) if max_load_row[total_e1rm_col] is not None else None,
            }
        )

        e1rm_subset = [row for row in subset if row[e1rm_col] is not None]
        if e1rm_subset:
            e1rm_row = sorted(e1rm_subset, key=lambda row: row[e1rm_col], reverse=True)[0]
            prs.append(
                {
                    "exercise_category": category,
                    "pr_type": "best_e1rm",
                    "date": e1rm_row["date"],
                    "exercise_title": e1rm_row["exercise_title"],
                    "weight_kg": round(float(e1rm_row[load_col]), 2),
                    "reps": int(e1rm_row["reps"]),
                    "e1rm_kg": round(float(e1rm_row[e1rm_col]), 2),
                    "total_load_kg": round(float(e1rm_row[total_col]), 2) if e1rm_row[total_col] is not None else None,
                    "total_e1rm_kg": round(float(e1rm_row[total_e1rm_col]), 2) if e1rm_row[total_e1rm_col] is not None else None,
                }
            )

    return prs


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_rows = read_hevy_export()
    strength_sets = build_strength_sets(raw_rows)
    strength_workouts = build_strength_workouts(strength_sets)
    strength_weekly = build_strength_weekly(strength_sets, strength_workouts)
    strength_prs = build_strength_prs(strength_sets)

    write_csv_rows(STRENGTH_SETS_FILE, strength_sets, SET_COLUMNS)
    write_csv_rows(STRENGTH_WORKOUTS_FILE, strength_workouts, WORKOUT_COLUMNS)
    write_csv_rows(STRENGTH_WEEKLY_FILE, strength_weekly, WEEKLY_COLUMNS)
    write_csv_rows(STRENGTH_PRS_FILE, strength_prs, PR_COLUMNS)

    print(f"Creato: {STRENGTH_SETS_FILE}")
    print(f"Creato: {STRENGTH_WORKOUTS_FILE}")
    print(f"Creato: {STRENGTH_WEEKLY_FILE}")
    print(f"Creato: {STRENGTH_PRS_FILE}")
    print()
    print(f"Set importati: {len(strength_sets)}")
    print(f"Workout importati: {len(strength_workouts)}")
    print()
    print("Categorie esercizi principali:")
    for category, count in Counter(row["exercise_category"] for row in strength_sets).most_common():
        print(f"{category}: {count}")


if __name__ == "__main__":
    main()
