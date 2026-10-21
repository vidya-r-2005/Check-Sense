"""Generate and populate exploratory data analysis (EDA) notebooks for Phase 1.

Generates:
1. notebooks/01_pure_eda.ipynb
2. notebooks/02_arta_eda.ipynb
3. notebooks/03_qure_eda.ipynb
"""

from __future__ import annotations

import json
from pathlib import Path

NOTEBOOKS_DIR = Path("notebooks")
NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)


def make_notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12.4",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def make_markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source.split("\n")],
    }


def make_code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.split("\n")],
    }


def create_pure_eda_notebook():
    cells = [
        make_markdown_cell(
            "# 01. Exploratory Data Analysis: PURE Dataset\n\n"
            "This notebook analyzes the authentic PURE (Public REquirements) dataset (Ferrari et al., RE 2017).\n"
            "Per CheckSense binding rules, all statistics and samples are drawn directly from `data/interim/pure_requirements.jsonl`."
        ),
        make_code_cell(
            "import json\n"
            "import pandas as pd\n"
            "from pathlib import Path\n\n"
            "# 1. Load interim requirements\n"
            "jsonl_path = Path('../data/interim/pure_requirements.jsonl')\n"
            "records = [json.loads(line) for line in jsonl_path.read_text(encoding='utf-8').splitlines() if line.strip()]\n"
            "df = pd.DataFrame(records)\n"
            "print(f'Total candidate requirements: {len(df):,}')\n"
            "print(f'Unique documents: {df[\"doc_id\"].nunique()}')\n"
            "df.head()"
        ),
        make_markdown_cell("## 2. Requirements per Document Breakdown"),
        make_code_cell(
            "doc_counts = df['doc_id'].value_counts().reset_index()\n"
            "doc_counts.columns = ['Document ID', 'Requirement Count']\n"
            "doc_counts"
        ),
        make_markdown_cell("## 3. Token Length Distribution"),
        make_code_cell(
            "stats = df['token_count'].describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95])\n"
            "print('Token Count Summary Statistics:')\n"
            "print(stats)\n"
        ),
        make_markdown_cell("## 4. Modal Verb Proportions"),
        make_code_cell(
            "import re\n"
            "modals = {'shall': r'\\bshall\\b', 'must': r'\\bmust\\b', 'should': r'\\bshould\\b', 'will': r'\\bwill\\b'}\n"
            "modal_counts = {}\n"
            "for name, pat in modals.items():\n"
            "    count = df['text'].str.contains(pat, flags=re.IGNORECASE).sum()\n"
            "    modal_counts[name] = {'count': count, 'percentage': round(100 * count / len(df), 2)}\n"
            "pd.DataFrame(modal_counts).T"
        ),
        make_markdown_cell("## 5. Filtering Audit Statistics"),
        make_code_cell(
            "stats_path = Path('../data/interim/pure_filtering_stats.json')\n"
            "filter_stats = json.loads(stats_path.read_text(encoding='utf-8'))\n"
            "pd.DataFrame(list(filter_stats['summary'].items()), columns=['Metric', 'Value'])"
        ),
        make_markdown_cell("## 6. Twenty Random Requirement Samples (Seed 42)"),
        make_code_cell(
            "sample_20 = df.sample(n=20, random_state=42)[['req_id', 'doc_id', 'token_count', 'text']]\n"
            "for idx, row in sample_20.reset_index(drop=True).iterrows():\n"
            "    print(f'[{idx+1:02d}] {row[\"req_id\"]} ({row[\"token_count\"]} tokens):')\n"
            "    print(f'     \"{row[\"text\"]}\"\\n')"
        ),
    ]
    nb = make_notebook(cells)
    out_path = NOTEBOOKS_DIR / "01_pure_eda.ipynb"
    out_path.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    print(f"Created {out_path}")


