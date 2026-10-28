"""Comparative Baselines (B1–B4) and Ablation Studies for CheckSense.

Implements MASTER_SPEC.md Sections 7 and 11:
- B1: Rules-only baseline (lexicon & frame slot rules).
- B2: Span tagger alone (maps token-level BIO predictions directly to gaps, no multi-head, no fusion).
- B3: Single zero-shot LLM (qwen2.5:7b default) with strict span grounding (ungrounded spans discarded).
- B4: Multi-LLM majority vote (qwen2.5:7b, llama3.1:8b, mistral:7b) with span grounding and >=2 consensus.
- Ablations:
  * Remove Head 4a (no smell/span ambiguity head).
  * Remove Head 4b (no semantic frame slot incompleteness head).
  * Remove Head 4c (no domain ontology implicit head).
  * Plain union of heads (union without Phase 5 candidate-level MLP fusion).
  * Template-only vs. LLM question formulation comparison.
  * Generic vs. gap-conditioned prompt comparison.
- Generates paper-ready comparative summary to 'results/summary.csv' in one command.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .baseline import CandidateGap, _find_exact_phrase, detect_rule_gaps
from .frame import extract_requirement_frame
from .fusion import HeuristicFusionScorer, MLPFusionScorer, deduplicate_and_rank_candidates
from .generation import (
    get_template_explanation_and_question,
    validate_generation_output,
)
from .heads import Phase4Pipeline
from .llm import LLMClient, OllamaClient
from .metrics import evaluate_predictions
from .span_tagger import LinearSpanTagger, token_jaccard

# ============================================================================
# Baseline B2: Span Tagger Alone
# ============================================================================

def detect_b2_span_alone_gaps(
    text: str,
    span_tagger: LinearSpanTagger | None = None,
    span_model_path: Path | None = None,
) -> list[CandidateGap]:
    """B2 Baseline: Token-level BIO span tagger mapped directly to gaps.

    Operates without multi-head detection, sentence smell classification,
    frame-slot rules, or candidate fusion.
    """
    if span_tagger is None:
        path = span_model_path or Path("results/span_tagger/span_tagger.joblib")
        if path.exists():
            try:
                span_tagger = LinearSpanTagger.load(path)
            except Exception:
                span_tagger = None

    if span_tagger is None:
        return []

    predicted_spans = span_tagger.predict_spans(text)
    gaps: list[CandidateGap] = []

    for s in predicted_spans:
        g_type = s.get("gap_type", "ambiguity")
        span_text = s.get("span_text", "").strip()
        if not span_text:
            continue

        if g_type == "ambiguity":
            s_type = "vague_term"
        elif g_type == "incompleteness":
            s_type = "missing_condition"
        else:
            s_type = "unstated_constraint"

        expl, q = get_template_explanation_and_question(g_type, s_type, span_text)

        gaps.append(
            CandidateGap(
                gap_type=g_type,
                subtype=s_type,
                span_text=span_text,
                start_char=s.get("start_char"),
                end_char=s.get("end_char"),
                severity=2,
                probability=float(s.get("confidence", 0.75)),
                explanation=expl,
                question=q,
            )
        )

    return gaps


# ============================================================================
# Baseline B3: Single Zero-Shot LLM (Span Grounded)
# ============================================================================

B3_PROMPT_TEMPLATE = """You are an expert requirements engineer analyzing software specifications for defects.
Requirement: "{text}"

Identify any defect gaps in this requirement sentence across three classes:
1. "ambiguity" (e.g. vague terms, quantifiers, ambiguous pronouns)
2. "incompleteness" (e.g. missing actor, missing condition, missing threshold, missing error handling)
3. "implicit" (e.g. unstated security, privacy, or safety constraints)

