import csv
from config import REQUIRED_COLUMNS

def load_centroid_file(csv_path):
    components = []

    with open(csv_path, newline="", encoding="utf-8", errors="ignore") as file:
        reader = csv.DictReader(file)

        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        for row in reader:
            components.append({
                "designator": row["Designator"],
                "x": float(row["X"]),
                "y": float(row["Y"]),
                "rotation": float(row["Rotation"]),
            })

    return components
