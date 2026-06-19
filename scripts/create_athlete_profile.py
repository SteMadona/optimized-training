from __future__ import annotations

from csv import DictReader, DictWriter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "data" / "manual" / "athlete_profile.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

METRICS_FILE = OUTPUT_DIR / "athlete_metrics.csv"
HR_ZONES_FILE = OUTPUT_DIR / "hr_zones.csv"

REQUIRED_KEYS = [
    "age",
    "height",
    "bodyweight",
    "estimated_max_hr",
    "bench_1rm",
    "weighted_pullup_1rm",
    "squat_1rm",
    "sumo_deadlift_1rm",
]

METRICS_COLUMNS = ["metric", "value", "unit", "category"]
HR_ZONES_COLUMNS = ["zone", "name", "min_pct", "max_pct", "min_bpm", "max_bpm", "range_bpm"]


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


def read_profile() -> dict[str, dict[str, object]]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"File non trovato: {INPUT_FILE}")

    with INPUT_FILE.open(newline="", encoding="utf-8-sig") as handle:
        reader = DictReader(handle)
        rows = list(reader)
        columns = reader.fieldnames or []

    required_columns = {"key", "value", "unit"}
    missing_columns = required_columns - set(columns)

    if missing_columns:
        raise ValueError(f"Colonne mancanti in athlete_profile.csv: {missing_columns}")

    profile: dict[str, dict[str, object]] = {}

    for row in rows:
        key = str(row.get("key", "")).strip()
        value = row.get("value")
        unit = str(row.get("unit", "")).strip()

        parsed_value = parse_float(value)
        profile[key] = {"value": parsed_value if parsed_value is not None else value, "unit": unit}

    missing_keys = [key for key in REQUIRED_KEYS if key not in profile]
    if missing_keys:
        raise ValueError(f"Chiavi mancanti in athlete_profile.csv: {missing_keys}")

    return profile


def get_value(profile: dict[str, dict[str, object]], key: str) -> float:
    return float(profile[key]["value"])


def build_athlete_metrics(profile: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    age = get_value(profile, "age")
    height_cm = get_value(profile, "height")
    bodyweight = get_value(profile, "bodyweight")
    estimated_max_hr = get_value(profile, "estimated_max_hr")

    bench_1rm = get_value(profile, "bench_1rm")
    weighted_pullup_1rm = get_value(profile, "weighted_pullup_1rm")
    squat_1rm = get_value(profile, "squat_1rm")
    sumo_deadlift_1rm = get_value(profile, "sumo_deadlift_1rm")

    height_m = height_cm / 100
    bmi = bodyweight / (height_m**2)
    pullup_total_load = bodyweight + weighted_pullup_1rm

    return [
        {"metric": "Età", "value": round(age, 2), "unit": "anni", "category": "Profilo"},
        {"metric": "Altezza", "value": round(height_cm, 2), "unit": "cm", "category": "Profilo"},
        {"metric": "Peso corporeo", "value": round(bodyweight, 2), "unit": "kg", "category": "Profilo"},
        {"metric": "BMI", "value": round(bmi, 2), "unit": "", "category": "Composizione corporea"},
        {"metric": "FC max stimata", "value": round(estimated_max_hr, 2), "unit": "bpm", "category": "Cardio"},
        {"metric": "Panca 1RM", "value": round(bench_1rm, 2), "unit": "kg", "category": "Forza"},
        {"metric": "Panca / peso corporeo", "value": round(bench_1rm / bodyweight, 2), "unit": "xBW", "category": "Forza relativa"},
        {"metric": "Trazione zavorrata 1RM", "value": round(weighted_pullup_1rm, 2), "unit": "kg esterni", "category": "Forza"},
        {"metric": "Trazione carico totale", "value": round(pullup_total_load, 2), "unit": "kg", "category": "Forza"},
        {"metric": "Trazione carico totale / peso corporeo", "value": round(pullup_total_load / bodyweight, 2), "unit": "xBW", "category": "Forza relativa"},
        {"metric": "Squat 1RM", "value": round(squat_1rm, 2), "unit": "kg", "category": "Forza - storico"},
        {"metric": "Squat / peso corporeo", "value": round(squat_1rm / bodyweight, 2), "unit": "xBW", "category": "Forza relativa - storico"},
        {"metric": "Stacco sumo 1RM", "value": round(sumo_deadlift_1rm, 2), "unit": "kg", "category": "Forza - storico"},
        {"metric": "Stacco sumo / peso corporeo", "value": round(sumo_deadlift_1rm / bodyweight, 2), "unit": "xBW", "category": "Forza relativa - storico"},
    ]


def build_hr_zones(profile: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    max_hr = get_value(profile, "estimated_max_hr")

    zones = [
        {"zone": "Z1", "name": "Recupero", "min_pct": 0.50, "max_pct": 0.60},
        {"zone": "Z2", "name": "Aerobica facile", "min_pct": 0.60, "max_pct": 0.70},
        {"zone": "Z3", "name": "Aerobica media", "min_pct": 0.70, "max_pct": 0.80},
        {"zone": "Z4", "name": "Soglia", "min_pct": 0.80, "max_pct": 0.90},
        {"zone": "Z5", "name": "VO2max", "min_pct": 0.90, "max_pct": 1.00},
    ]

    rows: list[dict[str, object]] = []
    for zone in zones:
        min_bpm = round(zone["min_pct"] * max_hr)
        max_bpm = round(zone["max_pct"] * max_hr)
        rows.append(
            {
                "zone": zone["zone"],
                "name": zone["name"],
                "min_pct": zone["min_pct"],
                "max_pct": zone["max_pct"],
                "min_bpm": int(min_bpm),
                "max_bpm": int(max_bpm),
                "range_bpm": f"{int(min_bpm)}-{int(max_bpm)}",
            }
        )

    return rows


def write_csv_rows(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    profile = read_profile()
    athlete_metrics = build_athlete_metrics(profile)
    hr_zones = build_hr_zones(profile)

    write_csv_rows(METRICS_FILE, athlete_metrics, METRICS_COLUMNS)
    write_csv_rows(HR_ZONES_FILE, hr_zones, HR_ZONES_COLUMNS)

    print(f"Creato: {METRICS_FILE}")
    print(f"Creato: {HR_ZONES_FILE}")


if __name__ == "__main__":
    main()