Output ONLY a valid JSON list of objects:
[
  {{
    "gap_type": "ambiguity" | "incompleteness" | "implicit",
    "subtype": "<specific subtype>",
    "span_text": "<exact substring from the requirement, or empty string if implicit>",
    "severity": 1 | 2 | 3
  }}
]
If there are no defects, output an empty list [].
Do NOT include markdown formatting or introductory text.
"""


def detect_b3_zeroshot_llm_gaps(
    text: str,
    llm_client: LLMClient | None = None,
    model_name: str = "qwen2.5:7b",
) -> list[CandidateGap]:
    """B3 Baseline: Single Zero-Shot LLM with strict span grounding.

    Per MASTER_SPEC.md Section 7:
    'LLM gaps whose span is not in the requirement are discarded.'
    """
    if llm_client is None:
        llm_client = OllamaClient(model=model_name)

    if not llm_client.is_available():
        return []

    prompt = B3_PROMPT_TEMPLATE.format(text=text.strip())
    try:
        raw = llm_client.generate(prompt=prompt, temperature=0.0)
    except Exception:
        return []

    # Clean JSON
    raw = raw.strip()
    match = re.search(r"(\[.*\])", raw, re.DOTALL)
    if match:
        raw = match.group(1).strip()

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
    except Exception:
        return []

    grounded_gaps: list[CandidateGap] = []
    text_lower = text.lower()

    for item in data:
        if not isinstance(item, dict):
            continue

        g_type = str(item.get("gap_type", "ambiguity")).strip().lower()
        if g_type not in {"ambiguity", "incompleteness", "implicit"}:
            continue

        s_type = str(item.get("subtype", "vague_term")).strip().lower()
        span = str(item.get("span_text", "")).strip()
        sev = int(item.get("severity", 2))
        sev = max(1, min(3, sev))

        # Strict Span Grounding Rule:
        # If gap has a span, it MUST exist verbatim in the requirement text.
        start_char, end_char = None, None
        if span:
            if span.lower() not in text_lower:
                # Discard ungrounded hallucinated span per Section 7
                continue
            bounds = _find_exact_phrase(text, span)
            if bounds:
                start_char, end_char = bounds
        elif g_type != "implicit":
            # Ambiguity and incompleteness must have a span
            continue

        expl, q = get_template_explanation_and_question(g_type, s_type, span)

        grounded_gaps.append(
            CandidateGap(
                gap_type=g_type,
                subtype=s_type,
                span_text=span,
                start_char=start_char,
                end_char=end_char,
                severity=sev,
                probability=0.70,
                explanation=expl,
                question=q,
            )
        )

    return grounded_gaps


# ============================================================================
# Baseline B4: Multi-LLM Majority Vote (Span Grounded)
# ============================================================================

def detect_b4_multi_llm_majority_gaps(
    text: str,
    clients: list[tuple[str, LLMClient]] | None = None,
) -> list[CandidateGap]:
    """B4 Baseline: Multi-LLM ensemble majority vote with span grounding.

    Models: qwen2.5:7b, llama3.1:8b, mistral:7b.
    Candidates require agreement from >= 2 models (matching gap_type and
    span token Jaccard >= 0.5 or containment).
    """
    if clients is None:
        clients = [
            ("qwen2.5:7b", OllamaClient(model="qwen2.5:7b")),
            ("llama3.1:8b", OllamaClient(model="llama3.1:8b")),
            ("mistral:7b", OllamaClient(model="mistral:7b")),
        ]

    # Gather predictions from each available model
    model_predictions: list[list[CandidateGap]] = []
    available_models: list[str] = []

    for name, client in clients:
        if client.is_available():
            available_models.append(name)
            preds = detect_b3_zeroshot_llm_gaps(text=text, llm_client=client, model_name=name)
            model_predictions.append(preds)

    # Quorum check: need at least 2 running models for a majority vote
    if len(model_predictions) < 2:
        return []

    # Majority voting aggregation
    all_candidates: list[tuple[CandidateGap, int]] = []
    for model_idx, preds in enumerate(model_predictions):
        for cand in preds:
            all_candidates.append((cand, model_idx))

    consensus_gaps: list[CandidateGap] = []
    used = set()

    for i, (cand_i, model_i) in enumerate(all_candidates):
        if i in used:
            continue

        agreeing_models = {model_i}
        matching_indices = [i]

        for j, (cand_j, model_j) in enumerate(all_candidates):
            if i == j or j in used or model_i == model_j:
                continue

            # Agreement criteria: same gap_type and span overlap
            if cand_i.gap_type == cand_j.gap_type:
                if cand_i.gap_type == "implicit":
                    agreeing_models.add(model_j)
                    matching_indices.append(j)
                elif cand_i.span_text and cand_j.span_text:
                    jacc = token_jaccard(cand_i.span_text, cand_j.span_text)
                    if (
                        jacc >= 0.5
                        or cand_i.span_text.lower() in cand_j.span_text.lower()
                        or cand_j.span_text.lower() in cand_i.span_text.lower()
                    ):
                        agreeing_models.add(model_j)
                        matching_indices.append(j)

        # Consensus condition: >= 2 models agree
        if len(agreeing_models) >= 2:
            consensus_gaps.append(cand_i)
            used.update(matching_indices)

    return consensus_gaps


# ============================================================================
# Architectural Ablations
# ============================================================================

def detect_ablation_no_4a(
    text: str,
    pipeline: Phase4Pipeline,
) -> list[CandidateGap]:
    """Ablation: Exclude Head 4a (Smell & Span Tagger). Runs 4b + 4c only."""
    frame = extract_requirement_frame(text)
    gaps_4b = pipeline.detect_head_4b_completeness(text, frame)
    gaps_4c = pipeline.detect_head_4c_implicit(text, frame)
    return gaps_4b + gaps_4c


def detect_ablation_no_4b(
    text: str,
    pipeline: Phase4Pipeline,
) -> list[CandidateGap]:
    """Ablation: Exclude Head 4b (Semantic Frame Completeness). Runs 4a + 4c only."""
    frame = extract_requirement_frame(text)
    gaps_4a = pipeline.detect_head_4a_ambiguity(text, frame)
    gaps_4c = pipeline.detect_head_4c_implicit(text, frame)
    return gaps_4a + gaps_4c


def detect_ablation_no_4c(
    text: str,
    pipeline: Phase4Pipeline,
) -> list[CandidateGap]:
    """Ablation: Exclude Head 4c (Implicit Domain Knowledge). Runs 4a + 4b only."""
    frame = extract_requirement_frame(text)
    gaps_4a = pipeline.detect_head_4a_ambiguity(text, frame)
    gaps_4b = pipeline.detect_head_4b_completeness(text, frame)
    return gaps_4a + gaps_4b


def detect_ablation_plain_union(
    text: str,
    pipeline: Phase4Pipeline,
) -> list[CandidateGap]:
    """Ablation: Plain union of Heads 4a, 4b, 4c WITHOUT Phase 5 MLP fusion scorer."""
    frame = extract_requirement_frame(text)
    return pipeline.detect_all_gaps(text, frame=frame)


# ============================================================================
# Question Formulation & Prompting Strategy Comparisons
# ============================================================================

def compare_question_formulation_strategies(
    gold_requirements: list[dict[str, Any]],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    """Ablation: Compare template-only vs. LLM question formulation quality.

    Metrics:
    - Compliance rate (exactly one '?' and <= 30 words)
    - Mean word count
    - Lexical uniqueness (unique words / total words)
    """
    template_questions: list[str] = []
    llm_questions: list[str] = []

    for req in gold_requirements:
        gap_type = req.get("gap_type", "ambiguity")
        subtype = req.get("subtype", "vague_term")
        span = req.get("span_text", "")

        # Template Question
        _expl, q_tmpl = get_template_explanation_and_question(gap_type, subtype, span)
        template_questions.append(q_tmpl)

        # LLM Question (if available)
        if llm_client and llm_client.is_available():
            prompt = f"Requirement: {req.get('text', '')}\nGap: {gap_type} ({subtype}) on '{span}'\nFormulate a clarification question:"
            try:
                raw = llm_client.generate(prompt)
                valid, _, q_llm, _ = validate_generation_output(raw)
                llm_questions.append(q_llm if valid else q_tmpl)
            except Exception:
                llm_questions.append(q_tmpl)

    def _stats(questions: list[str]) -> dict[str, float]:
        if not questions:
            return {"count": 0, "compliant_rate": 0.0, "mean_words": 0.0, "lexical_diversity": 0.0}
        compliant = sum(1 for q in questions if q.count("?") == 1 and len(q.split()) <= 30)
        word_counts = [len(q.split()) for q in questions]
        all_words = [w.lower() for q in questions for w in q.split()]
        unique_words = len(set(all_words))
        return {
            "count": len(questions),
            "compliant_rate": round(compliant / len(questions), 4),
            "mean_words": round(float(sum(word_counts) / len(word_counts)), 2),
            "lexical_diversity": round(unique_words / max(1, len(all_words)), 4),
        }

    return {
        "template_strategy": _stats(template_questions),
        "llm_strategy": _stats(llm_questions) if llm_questions else "LLM Offline / Unavailable",
    }


def compare_prompting_strategies(
    requirement_text: str,
    gap_type: str,
    subtype: str,
    span_text: str,
    llm_client: LLMClient | None = None,
) -> dict[str, str]:
    """Ablation: Compare generic prompting vs. gap-conditioned prompting."""
    generic_prompt = (
        f"Review this requirement sentence and ask a clarification question: \"{requirement_text}\""
    )
    conditioned_prompt = (
        f"Requirement: \"{requirement_text}\"\n"
        f"Defect: {gap_type} ({subtype}) on span '{span_text}'\n"
        "Ask a specific clarification question grounded in resolving this defect:"
    )

    if llm_client is None or not llm_client.is_available():
        return {
            "generic_response": "Offline: requires active LLM daemon",
            "conditioned_response": get_template_explanation_and_question(gap_type, subtype, span_text)[1],
            "status": "offline_fallback",
        }

    try:
        resp_gen = llm_client.generate(generic_prompt)
        resp_cond = llm_client.generate(conditioned_prompt)
        return {
            "generic_response": resp_gen.strip(),
            "conditioned_response": resp_cond.strip(),
            "status": "success",
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}


# ============================================================================
# Benchmark Runner: Reproduce results/summary.csv with One Command
# ============================================================================

def run_comparative_benchmark(
    gold_file: Path,
    output_summary_file: Path = Path("results/summary.csv"),
    smell_model_path: Path | None = None,
    span_model_path: Path | None = None,
    fusion_model_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Execute complete comparative evaluation across B1-B4 and all ablations.

    Outputs results/summary.csv strictly complying with MASTER_SPEC.md Section 11:
    'One command reproduces results/summary.csv'
    """
    output_summary_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load and gate gold data
    if not gold_file.exists():
        raise FileNotFoundError(f"Gold annotations not found: {gold_file.resolve()}")

    with gold_file.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Enforce Rule 4
    unverified = [r["req_id"] for r in rows if r.get("label_status") != "verified"]
    if unverified:
        raise ValueError(f"Benchmark refused: {len(unverified)} unverified rows.")

    req_gold: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        req_gold.setdefault(r["req_id"], []).append(r)

    # Initialize shared pipeline components
    smell_path = smell_model_path or Path("results/smell_classifier/smell_classifier.joblib")
    span_path = span_model_path or Path("results/span_tagger/span_tagger.joblib")

    pipeline = Phase4Pipeline(
        smell_model_path=smell_path if smell_path.exists() else None,
        span_model_path=span_path if span_path.exists() else None,
    )
    span_tagger = pipeline.span_tagger or (LinearSpanTagger.load(span_path) if span_path.exists() else None)

    fpath = fusion_model_path or Path("results/fusion_model/fusion_model.joblib")
    if fpath.exists():
        try:
            fusion_scorer = MLPFusionScorer.load(fpath)
        except Exception:
            fusion_scorer = HeuristicFusionScorer()
    else:
        fusion_scorer = HeuristicFusionScorer()

    # Check local Ollama availability
    ollama_ping = OllamaClient(timeout=1.0)
    ollama_available = ollama_ping.is_available()

    # Systems to evaluate
    systems: list[dict[str, Any]] = [
        {
            "name": "B1_rules",
            "type": "baseline",
            "fn": lambda text: detect_rule_gaps(text),
            "status": "evaluated",
        },
        {
            "name": "B2_span_alone",
            "type": "baseline",
            "fn": lambda text: detect_b2_span_alone_gaps(text, span_tagger=span_tagger),
            "status": "evaluated" if span_tagger else "model_missing",
        },
        {
            "name": "B3_zeroshot_llm",
            "type": "baseline",
            "fn": lambda text: detect_b3_zeroshot_llm_gaps(text, llm_client=ollama_ping),
            "status": "evaluated" if ollama_available else "offline_llm",
        },
        {
            "name": "B4_multi_llm",
            "type": "baseline",
            "fn": lambda text: detect_b4_multi_llm_majority_gaps(text),
            "status": "evaluated" if ollama_available else "offline_llm",
        },
        {
            "name": "Phase4_multi_head",
            "type": "architecture",
            "fn": lambda text: pipeline.detect_all_gaps(text),
            "status": "evaluated",
        },
        {
            "name": "Phase5_fusion",
            "type": "architecture",
            "fn": lambda text: deduplicate_and_rank_candidates(
                candidates=pipeline.detect_all_gaps(text),
                scorer=fusion_scorer,
                req_text=text,
            ),
            "status": "in_sample_resubstitution",
        },
        {
            "name": "Ablation_no_4a",
            "type": "ablation",
            "fn": lambda text: detect_ablation_no_4a(text, pipeline),
            "status": "evaluated",
        },
        {
            "name": "Ablation_no_4b",
            "type": "ablation",
            "fn": lambda text: detect_ablation_no_4b(text, pipeline),
            "status": "evaluated",
        },
        {
            "name": "Ablation_no_4c",
            "type": "ablation",
            "fn": lambda text: detect_ablation_no_4c(text, pipeline),
            "status": "evaluated",
        },
        {
            "name": "Ablation_plain_union",
            "type": "ablation",
            "fn": lambda text: detect_ablation_plain_union(text, pipeline),
            "status": "evaluated",
        },
    ]

    summary_records: list[dict[str, Any]] = []

    print("\n" + "=" * 70)
    print("Running CheckSense Phase 7 Comparative Baselines & Ablation Studies")
    print("=" * 70)

    for sys_info in systems:
        sys_name = sys_info["name"]
        status = sys_info["status"]
        print(f"[*] Evaluating {sys_name:<22} (status: {status})...")

        req_preds: dict[str, list[dict[str, Any]]] = {}
        for req_id, gold_items in req_gold.items():
            text = str(gold_items[0].get("text", "")).strip()
            if not text:
                continue

            if status == "offline_llm":
                req_preds[req_id] = []
            else:
                try:
                    cands = sys_info["fn"](text)
                    req_preds[req_id] = [c.to_dict() for c in cands]
                except Exception as e:
                    print(f"    [-] Error on {req_id}: {e}")
                    req_preds[req_id] = []

        # Run evaluation metrics
        report = evaluate_predictions(req_preds, req_gold, req_level=False)

        rec = {
            "system": sys_name,
            "type": sys_info["type"],
            "macro_f1": round(report.macro_f1, 4),
            "micro_f1": round(report.micro_f1, 4),
            "micro_f2": round(report.micro_f2, 4),
            "ambiguity_f1": round(report.per_class.get("ambiguity", {}).f1 if "ambiguity" in report.per_class else 0.0, 4),
            "incompleteness_f1": round(report.per_class.get("incompleteness", {}).f1 if "incompleteness" in report.per_class else 0.0, 4),
            "implicit_f1": round(report.per_class.get("implicit", {}).f1 if "implicit" in report.per_class else 0.0, 4),
            "has_gap_accuracy": round(report.has_gap_accuracy, 4),
            "clean_false_alarm_rate": round(report.false_alarm_rate_clean, 4),
            "n_predicted_gaps": report.n_pred_gaps,
            "status": status,
        }
        summary_records.append(rec)
        print(f"    -> Macro-F1: {rec['macro_f1']:.4f} | Micro-F1: {rec['micro_f1']:.4f} | Pred Gaps: {rec['n_predicted_gaps']}")

    # Write results/summary.csv
    fieldnames = [
        "system",
        "type",
        "macro_f1",
        "micro_f1",
        "micro_f2",
        "ambiguity_f1",
        "incompleteness_f1",
        "implicit_f1",
        "has_gap_accuracy",
        "clean_false_alarm_rate",
        "n_predicted_gaps",
        "status",
    ]

    with output_summary_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_records)

    print(f"\n[+] Comparative summary table successfully written to: {output_summary_file.resolve()}")

    # Save detailed JSON provenance beside it
    json_path = output_summary_file.parent / "comparative_metrics.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "gold_file": str(gold_file.resolve()),
                "ollama_available": ollama_available,
                "summary": summary_records,
            },
            f,
            indent=2,
        )

    # Run and log Question Formulation Ablation
    q_ablation = compare_question_formulation_strategies(rows, llm_client=ollama_ping if ollama_available else None)
    q_path = output_summary_file.parent / "ablation_questions.json"
    with q_path.open("w", encoding="utf-8") as f:
        json.dump(q_ablation, f, indent=2)

    return summary_records
