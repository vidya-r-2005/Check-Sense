from .agreement import (
    compute_annotation_agreement,
    compute_cohens_kappa,
    compute_dataset_annotation_stats,
    interpret_kappa,
)
from .baseline import CandidateGap, detect_rule_gaps
from .eval import UnverifiedEvaluationError, run_evaluation
from .frame import RequirementFrame, extract_requirement_frame
from .metrics import EvaluationReport, evaluate_predictions
from .sample import partition_documents, sample_requirements
from .version import __version__

__all__ = [
    "CandidateGap",
    "EvaluationReport",
    "RequirementFrame",
    "UnverifiedEvaluationError",
    "__version__",
    "compute_annotation_agreement",
    "compute_cohens_kappa",
    "compute_dataset_annotation_stats",
    "detect_rule_gaps",
    "evaluate_predictions",
    "extract_requirement_frame",
    "interpret_kappa",
    "partition_documents",
    "run_evaluation",
    "sample_requirements",
]

