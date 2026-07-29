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

# --- Blender (Phase 3 render harness) ---
# EDIT THESE TWO to match your machine.
# Find your Blender path with: (Get-Command blender).Source in PowerShell,
# or the full path to blender.exe if it's not on PATH (e.g. under
# "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe").
BLENDER_EXECUTABLE = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")

# Path to the render_views.py script (Phase 3).
RENDER_SCRIPT_PATH = PROJECT_ROOT / "pipeline" / "phase3_render" / "render_views.py"

RENDER_VIEWS = 12
RENDER_RESOLUTION = 1024


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


def phase3_renders_dir(run_id: str) -> Path:
    """Blender render output (view_XX.png per subfolder: highpoly/, ratio_X/)."""
    return run_dir(run_id) / "phase3_renders"


def phase3_evaluate_dir(run_id: str) -> Path:
    """Phase 4 evaluate_equalness() JSON output (ratio_X.json, summary.json)."""
    return run_dir(run_id) / "phase3_evaluate"


def phase3_dir(run_id: str) -> Path:
    """DEPRECATED alias kept for backward compatibility with any existing
    scripts that still call this -- prefer phase3_renders_dir /
    phase3_evaluate_dir directly for new code, since renders and eval JSON
    are now kept in separate subfolders rather than one combined dir."""
    return run_dir(run_id) / "phase3_eval"


def input_image_path(image_name: str) -> Path:
    """image_name e.g. 'chair.png' -> data/inputs/chair.png"""
    return INPUTS_DIR / image_name