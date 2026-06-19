from pathlib import Path
from datetime import date, timedelta

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DAILY_WELLNESS_FILE = PROJECT_ROOT / "data" / "manual" / "daily_wellness.csv"
STRETCHING_FILE = PROJECT_ROOT / "data" / "manual" / "stretching.csv"

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

MANUAL_SUMMARY_FILE = OUTPUT_DIR / "manual_summary.csv"
STRETCHING_PROCESSED_FILE = OUTPUT_DIR / "stretching_processed.csv"
RED_FLAGS_FILE = OUTPUT_DIR / "red_flags.csv"


DAILY_COLUMNS = [
    "date",
    "mental_stress_1_5",
    "caffeine_mg",
    "pain_0_10",
    "pain_area",
    "notes",
]

STRETCHING_COLUMNS = [
    "date",
    "duration_min",
    "focus",
    "mobility_1_5",
    "notes",
]


def read_csv_safe(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=columns)

    for col in columns:
        if col not in df.columns:
            df[col] = pd.NA

    return df[columns].copy()


def clean_daily_wellness(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=DAILY_COLUMNS)

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])

    numeric_columns = [
        "mental_stress_1_5",
        "caffeine_mg",
        "pain_0_10",
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.sort_values("date")


def clean_stretching(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=STRETCHING_COLUMNS)

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])

    df["duration_min"] = pd.to_numeric(df["duration_min"], errors="coerce").fillna(0)
    df["mobility_1_5"] = pd.to_numeric(df["mobility_1_5"], errors="coerce")

    return df.sort_values("date")


def build_stretching_daily(stretching: pd.DataFrame) -> pd.DataFrame:
    if stretching.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "stretching_sessions",
                "stretching_min",
                "mobility_avg",
                "focus_list",
            ]
        )

    grouped = (
        stretching
        .groupby("date")
        .agg(
            stretching_sessions=("date", "size"),
            stretching_min=("duration_min", "sum"),
            mobility_avg=("mobility_1_5", "mean"),
            focus_list=("focus", lambda x: ", ".join(sorted(set(str(v) for v in x if pd.notna(v))))),
        )
        .reset_index()
    )

    grouped["mobility_avg"] = grouped["mobility_avg"].round(2)

    return grouped


def build_date_range(daily: pd.DataFrame, stretching_daily: pd.DataFrame) -> pd.DataFrame:
    today = date.today()
    default_start = today - timedelta(days=29)

    dates = []

    if not daily.empty:
        dates.extend(daily["date"].dropna().tolist())

    if not stretching_daily.empty:
        dates.extend(stretching_daily["date"].dropna().tolist())

    if dates:
        start_date = min(min(dates), default_start)
        end_date = max(max(dates), today)
    else:
        start_date = default_start
        end_date = today

    calendar = pd.DataFrame({
        "date": pd.date_range(start=start_date, end=end_date, freq="D").date
    })

    return calendar


def build_manual_summary(daily: pd.DataFrame, stretching_daily: pd.DataFrame) -> pd.DataFrame:
    calendar = build_date_range(daily, stretching_daily)

    summary = calendar.merge(daily, on="date", how="left")
    summary = summary.merge(stretching_daily, on="date", how="left")

    summary["stretching_sessions"] = summary["stretching_sessions"].fillna(0).astype(int)
    summary["stretching_min"] = summary["stretching_min"].fillna(0).astype(int)

    summary["mobility_avg"] = summary["mobility_avg"].round(2)

    summary["wellness_logged"] = summary["mental_stress_1_5"].notna() | summary["pain_0_10"].notna()
    summary["stretching_done"] = summary["stretching_min"] > 0

    return summary.sort_values("date")


def build_red_flags(summary: pd.DataFrame) -> pd.DataFrame:
    flags = []

    if summary.empty:
        return pd.DataFrame(columns=["date", "flag", "severity", "detail"])

    latest_date = summary["date"].max()
    latest = summary[summary["date"] == latest_date].iloc[0]

    mental_stress = latest.get("mental_stress_1_5")
    pain = latest.get("pain_0_10")
    caffeine = latest.get("caffeine_mg")
    mobility = latest.get("mobility_avg")

    if pd.notna(mental_stress):
        if mental_stress >= 5:
            flags.append({
                "date": latest_date,
                "flag": "Stress mentale molto alto",
                "severity": "red",
                "detail": f"Stress mentale segnato a {mental_stress}/5.",
            })
        elif mental_stress >= 4:
            flags.append({
                "date": latest_date,
                "flag": "Stress mentale alto",
                "severity": "yellow",
                "detail": f"Stress mentale segnato a {mental_stress}/5.",
            })

    if pd.notna(pain):
        if pain >= 7:
            flags.append({
                "date": latest_date,
                "flag": "Dolore alto",
                "severity": "red",
                "detail": f"Dolore segnato a {pain}/10.",
            })
        elif pain >= 5:
            flags.append({
                "date": latest_date,
                "flag": "Dolore moderato",
                "severity": "yellow",
                "detail": f"Dolore segnato a {pain}/10.",
            })

    if pd.notna(caffeine) and caffeine >= 400:
        flags.append({
            "date": latest_date,
            "flag": "Caffeina alta",
            "severity": "yellow",
            "detail": f"Caffeina segnata a {caffeine} mg.",
        })

    recent_4_days = summary[summary["date"] >= latest_date - timedelta(days=3)]
    stretching_minutes_4_days = recent_4_days["stretching_min"].sum()

    if stretching_minutes_4_days == 0:
        flags.append({
            "date": latest_date,
            "flag": "Stretching assente negli ultimi 4 giorni",
            "severity": "yellow",
            "detail": "Nessuna seduta di stretching registrata negli ultimi 4 giorni.",
        })

    if pd.notna(mobility) and mobility <= 2:
        flags.append({
            "date": latest_date,
            "flag": "Mobilità percepita bassa",
            "severity": "yellow",
            "detail": f"Mobilità percepita media: {mobility}/5.",
        })

    if not flags:
        flags.append({
            "date": latest_date,
            "flag": "Nessuna red flag manuale attiva",
            "severity": "green",
            "detail": "Stress, dolore, caffeina e stretching non mostrano criticità manuali evidenti.",
        })

    return pd.DataFrame(flags)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    daily = read_csv_safe(DAILY_WELLNESS_FILE, DAILY_COLUMNS)
    stretching = read_csv_safe(STRETCHING_FILE, STRETCHING_COLUMNS)

    daily = clean_daily_wellness(daily)
    stretching = clean_stretching(stretching)

    stretching_daily = build_stretching_daily(stretching)
    summary = build_manual_summary(daily, stretching_daily)
    red_flags = build_red_flags(summary)

    stretching.to_csv(STRETCHING_PROCESSED_FILE, index=False)
    summary.to_csv(MANUAL_SUMMARY_FILE, index=False)
    red_flags.to_csv(RED_FLAGS_FILE, index=False)

    print(f"Creato: {MANUAL_SUMMARY_FILE}")
    print(f"Creato: {STRETCHING_PROCESSED_FILE}")
    print(f"Creato: {RED_FLAGS_FILE}")


if __name__ == "__main__":
    main()