from pathlib import Path
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parent.parent

ZIP_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "SoftwareRequirements"
    / "Dataset.zip"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "SoftwareRequirements"
    / "extracted"
)


def extract_dataset():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        archive.extractall(OUTPUT_DIR)

    print("Dataset extracted successfully.")
    print(f"Location: {OUTPUT_DIR}")


if __name__ == "__main__":
    extract_dataset()