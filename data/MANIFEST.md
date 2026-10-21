# CheckSense Dataset Manifest

This manifest documents all datasets acquired and verified for the CheckSense project.
Per **MASTER_SPEC.md** Section 0 and Section 3, all datasets are authentic, real-world data verified against published host metadata.
Never fabricate datasets, labels, or metrics.

---

## Dataset Summary Table

| Dataset Name | Source URL / DOI / Record ID | Version | License & Rights | Download Date | File Count & Sizes | Checksums (MD5 / SHA256) | Intended Role | Verification & Reuse Status |
|---|---|---|---|---|---|---|---|---|
| **PURE** | **Concept DOI:** `10.5281/zenodo.1414116`<br>**Version Record:** Zenodo `7118517` (DOI `10.5281/zenodo.7118517`) | v2.0 (2018-09-12) | Record license: `CC-BY-4.0`<br>Source: Web-gathered public requirements with curator takedown policy (see Section 1 below) | 2026-10-21 | 3 files (34.0 MB):<br>• `requirements-xml.zip` (378,737 B)<br>• `req_document.xsd` (5,355 B)<br>• `requirements.zip` (33,623,628 B) | **requirements-xml.zip:**<br>MD5: `c81235c40f88a2c947ae66e0eddad585`<br>SHA256: `cf893f419d273a743ba090445d472c9e7825b29f34f66dbb7ad546700c02be55`<br>**req_document.xsd:**<br>MD5: `f44c255db9414afb7c39265697abcb33`<br>SHA256: `91ca5b4104d41fa77f300c3c907b27be636c0d8f070cb7a8b548f070dc88ba27`<br>**requirements.zip:**<br>MD5: `bc319fe28619f6290badff328ca159dd`<br>SHA256: `9ee633634e0fe93c5240212df49733ebdf11171fb2d02c1d044237d046c3ef6a` | Base corpus for candidate requirement extraction and gold annotation sampling | **VERIFIED**<br>Contains 18 authentic XML specifications in `requirements-xml.zip` (all 18 parsed; 0 dropped). |
| **ARTA** | **Record:** Zenodo `4266727`<br>**DOI:** `10.5281/zenodo.4266727` | v1.0.0 (2020-11-10) | **None specified** (`"license": null`, `"access_right": "open"`; no license file in zip) | 2026-10-21 | 1 file (1.3 MB):<br>• `ARTADataset_release1.zip` (1,312,856 B) | **ARTADataset_release1.zip:**<br>MD5: `92a09adc5e4b9cd96370e7f09fe466d2`<br>SHA256: `41eb404fb8ea37cf21a37c0a6b7d197607a701ee435bb19163f572ae8b1b5e52` | Training and grouped cross-validation for sentence smell classifier | **DOWNLOAD VERIFIED / TRAINING BLOCKED**<br>Checksum verified. Training remains blocked until human establishes reuse terms. |
| **QuRE** | **Concept DOI:** `10.5281/zenodo.15656471`<br>**Version Record:** Zenodo `16049822`<br>**Version DOI:** `10.5281/zenodo.16049822` | v1.0.1 (2025-07-17) | `CC-BY-4.0` | 2026-10-21 | 2 files (333.0 KB):<br>• `QuRE.csv` (332,428 B)<br>• `description.md` (534 B) | **QuRE.csv:**<br>MD5: `80565e3b8996d8af1598813aafc87cb3`<br>SHA256: `6fe1d16715694dd6d6ae930926dff2ca7e0c4b2679c1db16d004655957b4478f`<br>**description.md:**<br>MD5: `e7b7a3526c0471fe6853daa13e5613d7`<br>SHA256: `25bce8c35397d91cb3dd567b40d6cfa878fa4209fae4a77cf38ca6efd7a0c868` | External evaluation test set for requirement ambiguity and smell detection | **VERIFIED**<br>2,187 labeled rows (2,111 unique industrial requirements) with human defect annotations. |
| **Software Requirements Data Set** *(Unverified archive 7897601)* | **Record:** Zenodo `7897601`<br>**DOI:** `10.5281/zenodo.7897601` | None (2023-05-04) | `CC-BY-4.0` | 2026-10-21 | 1 file (11.8 MB):<br>• `Dataset.zip` (11,864,852 B) | **Dataset.zip:**<br>MD5: `89f141ad7376afdbec1cf6db858f10c4`<br>SHA256: `ce2f676239fe28224b74a3f2d2209d733c94d075191060934188b907c1efbb7d` | Investigated archive; confirmed as Šenkýř & Kroha derived composite corpus | **VERIFIED & DOCUMENTED**<br>Auxiliary reference only (contains 18 PURE docs + 3 other domains). |
| **PROMISE_exp** | N/A | N/A | Unverified / No canonical open host | N/A | None | N/A | Learned functional-requirement filter | **SKIPPED PER SPEC RULE**<br>Logged in HUMAN_TODO; deterministic modal-verb rule retained. |

