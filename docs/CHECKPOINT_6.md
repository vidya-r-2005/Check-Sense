# CheckSense Checkpoint 6: Phase 6 Explanation, Question Formulation & Requirement Refinement Engine

**Date:** 2026-10-28  
**Phase:** Phase 6  
**Status:** COMPLETED & VERIFIED (Offline Deterministic Guarantee Maintained)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. Executive Summary of Phase 6 Deliverables

In strict compliance with Section 5 (Stages 6–8), Section 8, and Section 11 of `MASTER_SPEC.md`, Phase 6 provides grounded explanation generation, structured clarification question formulation, stakeholder answer integration, and requirement refinement:

| Deliverable | Source Code / Artifacts | Status | Technical Details & Highlights |
|---|---|---|---|
| **LLM Provider Interface & Ollama Adapter** | [src/checksense/llm.py](../src/checksense/llm.py) | **VERIFIED** | `LLMClient` protocol with `OllamaClient` (`qwen2.5:7b` default on `http://localhost:11434`), configurable via environment variables, and `MockLLMClient` for deterministic testing. |
| **Grounded Question & Explanation Engine** | [src/checksense/generation.py](../src/checksense/generation.py) | **VERIFIED** | Prompts grounded strictly in requirement text and detected gap. Emits structured JSON containing `explanation` and `question`. |
| **Output Validation Guardrails** | [src/checksense/generation.py](../src/checksense/generation.py) | **VERIFIED** | Strict enforcement: JSON parseability, exactly one question mark `'?'` located at the end, and maximum length of 30 words. |
| **Deterministic Per-Subtype Templates** | [src/checksense/generation.py](../src/checksense/generation.py) | **VERIFIED** | Complete template coverage across all 9 taxonomy subtypes + implicit gaps. All template questions guaranteed valid ($=1$ `'?'`, $\le 30$ words). |
| **Offline / Unavailable LLM Guarantee** | [src/checksense/generation.py](../src/checksense/generation.py) | **VERIFIED** | Automatic fallback to deterministic templates whenever Ollama is offline, unreachable, or produces non-compliant output. |
| **Stakeholder Answer Container** | [src/checksense/refinement.py](../src/checksense/refinement.py) | **VERIFIED** | `StakeholderAnswer` dataclass capturing requirement ID, gap type, subtype, span, question, and stakeholder response. |
| **Strict Numeric Preservation Guardrail** | [src/checksense/refinement.py](../src/checksense/refinement.py) | **VERIFIED** | Mathematical number extraction: rejects any refinement that drops existing numbers or invents unauthorized numbers not in the requirement or answer. |
| **Requirement Refinement Engine** | [src/checksense/refinement.py](../src/checksense/refinement.py) | **VERIFIED** | Rewrites requirements using LLM, with automatic fallback to deterministic rule-based grammar edits on validation failure or missing LLM. |
| **Automated Test Suite** | [tests/test_phase6.py](../tests/test_phase6.py) | **VERIFIED** | 24 unit and regression tests covering Ollama availability, validation constraints, numeric preservation, rule edits, and offline behavior. |

---

## 2. Architecture & Algorithmic Workflow

```
   Candidate Gap (Ranked from Phase 5)
                 │
                 ▼
     [ LLM Available & Reachable? ]
            /            \
       YES /              \ NO (Offline / Fallback)
          ▼                ▼
   [ Grounded LLM Prompt ] [ Deterministic Template ]
   (qwen2.5:7b on Ollama)   (Guaranteed 1 '?', <=30 words)
          │                ▲
          ▼                │
   [ Validation Check ]    │
   - Parseable JSON        │
   - Exactly 1 '?' at end  │
   - <= 30 words           │
          │                │
     FAIL └────────────────┘
          │ PASS
          ▼
   Validated (Explanation, Clarification Question)
                 │
                 ▼
   [ Interactive Stakeholder Clarification Answer ]
                 │
                 ▼
   [ Requirement Refinement Engine ]
            /            \
       YES /              \ NO / Failed Guardrail
          ▼                ▼
   [ LLM Refinement ]   [ Rule-Based Fallback Edit ]
   - Normative check    - Vague span substitution
   - Strict numeric     - Conditional clause append
     preservation       - Error handling append
     (no dropped or     - Actor role injection
      invented nums)
          │                ▲
     FAIL └────────────────┘
          │ PASS
          ▼
   Final Refined Functional Requirement Sentence
```

