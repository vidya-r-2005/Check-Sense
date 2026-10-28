# CheckSense: ARTA Label Mapping Specification

**Date:** 2026-10-28  
**Status:** PROVISIONALLY ADOPTED FOR PHASE 4 (Per Stakeholder Directive)  
**Dataset Reference:** ARTA (Zenodo record 4266727, v1.0.0, Zakeri-Nasrabadi 2020)  
**Provisional Reference:** Rater 1 Annotations (`data/gold/annotations/rater_1.csv`)

---

## 1. Inspection of Real ARTA Spreadsheets

Inspection of `data/raw/arta/extracted/ARTADataset_release1/Datasets/` reveals 4 primary evaluation spreadsheets totaling **4,752 requirements**:

| Spreadsheet | Number of Rows | Number of Columns | Primary Smell Columns (Exact Column Headers) |
|---|---|---|---|
| `DS1.xlsx` | 985 | 12 | `Subjective_lang.`, `Ambiguous_adv._adj.`, `Loophole`, `Nonverifiable_term`, `Superlative`, `Comparative`, `Negative`, `Vague_pron.`, `Uncertain_verb`, `Polysemy` |
| `DS2.xlsx` | 1,092 | 10 | `subjective_language`, `ambiguous_adverbs_adjectives`, `loopholes`, `open_ended`, `superlatives`, `comparatives`, `negative_statements`, `vague_pronouns` |
| `DS3.xlsx` | 1,522 | 10 | `subjective_language`, `ambiguous_adverbs_adjectives`, `loopholes`, `open_ended`, `superlatives`, `comparatives`, `negative_statements`, `vague_pronouns` |
| `DS4.xlsx` | 1,153 | 10 | `superlative`, `vague_pronuns`, `Compratives`, `Ambiguouse_adverb_and_adjective`, `negative_sentence`, `looples`, `Open ended NonVarifiable`, `Subjective Language` |
| `SmellyWordsDictionary.xlsx` | 1,000 | 8 | `Subjective Language`, `Ambiguous Adv, Adj`, `Loopholes`, `Open-ended, Non-verifiable terms`, `Polysemy`, `Irrelevant` |

### Value Representation in Cells
- When a smell is **present**, the cell contains the span or triggering word(s) (e.g., `'safely'`, `'appropriate*other*commercial'`).
- When a smell is **absent**, the cell contains `'-'` or empty/whitespace.
- Therefore, a binary smell indicator is derived deterministically: `cell.strip().lower() not in ('-', '', 'nan', 'none', '0', 'null', 'false')`.

---

## 2. CheckSense Target Gap Taxonomy (MASTER_SPEC.md Section 2)

| Class | Subtype | Definition / Examples |
|---|---|---|
| `ambiguity` | `vague_term` | Subjective terms, ambiguous adjectives/adverbs, non-verifiable terms, uncertain verbs (e.g. *user-friendly*, *adequately*, *fast*, *might*) |
| `ambiguity` | `vague_quantifier` | Unquantified superlatives and comparatives (e.g. *highest possible*, *faster than usual*, *minimal*) |
| `ambiguity` | `anaphora` | Pronouns with ambiguous antecedents (e.g. *it*, *this*, *they*) |
| `ambiguity` | `coordination` | Ambiguous boolean scope (*and* / *or* combinations) |
| `incompleteness` | `missing_condition` | Loopholes, open-ended clauses, or negative conditionals (*as appropriate*, *if possible*) |
| `incompleteness` | `missing_actor` | Passive voice missing clear agent |
| `incompleteness` | `missing_threshold` | Undefined operational boundaries |
| `incompleteness` | `missing_error_handling`| Failure paths unaddressed |
| `implicit` | `unstated_constraint` | Implicit requirements from ontology |

---

## 3. Adopted Mapping

The 9 ARTA smell types map to CheckSense classes and subtypes as follows:

| ARTA Smell Type | Normalized Column Variations | Target CheckSense Class | Target CheckSense Subtype | Rationale |
|---|---|---|---|---|
| **Subjective Language** | `Subjective_lang.`, `subjective_language`, `Subjective Language` | `ambiguity` | `vague_term` | Subjective words (*easy*, *safe*, *flexible*) depend on personal opinion and cannot be verified objectively. |
| **Ambiguous Adverbs & Adjectives** | `Ambiguous_adv._adj.`, `ambiguous_adverbs_adjectives`, `Ambiguouse_adverb_and_adjective` | `ambiguity` | `vague_term` | Adverbs/adjectives lacking operational precision (*periodically*, *quickly*, *suitable*). |
| **Non-verifiable / Open-ended** | `Nonverifiable_term`, `open_ended`, `Open ended NonVarifiable` | `ambiguity` | `vague_term` | Terms admitting unbounded possibilities (*including but not limited to*, *support*, *etc.*). |
| **Uncertain Verbs** | `Uncertain_verb` | `ambiguity` | `vague_term` | Verbs expressing doubt or non-commitment (*might*, *could*, *plan to*). |
| **Polysemy** | `Polysemy` | `ambiguity` | `vague_term` | Words having multiple semantic interpretations in technical domain. |
| **Superlatives** | `Superlative`, `superlatives`, `superlative` | `ambiguity` | `vague_quantifier` | Extreme claims (*best*, *most efficient*) lacking bounded metric. |
| **Comparatives** | `Comparative`, `comparatives`, `Compratives` | `ambiguity` | `vague_quantifier` | Relative comparisons (*faster*, *better*) without explicit baseline. |
| **Vague Pronouns** | `Vague_pron.`, `vague_pronouns`, `vague_pronuns` | `ambiguity` | `anaphora` | Pronouns (*it*, *which*, *they*) creating anaphoric ambiguity. |
| **Loopholes** | `Loophole`, `loopholes`, `looples` | `incompleteness` | `missing_condition` | Clauses allowing omission of duty (*where feasible*, *as appropriate*, *if applicable*). |
| **Negative Statements** | `Negative`, `negative_statements`, `negative_sentence` | `ambiguity` / auxiliary feature | `auxiliary_negative` | Negative statements (*shall not*) are not automatically defective, but frequently create loophole / scoping ambiguities. Adopted as an auxiliary sentence-level feature for the smell classifier. |

---

## 4. Governance & Provisional Adoption Notice

Per Stakeholder Directive (2026-10-28):
- To proceed to Phase 4 without delaying for manual pilot re-annotation, this mapping is **provisionally adopted** for training and evaluating `TfidfSmellClassifier` and associated heads.
- Both original annotator files (`rater_1.csv` and `rater_2.csv`) are strictly preserved unchanged.
- `rater_1.csv` is designated as the provisional classification reference for training and evaluation benchmarks.
- Model performance against these provisional labels measures agreement with Rater 1's labeling conventions, not reconciled ground-truth defect detection.
