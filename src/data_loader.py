import requests
from pathlib import Path
from tqdm import tqdm


# Zenodo record IDs
PURE_RECORD = "7118517"
SECOND_RECORD = "7897601"


# Project directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


def get_zenodo_record(record_id):
    url = f"https://zenodo.org/api/records/{record_id}"

    response = requests.get(url)
    response.raise_for_status()

    return response.json()


def download_file(url, destination):

    destination = Path(destination)

    # Don't download again if file already exists
    if destination.exists():
        print(f"Already exists: {destination}")
        return

    print(f"\nDownloading: {destination.name}")

    response = requests.get(url, stream=True)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    with open(destination, "wb") as file:

        with tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            desc=destination.name
        ) as progress:

            for chunk in response.iter_content(chunk_size=8192):

                if chunk:
                    file.write(chunk)
                    progress.update(len(chunk))

    print("Download complete.")


def download_zenodo_file(record_id, file_name, output_folder):

    record = get_zenodo_record(record_id)

    for file_info in record["files"]:

        if file_info["key"] == file_name:

            url = file_info["links"]["self"]

            output_folder = Path(output_folder)
            output_folder.mkdir(parents=True, exist_ok=True)

            destination = output_folder / file_name

            download_file(url, destination)

            return

    raise FileNotFoundError(
        f"{file_name} was not found in Zenodo record {record_id}"
    )


if __name__ == "__main__":

    # PURE
    print("\n=== PURE DATASET ===")

    download_zenodo_file(
        PURE_RECORD,
        "requirements.zip",
        RAW_DATA_DIR / "PURE"
    )

    # Software Requirements Dataset
    print("\n=== SOFTWARE REQUIREMENTS DATASET ===")

    download_zenodo_file(
        SECOND_RECORD,
        "Dataset.zip",
        RAW_DATA_DIR / "SoftwareRequirements"
    )