### 2.1 Question Formatting Contract
Per `MASTER_SPEC.md` Section 5.6 and Section 8, every question must strictly adhere to the following contract:
1. Must end with a question mark (`'?'`).
2. Must contain exactly one question mark in total (`question.count('?') == 1`).
3. Must not exceed 30 words (`len(question.split()) <= 30`).
4. Must not propose speculative answers or hallucinate technical specifications.

### 2.2 Numeric Preservation Guardrail
Per `MASTER_SPEC.md` Section 5.8:
$$\text{Numbers}_{\text{refined}} \supseteq \text{Numbers}_{\text{original}} \quad \text{and} \quad \text{Numbers}_{\text{refined}} \subseteq (\text{Numbers}_{\text{original}} \cup \text{Numbers}_{\text{answer}})$$
- **Zero Dropped Numbers:** If any number from the original requirement is omitted in the rewrite, the LLM output is rejected immediately.
- **Zero Invented Numbers:** If any number appears in the rewrite that was not present in the original sentence or stakeholder answer, the rewrite is rejected immediately.
- On rejection, CheckSense executes the deterministic rule-based fallback edit.

---

## 3. Acceptance Criteria Verification

| Section 11 Requirement | Specified Condition | Empirical Result | Status |
|---|---|---|---|
| **Validation Tests** | Validation tests pass for JSON parsing, question formatting, and numeric preservation. | 24/24 unit tests passed in `tests/test_phase6.py`. | **PASSED** |
| **Offline Independence** | Works with deterministic templates when no local LLM is installed or running. | Verified offline: returns valid templates and rule edits without crashing. | **PASSED** |
| **Full Suite Integrity** | Regression-free across all existing components (Phases 0–5). | All 121 tests pass across `tests/`. | **PASSED** |

---

## 4. Reproducible Execution & Usage

### 1. Offline / Default Generation (Template Fallback):
```python
from checksense import (
    CandidateGap,
    enrich_candidates_with_questions,
    refine_requirement,
    StakeholderAnswer,
)

# 1. Enrich candidate with explanation and question
cand = CandidateGap(
    gap_type="ambiguity",
    subtype="vague_quantifier",
    span_text="several",
    start_char=20,
    end_char=27,
    severity=2,
    probability=0.85,
    explanation="",
    question="",
)
enriched = enrich_candidates_with_questions([cand], "The system shall process several transactions.")
print(enriched[0].question)
# Output: "What is the complete enumeration or exact numerical bound intended by 'several'?"

# 2. Refine requirement using stakeholder answer
ans = StakeholderAnswer(
    req_id="REQ_1",
    gap_type="ambiguity",
    subtype="vague_quantifier",
    span_text="several",
    question=enriched[0].question,
    answer="at least 50",
)
refined, method = refine_requirement(
    original_text="The system shall process several transactions.",
    stakeholder_answer=ans,
)
print(f"Refined: {refined} (Method: {method})")
# Output: "The system shall process at least 50 transactions. (Method: rule_fallback)"
```

### 2. Using Local Ollama LLM (`qwen2.5:7b`):
```python
from checksense import OllamaClient, refine_requirement

llm = OllamaClient(host="http://localhost:11434", model="qwen2.5:7b")
# If Ollama daemon is running, LLM will be used; if offline, automatically falls back to templates
```

### 3. Run Automated Phase 6 Test Suite:
```powershell
pytest tests/test_phase6.py -v
```

