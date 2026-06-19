from pathlib import Path
import pandas as pd


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


def read_profile() -> dict:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"File non trovato: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE)

    required_columns = {"key", "value", "unit"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Colonne mancanti in athlete_profile.csv: {missing_columns}")

    profile = {}

    for _, row in df.iterrows():
        key = str(row["key"]).strip()
        value = row["value"]
        unit = str(row["unit"]).strip()

        try:
            value = float(value)
        except ValueError:
            pass

        profile[key] = {
            "value": value,
            "unit": unit,
        }

    missing_keys = [key for key in REQUIRED_KEYS if key not in profile]

    if missing_keys:
        raise ValueError(f"Chiavi mancanti in athlete_profile.csv: {missing_keys}")

    return profile


def get_value(profile: dict, key: str) -> float:
    return float(profile[key]["value"])


def build_athlete_metrics(profile: dict) -> pd.DataFrame:
    age = get_value(profile, "age")
    height_cm = get_value(profile, "height")
    bodyweight = get_value(profile, "bodyweight")
    estimated_max_hr = get_value(profile, "estimated_max_hr")

    bench_1rm = get_value(profile, "bench_1rm")
    weighted_pullup_1rm = get_value(profile, "weighted_pullup_1rm")
    squat_1rm = get_value(profile, "squat_1rm")
    sumo_deadlift_1rm = get_value(profile, "sumo_deadlift_1rm")

    height_m = height_cm / 100
    bmi = bodyweight / (height_m ** 2)

    pullup_total_load = bodyweight + weighted_pullup_1rm

    metrics = [
        {
            "metric": "Età",
            "value": age,
            "unit": "anni",
            "category": "Profilo",
        },
        {
            "metric": "Altezza",
            "value": height_cm,
            "unit": "cm",
            "category": "Profilo",
        },
        {
            "metric": "Peso corporeo",
            "value": bodyweight,
            "unit": "kg",
            "category": "Profilo",
        },
        {
            "metric": "BMI",
            "value": bmi,
            "unit": "",
            "category": "Composizione corporea",
        },
        {
            "metric": "FC max stimata",
            "value": estimated_max_hr,
            "unit": "bpm",
            "category": "Cardio",
        },
        {
            "metric": "Panca 1RM",
            "value": bench_1rm,
            "unit": "kg",
            "category": "Forza",
        },
        {
            "metric": "Panca / peso corporeo",
            "value": bench_1rm / bodyweight,
            "unit": "xBW",
            "category": "Forza relativa",
        },
        {
            "metric": "Trazione zavorrata 1RM",
            "value": weighted_pullup_1rm,
            "unit": "kg esterni",
            "category": "Forza",
        },
        {
            "metric": "Trazione carico totale",
            "value": pullup_total_load,
            "unit": "kg",
            "category": "Forza",
        },
        {
            "metric": "Trazione carico totale / peso corporeo",
            "value": pullup_total_load / bodyweight,
            "unit": "xBW",
            "category": "Forza relativa",
        },
        {
            "metric": "Squat 1RM",
            "value": squat_1rm,
            "unit": "kg",
            "category": "Forza - storico",
        },
        {
            "metric": "Squat / peso corporeo",
            "value": squat_1rm / bodyweight,
            "unit": "xBW",
            "category": "Forza relativa - storico",
        },
        {
            "metric": "Stacco sumo 1RM",
            "value": sumo_deadlift_1rm,
            "unit": "kg",
            "category": "Forza - storico",
        },
        {
            "metric": "Stacco sumo / peso corporeo",
            "value": sumo_deadlift_1rm / bodyweight,
            "unit": "xBW",
            "category": "Forza relativa - storico",
        },
    ]

    df = pd.DataFrame(metrics)

    df["value"] = df["value"].round(2)

    return df


def build_hr_zones(profile: dict) -> pd.DataFrame:
    max_hr = get_value(profile, "estimated_max_hr")

    zones = [
        {
            "zone": "Z1",
            "name": "Recupero",
            "min_pct": 0.50,
            "max_pct": 0.60,
        },
        {
            "zone": "Z2",
            "name": "Aerobica facile",
            "min_pct": 0.60,
            "max_pct": 0.70,
        },
        {
            "zone": "Z3",
            "name": "Aerobica media",
            "min_pct": 0.70,
            "max_pct": 0.80,
        },
        {
            "zone": "Z4",
            "name": "Soglia",
            "min_pct": 0.80,
            "max_pct": 0.90,
        },
        {
            "zone": "Z5",
            "name": "VO2max",
            "min_pct": 0.90,
            "max_pct": 1.00,
        },
    ]

    df = pd.DataFrame(zones)

    df["min_bpm"] = (df["min_pct"] * max_hr).round(0).astype(int)
    df["max_bpm"] = (df["max_pct"] * max_hr).round(0).astype(int)

    df["range_bpm"] = df["min_bpm"].astype(str) + "–" + df["max_bpm"].astype(str)

    return df


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    profile = read_profile()

    athlete_metrics = build_athlete_metrics(profile)
    hr_zones = build_hr_zones(profile)

    athlete_metrics.to_csv(METRICS_FILE, index=False)
    hr_zones.to_csv(HR_ZONES_FILE, index=False)

    print(f"Creato: {METRICS_FILE}")
    print(f"Creato: {HR_ZONES_FILE}")


if __name__ == "__main__":
    main()