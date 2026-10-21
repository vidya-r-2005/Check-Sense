"""Inspect Zenodo record metadata via REST API.

Queries Zenodo records for PURE, ARTA, QuRE, and unverified archives,
extracting title, version, license, DOI, files, file sizes, and checksums.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

RECORDS = {
    "pure_1414116": "1414116",
    "pure_1414117": "1414117",
    "arta_4266727": "4266727",
    "qure_15656471": "15656471",
    "unverified_7118517": "7118517",
    "unverified_7897601": "7897601",
}

ZENODO_API = "https://zenodo.org/api/records/{record_id}"


def inspect_record(name: str, record_id: str) -> dict:
    url = ZENODO_API.format(record_id=record_id)
    print(f"[*] Querying Zenodo for {name} (record {record_id})...")
    headers = {"User-Agent": "CheckSense-Dataset-Verifier/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            metadata = data.get("metadata", {})
            files = data.get("files", [])
            summary = {
                "name": name,
                "record_id": record_id,
                "status": "success",
                "title": metadata.get("title"),
                "doi": data.get("doi") or metadata.get("doi"),
                "version": metadata.get("version"),
                "license": metadata.get("license"),
                "description": metadata.get("description", "")[:300],
                "publication_date": metadata.get("publication_date"),
                "creators": [c.get("name") for c in metadata.get("creators", [])],
                "files": [
                    {
                        "filename": f.get("key") or f.get("filename"),
                        "size": f.get("size") or f.get("filesize"),
                        "checksum": f.get("checksum"),
                        "download_url": (f.get("links", {})).get("self") or (f.get("links", {})).get("download"),
                    }
                    for f in files
                ],
            }
            return summary
        else:
            return {
                "name": name,
                "record_id": record_id,
                "status": f"HTTP {resp.status_code}",
                "error": resp.text[:200],
            }
    except Exception as e:
        return {
            "name": name,
            "record_id": record_id,
            "status": "connection_error",
            "error": str(e),
        }


def main():
    results = {}
    for name, record_id in RECORDS.items():
        results[name] = inspect_record(name, record_id)

    out_path = Path("data/raw/zenodo_metadata_cache.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[+] Saved metadata cache to {out_path}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
