from .agreement import (
    compute_annotation_agreement,
    compute_cohens_kappa,
    compute_dataset_annotation_stats,
    interpret_kappa,
    load_pilot_expected_ids,
)
from .annotation import (
    ALL_SUBTYPES,
    ANNOTATION_COLUMNS,
    TAXONOMY,
    load_annotation_sheet,
    save_annotation_rows,
    validate_clarification_question,
    validate_gap_row,
    validate_requirement_annotations,
)
from .baseline import CandidateGap, detect_rule_gaps
from .eval import UnverifiedEvaluationError, run_evaluation
from .frame import RequirementFrame, extract_requirement_frame
from .fusion import (
    HeuristicFusionScorer,
    MLPFusionScorer,
    deduplicate_and_rank_candidates,
    extract_candidate_features,
    train_and_cross_validate_fusion_scorer,
)
from .generation import (
    enrich_candidates_with_questions,
    generate_gap_explanation_and_question,
    get_template_explanation_and_question,
    validate_generation_output,
)
from .heads import Phase4Pipeline, run_phase4_heads
from .llm import (
    LLMClient,
    LLMUnavailableError,
    MockLLMClient,
    OllamaClient,
    get_default_llm_client,
)
from .metrics import EvaluationReport, evaluate_predictions
from .refinement import (
    StakeholderAnswer,
    extract_numbers,
    refine_requirement,
    rule_based_refinement_edit,
    validate_numeric_preservation,
)
from .sample import (
    load_annotation_workflow_pool,
    partition_documents,
    sample_requirements,
)
from .smell import (
    TfidfSmellClassifier,
    load_arta_dataset,
    load_provisional_pilot_dataset,
    load_qure_dataset,
    train_and_cross_validate_smell_classifier,
)
from .span_tagger import (
    LinearSpanTagger,
    align_gold_spans_to_bio_tokens,
    load_bio_dataset_from_gold,
    train_and_evaluate_span_tagger,
)
from .version import __version__

__all__ = [
    "ALL_SUBTYPES",
    "ANNOTATION_COLUMNS",
    "CandidateGap",
    "EvaluationReport",
    "HeuristicFusionScorer",
    "LLMClient",
    "LLMUnavailableError",
    "LinearSpanTagger",
    "MLPFusionScorer",
    "MockLLMClient",
    "OllamaClient",
    "Phase4Pipeline",
    "RequirementFrame",
    "StakeholderAnswer",
    "TAXONOMY",
    "TfidfSmellClassifier",
    "UnverifiedEvaluationError",
    "__version__",
    "align_gold_spans_to_bio_tokens",
    "compute_annotation_agreement",
    "compute_cohens_kappa",
    "compute_dataset_annotation_stats",
    "deduplicate_and_rank_candidates",
    "detect_rule_gaps",
    "enrich_candidates_with_questions",
    "evaluate_predictions",
    "extract_candidate_features",
    "extract_numbers",
    "extract_requirement_frame",
    "generate_gap_explanation_and_question",
    "get_default_llm_client",
    "get_template_explanation_and_question",
    "interpret_kappa",
    "load_annotation_sheet",
    "load_annotation_workflow_pool",
    "load_arta_dataset",
    "load_bio_dataset_from_gold",
    "load_pilot_expected_ids",
    "load_provisional_pilot_dataset",
    "load_qure_dataset",
    "partition_documents",
    "refine_requirement",
    "rule_based_refinement_edit",
    "run_evaluation",
    "run_phase4_heads",
    "sample_requirements",
    "save_annotation_rows",
    "train_and_cross_validate_fusion_scorer",
    "train_and_cross_validate_smell_classifier",
    "train_and_evaluate_span_tagger",
    "validate_clarification_question",
    "validate_gap_row",
    "validate_generation_output",
    "validate_numeric_preservation",
    "validate_requirement_annotations",
]