---

## Detailed Provenance & Rights Statements

### 1. PURE Rights Statement & Specification Document Count
- **Curators:** Alessio Ferrari, Giorgio Oronzo Spagnolo, Stefania Gnesi (CNR-ISTI, Italy)
- **Official Records:**
  - Concept DOI: `10.5281/zenodo.1414116`
  - Version 1.0 Record: `1414117` (`10.5281/zenodo.1414117`)
  - Version 2.0 Record: `7118517` (`10.5281/zenodo.7118517`)
- **Official Description & Rights Statement (Verbatim from Zenodo metadata):**
  > *"The dataset has been created by gathering data from web sources and we are not aware of license agreements or intellectual property rights on the requirements. The curator took utmost diligence in minimizing the risks of copyright infringement by using non-recent data that is less likely to be critical, by sampling a subset of the original requirements collection, and by qualitatively analyzing the requirements. In case of copyright infringement, please contact the dataset curator (Alessio Ferrari, alessio.ferrari@cnr.it, alessio.ferrari@ucd.ie) to discuss the possibility of removal of that dataset [see Zenodo's policies]."*
- **XML Count Clarification:**
  While the curator's summary description informally states *"a subset of 19 documents in XML format"*, inspecting the actual deposited archive `requirements-xml.zip` (verified MD5 `c81235c40f88a2c947ae66e0eddad585`) reveals that it contains **exactly 18 XML files** inside `XMLZIPFile/`, plus the directory `XMLZIPFile` itself (totaling 19 zip entries; and 19 resource-fork entries in `__MACOSX`). The 18 specification documents are:
  1. `0000 - cctns.xml`
  2. `0000 - gamma j.xml`
  3. `1995 - gemini.xml`
  4. `1998 - themas.xml`
  5. `1999 - dii.xml`
  6. `1999 - tcs.xml`
  7. `2003 - qheadache.xml`
  8. `2005 - microcare.xml`
  9. `2005 - phin.xml`
  10. `2006 - eirene sys 15.xml`
  11. `2007 - get real 0.2.xml`
  12. `2007-eirene_fun_7-2.xml`
  13. `2007-ertms.xml`
  14. `2008 - keepass.xml`
  15. `2008 - peering.xml`
  16. `2009 - peppol approved.xml`
  17. `2009 - video search.xml`
  18. `2010-blitdraft.xml`  
  All 18 specification documents were successfully parsed and processed into `data/interim/pure_requirements.jsonl` with zero documents dropped.

### 2. ARTA Licensing & Reuse Restriction
- **Depositor:** Morteza Zakeri-Nasrabadi (2020)
- **Publication Reference:** Zakeri-Nasrabadi et al., *"Requirement testability measurement based on requirement smells"*, Neural Computing and Applications (2024).
- **Zenodo API Metadata:**
  - `"access_right": "open"`
  - `"license": null`
  - `"notes": null`
- **Archive Inspection:** `ARTADataset_release1.zip` contains only Excel spreadsheets (`.xlsx`) in `Datasets/` and `DS1_Evaluation/`. No `LICENSE`, `README`, or terms of use document is included in the archive.
- **Enforcement Status:** Because no explicit permissive open-source license is granted, **training on ARTA is strictly BLOCKED** until the user/stakeholder establishes or accepts the reuse terms.

### 3. QuRE Provenance
- **Curators:** Henning Femmer, Frank Houdek, Max Unterbusch, Andreas Vogelsang
- **Publication:** *Description and Comparative Analysis of QuRE: A New Industrial Requirements Quality Dataset*, IEEE 33rd International Requirements Engineering Conference Workshops (REW 2025).
- **Concept DOI:** `10.5281/zenodo.15656471` (resolves to latest version)
- **Version Record ID:** Zenodo `16049822`
- **Version DOI:** `10.5281/zenodo.16049822`
- **Version:** `1.0.1` (Published: 2025-07-17)
- **License:** `CC-BY-4.0` (Creative Commons Attribution 4.0 International)
- **Files Verified:**
  - `QuRE.csv` (332,428 bytes, MD5: `80565e3b8996d8af1598813aafc87cb3`, SHA256: `6fe1d16715694dd6d6ae930926dff2ca7e0c4b2679c1db16d004655957b4478f`)
  - `description.md` (534 bytes, MD5: `e7b7a3526c0471fe6853daa13e5613d7`, SHA256: `25bce8c35397d91cb3dd567b40d6cfa878fa4209fae4a77cf38ca6efd7a0c868`)
