"""
pipeline/config.py

Central config for paths and constants shared across all phases.
Nothing phase-specific here beyond directory layout — keeps phase1/2/3
scripts free of hardcoded paths.
"""

from pathlib import Path

PROJECT_ROOT = Path(r"C:\education\final year project\project")

TRIPOSR_DIR = PROJECT_ROOT / "TripoSR"
TRIPOSR_RUN_SCRIPT = TRIPOSR_DIR / "run.py"

DATA_DIR = PROJECT_ROOT / "data"
INPUTS_DIR = DATA_DIR / "inputs"
OUTPUTS_DIR = DATA_DIR / "outputs"

DECIMATION_RATIOS = [0.5, 0.2, 0.1, 0.05]


def run_dir(run_id: str) -> Path:
    return OUTPUTS_DIR / run_id


def phase1_dir(run_id: str) -> Path:
    """High-poly TripoSR output for this run."""
    return run_dir(run_id) / "phase1_highpoly"


def phase2_dir(run_id: str) -> Path:
    """Parent dir holding ratio_X subfolders of low-poly meshes."""
    return run_dir(run_id) / "phase2_lowpoly"


def phase2_ratio_dir(run_id: str, ratio: float) -> Path:
    return phase2_dir(run_id) / f"ratio_{ratio}"


def phase3_dir(run_id: str) -> Path:
    """Evaluation renders + metrics for this run."""
    return run_dir(run_id) / "phase3_eval"


def input_image_path(image_name: str) -> Path:
    """image_name e.g. 'chair.png' -> data/inputs/chair.png"""
    return INPUTS_DIR / image_name