def create_arta_eda_notebook():
    cells = [
        make_markdown_cell(
            "# 02. Exploratory Data Analysis: ARTA Smell Dataset\n\n"
            "Analyzes the authentic ARTA dataset (Zakeri-Nasrabadi 2020, Zenodo record 4266727).\n"
            "Inspects the 4 spreadsheet datasets (DS1 to DS4) and smell distributions."
        ),
        make_code_cell(
            "import pandas as pd\n"
            "from pathlib import Path\n\n"
            "data_dir = Path('../data/raw/arta/extracted/ARTADataset_release1/Datasets')\n"
            "files = sorted(data_dir.glob('DS*.xlsx'))\n"
            "dfs = {f.stem: pd.read_excel(f) for f in files}\n"
            "for name, d in dfs.items():\n"
            "    print(f'{name}: shape={d.shape}')"
        ),
        make_markdown_cell("## 2. Smell Columns in DS1"),
        make_code_cell(
            "ds1 = dfs['DS1']\n"
            "print('Columns in DS1:', list(ds1.columns))\n"
            "smell_cols = [c for c in ds1.columns if c not in ('Requirement_text', 'File')]\n"
            "smell_freq = {}\n"
            "for col in smell_cols:\n"
            "    present = ds1[col].astype(str).str.strip().ne('-') & ds1[col].notna()\n"
            "    smell_freq[col] = present.sum()\n"
            "pd.DataFrame(list(smell_freq.items()), columns=['Smell Type', 'Count in DS1']).sort_values('Count in DS1', ascending=False)"
        ),
        make_markdown_cell("## 3. Sample 20 Rows from DS1 (Seed 42)"),
        make_code_cell(
            "sample_20 = ds1.sample(n=20, random_state=42)\n"
            "for i, row in sample_20.reset_index(drop=True).iterrows():\n"
            "    active_smells = [c for c in smell_cols if str(row[c]).strip() not in ('-', 'nan')]\n"
            "    print(f'[{i+1:02d}] File: {row[\"File\"]}')\n"
            "    print(f'     Text: {str(row[\"Requirement_text\"]).strip()[:100]}...')\n"
            "    print(f'     Smells: {active_smells}\\n')"
        ),
    ]
    nb = make_notebook(cells)
    out_path = NOTEBOOKS_DIR / "02_arta_eda.ipynb"
    out_path.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    print(f"Created {out_path}")


def create_qure_eda_notebook():
    cells = [
        make_markdown_cell(
            "# 03. Exploratory Data Analysis: QuRE External Test Set\n\n"
            "Analyzes the QuRE dataset (Femmer et al., 2025; Zenodo DOI 10.5281/zenodo.15656471).\n"
            "Serves as the external test set for requirement ambiguity and smell detection."
        ),
        make_code_cell(
            "import pandas as pd\n"
            "from pathlib import Path\n\n"
            "qure_path = Path('../data/raw/qure/QuRE.csv')\n"
            "df = pd.read_csv(qure_path)\n"
            "print(f'Total requirements: {len(df):,}')\n"
            "print(f'Columns: {list(df.columns)}')\n"
            "df.head()"
        ),
        make_markdown_cell("## 2. Defect vs OK Label Distribution"),
        make_code_cell(
            "defect_counts = df['defect'].value_counts()\n"
            "pd.DataFrame({'Count': defect_counts, 'Percentage': (defect_counts / len(df) * 100).round(2)})"
        ),
        make_markdown_cell("## 3. Weak Word Frequency (Top 15)"),
        make_code_cell(
            "weak_words = df['weak_word'].value_counts().head(15)\n"
            "pd.DataFrame({'Count': weak_words, 'Percentage': (weak_words / len(df) * 100).round(2)})"
        ),
        make_markdown_cell("## 4. 20 Random Samples (Seed 42)"),
        make_code_cell(
            "sample_20 = df.sample(n=20, random_state=42)\n"
            "for i, row in sample_20.reset_index(drop=True).iterrows():\n"
            "    print(f'[{i+1:02d}] ID: {row[\"id\"]} | Weak Word: \"{row[\"weak_word\"]}\" | Defect: {row[\"defect\"]}')\n"
            "    print(f'     \"{row[\"requirement\"]}\"\\n')"
        ),
    ]
    nb = make_notebook(cells)
    out_path = NOTEBOOKS_DIR / "03_qure_eda.ipynb"
    out_path.write_text(json.dumps(nb, indent=2), encoding="utf-8")
    print(f"Created {out_path}")


if __name__ == "__main__":
    create_pure_eda_notebook()
    create_arta_eda_notebook()
    create_qure_eda_notebook()
