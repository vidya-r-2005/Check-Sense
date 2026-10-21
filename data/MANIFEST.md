# CheckSense Dataset Manifest

This manifest documents all datasets acquired and verified for the CheckSense project.
Per **MASTER_SPEC.md** Section 0 and Section 3, all datasets are authentic, real-world data verified against published host metadata.
Never fabricate datasets or metrics.

---

## Dataset Summary Table

| Dataset Name | Source URL / DOI / Record ID | Version | License | Download Date | File Count & Sizes | Checksums (MD5 / SHA256) | Intended Role | Verification Status |
|---|---|---|---|---|---|---|---|---|
| **PURE** | Zenodo `1414116` / `7118517` (DOI `10.5281/zenodo.7118517`) | v2.0 (2018) | CC-BY-4.0 | 2026-10-21 | 3 files (34.0 MB):<br>• `requirements-xml.zip` (378.7 KB)<br>• `req_document.xsd` (5.3 KB)<br>• `requirements.zip` (33.6 MB) | **requirements-xml.zip:**<br>MD5: `c81235c40f88a2c947ae66e0eddad585`<br>SHA256: `cf893f419d273a743ba090445d472c9e7825b29f34f66dbb7ad546700c02be55`<br>**req_document.xsd:**<br>MD5: `f44c255db9414afb7c39265697abcb33`<br>SHA256: `91ca5b4104d41fa77f300c3c907b27be636c0d8f070cb7a8b548f070dc88ba27`<br>**requirements.zip:**<br>MD5: `bc319fe28619f6290badff328ca159dd`<br>SHA256: `9ee633634e0fe93c5240212df49733ebdf11171fb2d02c1d044237d046c3ef6a` | Base corpus for candidate requirement extraction and gold annotation sampling | **VERIFIED** (Checksums match Zenodo REST API) |
| **ARTA** | Zenodo `4266727` (DOI `10.5281/zenodo.4266727`) | v1.0.0 (2020) | Null in Zenodo metadata (Academic Research; see HUMAN_TODO) | 2026-10-21 | 1 file (1.3 MB):<br>• `ARTADataset_release1.zip` (1,312,856 bytes) | **ARTADataset_release1.zip:**<br>MD5: `92a09adc5e4b9cd96370e7f09fe466d2`<br>SHA256: `41eb404fb8ea37cf21a37c0a6b7d197607a701ee435bb19163f572ae8b1b5e52` | Training and grouped cross-validation for sentence smell classifier | **VERIFIED** (Checksum matches; license approval logged in HUMAN_TODO) |
| **QuRE** | Zenodo `16049822` (Concept DOI `10.5281/zenodo.15656471`) | v1.0.1 (2025) | CC-BY-4.0 | 2026-10-21 | 2 files (333.0 KB):<br>• `QuRE.csv` (332,428 bytes)<br>• `description.md` (534 bytes) | **QuRE.csv:**<br>MD5: `80565e3b8996d8af1598813aafc87cb3`<br>SHA256: `6fe1d16715694dd6d6ae930926dff2ca7e0c4b2679c1db16d004655957b4478f`<br>**description.md:**<br>MD5: `e7b7a3526c0471fe6853daa13e5613d7`<br>SHA256: `25bce8c35397d91cb3dd567b40d6cfa878fa4209fae4a77cf38ca6efd7a0c868` | External evaluation test set for requirement ambiguity and smell detection | **VERIFIED** (Checksums match Zenodo REST API) |
| **Software Requirements Data Set** *(Unverified archive 7897601)* | Zenodo `7897601` (DOI `10.5281/zenodo.7897601`) | None (2023) | CC-BY-4.0 | 2026-10-21 | 1 file (11.8 MB):<br>• `Dataset.zip` (11,864,852 bytes) | **Dataset.zip:**<br>MD5: `89f141ad7376afdbec1cf6db858f10c4`<br>SHA256: `ce2f676239fe28224b74a3f2d2209d733c94d075191060934188b907c1efbb7d` | Investigated archive; confirmed as Šenkýř & Kroha derived composite corpus (PURE + coursework + healthcare + user stories) | **VERIFIED & DOCUMENTED** (Auxiliary reference only) |
| **PROMISE_exp** | N/A | N/A | Unverified | N/A | None | N/A | Functional requirement filter | **SKIPPED PER SPEC RULE** (Logged in HUMAN_TODO; modal-verb rule retained) |

---

## Detailed Acquisition & Verification Logs

### 1. PURE (Public REquirements Dataset)
- **Authors:** Alessio Ferrari, Giorgio Oronzo Spagnolo, Stefania Gnesi (CNR-ISTI, Italy)
- **Publication:** *2017 IEEE 25th International Requirements Engineering Conference (RE)*, pp. 502-505.
- **Repository Records:** Concept DOI `10.5281/zenodo.1414116`; v1.0 Record `1414117`; v2.0 Record `7118517`.
- **License Terms:** Creative Commons Attribution 4.0 International (CC-BY-4.0).
- **Contents:**
  - `requirements-xml.zip`: Contains 18 XML specification documents encoded under `req_document.xsd`.
  - `requirements.zip`: Contains 79 natural requirements specifications in PDF, RTF, and HTML format.
- **Verification:** Both archives downloaded and MD5 checksums matched host metadata byte-for-byte.

### 2. ARTA (Automatic Requirements Testability Analysis Dataset)
- **Author:** Morteza Zakeri-Nasrabadi (2020)
- **Publication:** *Requirement testability measurement based on requirement smells*, Neural Computing and Applications (2024).
- **Repository Record:** Zenodo `4266727`.
- **License Terms:** Academic fair use for research evaluation (see HUMAN_TODO.md).
- **Contents:** `ARTADataset_release1.zip` extracting `Datasets/` (`DS1.xlsx`, `DS2.xlsx`, `DS3.xlsx`, `DS4.xlsx`, `SmellyWordsDictionary.xlsx`) containing 4,752 requirements labeled across 9 smell categories.
- **Verification:** Downloaded and MD5 verified against Zenodo REST API.

### 3. QuRE (Industrial Requirements Quality Dataset)
- **Authors:** Henning Femmer, Frank Houdek, Max Unterbusch, Andreas Vogelsang
- **Publication:** *Description and Comparative Analysis of QuRE: A New Industrial Requirements Quality Dataset*, RE 2025 Workshops.
- **Repository Record:** Zenodo `16049822` / Concept DOI `10.5281/zenodo.15656471`.
- **License Terms:** Creative Commons Attribution 4.0 International (CC-BY-4.0).
- **Contents:** `QuRE.csv` (2,111 requirements evaluated for quality defects and weak words) and `description.md`.
- **Verification:** Both files downloaded and MD5 verified against Zenodo REST API.

### 4. Zenodo Archive 7897601 (Šenkýř & Kroha 2023)
- **Authors:** David Šenkýř, Petr Kroha (Czech Technical University in Prague)
- **Publication:** Zenodo `7897601` (May 2023).
- **License Terms:** CC-BY-4.0.
- **Contents:** `Dataset.zip` containing 51 subdirectories across 4 distinct requirement domains.
- **Verification:** Downloaded and verified.
