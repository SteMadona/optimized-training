from collections import Counter
import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEVY_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "hevy"


def inspect_csv(path: Path) -> None:
    print("=" * 90)
    print(f"FILE: {path.name}")
    print("=" * 90)

    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = reader.fieldnames or []
    except UnicodeDecodeError:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = reader.fieldnames or []

    if not columns:
        print("File CSV senza intestazioni riconoscibili.")
        print()
        return

    print(f"Righe: {len(rows)}")
    print(f"Colonne: {len(columns)}")
    print()

    print("COLONNE:")
    for col in columns:
        print(f"- {col}")

    print()
    print("TIPI DATI (inferiti):")
    for col in columns:
        values = [row.get(col, "") for row in rows if str(row.get(col, "")).strip()]
        inferred_type = infer_column_type(values)
        print(f"- {col}: {inferred_type}")

    print()
    print("VALORI NON NULL PER COLONNA:")
    for col in columns:
        non_null_count = sum(1 for row in rows if str(row.get(col, "")).strip() != "")
        print(f"- {col}: {non_null_count}")

    print()
    print("PRIME 3 RIGHE:")
    for index, row in enumerate(rows[:3], start=1):
        print(f"Riga {index}:")
        for col in columns:
            print(f"  {col}: {row.get(col, '')}")
        print()

    print()


def infer_column_type(values: list[str]) -> str:
    if not values:
        return "empty"

    type_counts = Counter(infer_value_type(value) for value in values)

    if len(type_counts) == 1:
        return next(iter(type_counts))

    if set(type_counts).issubset({"int", "float"}):
        return "float"

    if set(type_counts).issubset({"bool", "int"}):
        return "bool"

    return "mixed"


def infer_value_type(value: str) -> str:
    stripped = value.strip()

    if stripped == "":
        return "empty"

    lowered = stripped.lower()
    if lowered in {"true", "false", "yes", "no"}:
        return "bool"

    try:
        int(stripped)
    except ValueError:
        pass
    else:
        return "int"

    try:
        float(stripped)
    except ValueError:
        return "text"

    return "float"


def main() -> None:
    if not HEVY_RAW_DIR.exists():
        raise FileNotFoundError(
            f"Cartella non trovata: {HEVY_RAW_DIR}\n"
            "Crea data/raw/hevy e mettici dentro l'export CSV di Hevy."
        )

    csv_files = sorted(HEVY_RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"Nessun CSV trovato in: {HEVY_RAW_DIR}\n"
            "Metti qui dentro i file esportati da Hevy."
        )

    for csv_file in csv_files:
        inspect_csv(csv_file)


if __name__ == "__main__":
    main()