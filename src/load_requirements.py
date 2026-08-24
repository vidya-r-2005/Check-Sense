from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "SoftwareRequirements"
    / "extracted"
)


def load_raw_requirements():

    records = []

    for raw_file in DATASET_DIR.rglob("_Raw.txt"):

        try:

            text = raw_file.read_text(
                encoding="utf-8",
                errors="ignore"
            )

            project_name = raw_file.parent.name

            records.append({
                "project": project_name,
                "file": raw_file.name,
                "path": str(raw_file),
                "text": text
            })

        except Exception as e:

            print(f"Error reading {raw_file}: {e}")

    return pd.DataFrame(records)


if __name__ == "__main__":

    df = load_raw_requirements()

    print("\nNumber of projects loaded:", len(df))

    print("\nColumns:")
    print(df.columns.tolist())

    print("\nFirst projects:")
    print(df["project"].head())

    print("\nFirst requirement text:")
    print(df.iloc[0]["text"][:2000])