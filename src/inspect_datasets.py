from pathlib import Path
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PURE_ZIP = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "PURE"
    / "requirements.zip"
)

SECOND_ZIP = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "SoftwareRequirements"
    / "Dataset.zip"
)


def inspect_zip(zip_path, name):

    print("\n" + "=" * 60)
    print(name)
    print("=" * 60)

    with zipfile.ZipFile(zip_path, "r") as archive:

        files = archive.namelist()

        print(f"Number of files: {len(files)}\n")

        for file in files[:100]:
            print(file)

        if len(files) > 100:
            print(f"\n... and {len(files) - 100} more files")


inspect_zip(PURE_ZIP, "PURE DATASET")

inspect_zip(
    SECOND_ZIP,
    "SOFTWARE REQUIREMENTS DATASET"
)