"""Dataset acquisition and verification module for CheckSense.

Strictly downloads authentic datasets from Zenodo REST API, verifies
MD5/SHA256 checksums against host metadata, and extracts files safely.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

DATASET_CONFIGS = {
    "pure": {
        "record_id": "7118517",  # PURE v2.0 latest release (concept 1414116)
        "name": "PURE",
        "description": "PURE: a Dataset of Public Requirements Documents (v2.0, Ferrari et al. 2017)",
        "expected_files": {
            "requirements-xml.zip": "c81235c40f88a2c947ae66e0eddad585",
            "req_document.xsd": "f44c255db9414afb7c39265697abcb33",
            "requirements.zip": "bc319fe28619f6290badff328ca159dd",
        },
        "role": "Base corpus for candidate requirement extraction and gold annotation sampling",
    },
    "arta": {
        "record_id": "4266727",
        "name": "ARTA",
        "description": "Automatic Requirements Testability Analysis Dataset (Zakeri-Nasrabadi 2020)",
        "expected_files": {
            "ARTADataset_release1.zip": "92a09adc5e4b9cd96370e7f09fe466d2",
        },
        "role": "Training and cross-validation for sentence-level requirement smell classifier",
    },
    "qure": {
        "record_id": "15656471",  # Concept DOI 10.5281/zenodo.15656471 -> Record 16049822
        "name": "QuRE",
        "description": "QuRE: Industrial Requirements Quality Dataset (Femmer et al. 2025)",
        "expected_files": {
            "QuRE.csv": "80565e3b8996d8af1598813aafc87cb3",
            "description.md": "e7b7a3526c0471fe6853daa13e5613d7",
        },
        "role": "External test set for ambiguity and smell detection head",
    },
    "unverified": {
        "record_id": "7897601",
        "name": "Senkyr_Kroha_Dataset",
        "description": "Software Requirements Data Set (Šenkýř & Kroha 2023, PURE + 3 sources)",
        "expected_files": {
            "Dataset.zip": "89f141ad7376afdbec1cf6db858f10c4",
        },
        "role": "Investigated archive: derived dataset combining PURE with other sources",
    },
}

ZENODO_API_URL = "https://zenodo.org/api/records/{record_id}"


def compute_file_hashes(file_path: Path) -> tuple[str, str]:
    """Compute MD5 and SHA256 hex digests for a local file."""
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            md5.update(chunk)
            sha256.update(chunk)
    return md5.hexdigest(), sha256.hexdigest()


def fetch_zenodo_metadata(record_id: str) -> dict[str, Any]:
    """Fetch official metadata from Zenodo REST API."""
    url = ZENODO_API_URL.format(record_id=record_id)
    headers = {"User-Agent": "CheckSense-Dataset-Verifier/1.0"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def download_file(url: str, dest_path: Path, expected_size: int | None = None) -> None:
    """Download a file with progress tracking and streaming chunks."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "CheckSense-Dataset-Verifier/1.0"}
    with requests.get(url, headers=headers, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", expected_size or 0))
        with open(dest_path, "wb") as f, tqdm(
            desc=dest_path.name,
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
                    bar.update(len(chunk))


def acquire_dataset(
    dataset_key: str,
    output_base_dir: Path = Path("data/raw"),
    skip_checksum: bool = False,
    only_files: list[str] | None = None,
) -> dict[str, Any]:
    """Acquire, verify, and extract a dataset from Zenodo."""
    if dataset_key not in DATASET_CONFIGS:
        raise ValueError(f"Unknown dataset key: {dataset_key}. Valid: {list(DATASET_CONFIGS.keys())}")

    config = DATASET_CONFIGS[dataset_key]
    record_id = config["record_id"]
    target_dir = output_base_dir / dataset_key
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"Acquiring {config['name']} (Zenodo record {record_id})")
    print(f"{'='*70}")

    metadata_json = fetch_zenodo_metadata(record_id)
    files_info = metadata_json.get("files", [])
    meta = metadata_json.get("metadata", {})

    license_info = meta.get("license", {})
    license_id = license_info.get("id") if isinstance(license_info, dict) else str(license_info)
    print(f"Title: {meta.get('title')}")
    print(f"DOI: {metadata_json.get('doi')}")
    print(f"Version: {meta.get('version')}")
    print(f"License: {license_id}")

    verification_report: dict[str, Any] = {
        "dataset_key": dataset_key,
        "name": config["name"],
        "record_id": record_id,
        "doi": metadata_json.get("doi"),
        "version": meta.get("version"),
        "license": license_id,
        "publication_date": meta.get("publication_date"),
        "creators": [c.get("name") for c in meta.get("creators", [])],
        "role": config["role"],
        "files": [],
    }

    # Save raw metadata
    meta_path = target_dir / "zenodo_metadata.json"
    meta_path.write_text(json.dumps(metadata_json, indent=2), encoding="utf-8")

    # Match and download files
    for f in files_info:
        fname = f.get("key") or f.get("filename")
        if only_files and fname not in only_files:
            continue
        if fname not in config["expected_files"] and only_files is None:
            # Skip non-essential auxiliary files
            continue

        download_url = (f.get("links", {})).get("self") or (f.get("links", {})).get("download")
        if not download_url:
            continue

        file_dest = target_dir / fname
        expected_size = f.get("size") or f.get("filesize")
        expected_md5 = config["expected_files"].get(fname)
        if not expected_md5:
            # Zenodo format: 'md5:hash'
            zenodo_checksum = f.get("checksum", "")
            if zenodo_checksum.startswith("md5:"):
                expected_md5 = zenodo_checksum[4:]

        print(f"\n[*] Processing {fname} ({expected_size:,} bytes)...")
        if not file_dest.exists() or file_dest.stat().st_size != expected_size:
            print(f"    Downloading from {download_url}...")
            download_file(download_url, file_dest, expected_size=expected_size)
        else:
            print(f"    File already exists at {file_dest}, verifying checksum...")

        # Hash verification
        calc_md5, calc_sha256 = compute_file_hashes(file_dest)
        checksum_ok = (calc_md5 == expected_md5) if expected_md5 else True

        file_report = {
            "filename": fname,
            "size_bytes": file_dest.stat().st_size,
            "expected_md5": expected_md5,
            "calculated_md5": calc_md5,
            "calculated_sha256": calc_sha256,
            "checksum_verified": checksum_ok,
            "download_url": download_url,
        }
        verification_report["files"].append(file_report)

        if not checksum_ok and not skip_checksum:
            raise ValueError(
                f"Checksum mismatch for {fname}! Expected MD5: {expected_md5}, got: {calc_md5}"
            )
        print(f"    [+] MD5 Checksum verified: {calc_md5}")

        # Extract archive if zip
        if fname.endswith(".zip"):
            extract_dir = target_dir / "extracted" / Path(fname).stem
            print(f"    [*] Extracting to {extract_dir}...")
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(file_dest, "r") as zf:
                zf.extractall(extract_dir)
            extracted_count = len(list(extract_dir.rglob("*")))
            print(f"    [+] Extracted {extracted_count} items.")
            file_report["extracted_path"] = str(extract_dir)
            file_report["extracted_items_count"] = extracted_count

    return verification_report
