"""
pipeline/run_all.py

Phase 6: end-to-end orchestrator for one run_id, chaining Phase 2 (decimate)
-> Phase 3 (Blender render) -> Phase 4 (evaluate_equalness), with:

  - Adaptive ratio deepening: starts at [0.5, 0.2, 0.1, 0.05]. If the last
    ratio in the schedule still produced a DIFFERENT mesh than the one
    before it (i.e. face count changed -> compression is still "working"),
    keep going deeper (ratio *= DEEPEN_FACTOR) until either a plateau is
    hit or MIN_RATIO / MAX_EXTRA_STEPS is reached.
  - Plateau detection: if a ratio's decimation output has the SAME
    final_faces as the previous accepted ratio, it's a duplicate mesh.
    We skip Phase 3/4 for it entirely (no point re-rendering + re-scoring
    an identical mesh) and record it as plateaued, then STOP deepening.
  - Failure isolation: any exception in Phase 2/3/4 for a given ratio is
    caught, printed as a warning, and the ratio is marked failed in the
    summary -- the run continues to the next ratio rather than aborting.

Callable as a plain function so it can be looped over many input images
without shelling out per-call:

    from pipeline.run_all import run_pipeline
    for run_id in ["chair_run1", "lamp_run1", "mug_run1"]:
        summary = run_pipeline(run_id)

Assumes Phase 1 (TripoSR reconstruction) has already been run for run_id
and <phase1_dir>/mesh.obj + texture.png exist -- Phase 1 is frozen vendor
code invoked separately, not chained here.
"""

from __future__ import annotations

import json
import subprocess
import traceback
from pathlib import Path
from typing import Optional

from pipeline import config
from pipeline.phase2_remesh.remesh import decimate_mesh
from pipeline.phase3_evaluate.metrics import evaluate_equalness, DEFAULT_THRESHOLDS, EqualnessThresholds


# ---------------------------------------------------------------------------
# Adaptive-depth search parameters
# ---------------------------------------------------------------------------

BASE_RATIOS = [0.5, 0.2, 0.1, 0.05]
DEEPEN_FACTOR = 0.5      # each extra step goes to ratio * 0.5 (e.g. 0.05 -> 0.025 -> 0.0125 ...)
MIN_RATIO = 0.005        # stop deepening once ratio would drop below this
MAX_EXTRA_STEPS = 5      # hard cap on how many extra steps beyond BASE_RATIOS we'll try


def _warn(msg: str) -> None:
    print(f"[WARNING] {msg}")


def _run_phase3_render(run_dir: Path, views: int = 12, resolution: int = 1024) -> None:
    """Shells out to Blender headless for the render step (Phase 3 must run
    inside Blender's own Python, so it can't be imported directly)."""
    cmd = [
        str(config.BLENDER_EXECUTABLE),
        "--background",
        "--python", str(config.RENDER_SCRIPT_PATH),
        "--",
        "--run-dir", str(run_dir),
        "--views", str(views),
        "--resolution", str(resolution),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Blender render failed (exit {result.returncode}):\n"
            f"stdout tail: {result.stdout[-2000:]}\n"
            f"stderr tail: {result.stderr[-2000:]}"
        )


def run_pipeline(
    run_id: str,
    base_ratios: list[float] = BASE_RATIOS,
    deepen_factor: float = DEEPEN_FACTOR,
    min_ratio: float = MIN_RATIO,
    max_extra_steps: int = MAX_EXTRA_STEPS,
    render_views: int = 12,
    render_resolution: int = 1024,
    thresholds: EqualnessThresholds = DEFAULT_THRESHOLDS,
    n_points: int = 20000,
) -> dict:
    """
    Runs Phase 2 -> 3 -> 4 for one run_id, adaptively deepening the ratio
    schedule past base_ratios as long as compression is still "working"
    (face count still changing vs. the previous ratio), and stopping the
    instant it plateaus (a ratio yields the same final_faces as before).

    Returns a summary dict:
        {
            "run_id": run_id,
            "ratios_run": [...],        # ratios actually decimated (Phase 2 attempted)
            "ratios_evaluated": [...],  # ratios that got Phase 3/4 (non-plateaued, no errors)
            "plateau_at": float | None, # ratio where plateau was first detected
            "plateau_face_count": int | None,
            "results": {ratio: {...}},  # per-ratio stats + eval result, or {"error": ...}
        }
    """
    phase1_dir = config.phase1_dir(run_id)
    phase2_dir = config.phase2_dir(run_id)
    run_dir = config.run_dir(run_id)  # top-level data/outputs/<run_id>
    renders_dir = config.phase3_renders_dir(run_id)
    evaluate_dir = config.phase3_evaluate_dir(run_id)

    input_obj = phase1_dir / "mesh.obj"
    if not input_obj.exists():
        _warn(f"[{run_id}] Phase 1 output not found at {input_obj} -- skipping run entirely.")
        return {
            "run_id": run_id,
            "ratios_run": [],
            "ratios_evaluated": [],
            "plateau_at": None,
            "plateau_face_count": None,
            "results": {},
            "error": f"missing phase1 output: {input_obj}",
        }

    results: dict = {}
    ratios_run: list = []
    ratios_evaluated: list = []
    plateau_at: Optional[float] = None
    plateau_face_count: Optional[int] = None

    prev_final_faces: Optional[int] = None
    ratio_queue = list(base_ratios)
    extra_steps_taken = 0

    i = 0
    while i < len(ratio_queue):
        ratio = ratio_queue[i]
        ratios_run.append(ratio)
        print(f"\n[Phase6] === run_id={run_id}  ratio={ratio} ===")

        # ---------------- Phase 2: decimate ----------------
        try:
            ratio_dir = phase2_dir / f"ratio_{ratio}"
            output_obj = ratio_dir / "mesh.obj"
            stats = decimate_mesh(input_obj, ratio, output_obj)
            print(f"  [Phase2] final_faces={stats['final_faces']} "
                  f"(target {stats['target_face_num']}, actual_ratio={stats['actual_ratio']})")
        except Exception as e:
            _warn(f"[{run_id}] Phase 2 failed for ratio={ratio}: {e}")
            traceback.print_exc()
            results[ratio] = {"error": f"phase2_failed: {e}"}
            i += 1
            continue

        final_faces = stats["final_faces"]

        # ---------------- Plateau check ----------------
        if prev_final_faces is not None and final_faces == prev_final_faces:
            print(f"  [Phase6] PLATEAU detected: ratio={ratio} produced the same "
                  f"final_faces ({final_faces}) as the previous ratio. "
                  f"Skipping Phase 3/4 (identical mesh) and stopping the search.")
            plateau_at = ratio
            plateau_face_count = final_faces
            results[ratio] = {"phase2": stats, "plateaued": True, "evaluated": False}
            break  # stop entirely -- deeper ratios would just re-plateau too

        prev_final_faces = final_faces

        # ---------------- Phase 3: render (only reached if not plateaued) ----------------
        try:
            _run_phase3_render(run_dir, views=render_views, resolution=render_resolution)
        except Exception as e:
            _warn(f"[{run_id}] Phase 3 render failed for ratio={ratio}: {e}")
            traceback.print_exc()
            results[ratio] = {"phase2": stats, "error": f"phase3_failed: {e}"}
            i += 1
            continue

        # ---------------- Phase 4: evaluate ----------------
        try:
            eval_result = evaluate_equalness(
                ref_mesh_path=str(phase1_dir / "mesh.obj"),
                test_mesh_path=str(output_obj),
                ref_render_dir=str(renders_dir / "highpoly"),
                test_render_dir=str(renders_dir / f"ratio_{ratio}"),
                ratio=ratio,
                n_points=n_points,
                n_views=min(render_views, 8),
                thresholds=thresholds,
                save_json=str(evaluate_dir / f"ratio_{ratio}.json"),
            )
            print(f"  [Phase4] pass={eval_result['pass']}  failures={eval_result['failures']}")
        except Exception as e:
            _warn(f"[{run_id}] Phase 4 evaluation failed for ratio={ratio}: {e}")
            traceback.print_exc()
            results[ratio] = {"phase2": stats, "error": f"phase4_failed: {e}"}
            i += 1
            continue

        results[ratio] = {"phase2": stats, "evaluation": eval_result, "evaluated": True}
        ratios_evaluated.append(ratio)

        # ---------------- Decide whether to deepen ----------------
        # Only deepen once, at the moment we're about to fall off the end
        # of the current queue -- if the run has already queued a deeper
        # ratio (from an earlier iteration), don't queue another one until
        # we actually get there.
        is_last_in_queue = (i == len(ratio_queue) - 1)
        if is_last_in_queue and extra_steps_taken < max_extra_steps:
            deeper = round(ratio * deepen_factor, 6)
            if deeper >= min_ratio:
                print(f"  [Phase6] ratio={ratio} still compressing (no plateau yet) -- "
                      f"deepening to {deeper}")
                ratio_queue.append(deeper)
                extra_steps_taken += 1
            else:
                print(f"  [Phase6] ratio={ratio} still compressing, but next step "
                      f"({deeper}) is below min_ratio={min_ratio} -- stopping search.")

        i += 1

    summary = {
        "run_id": run_id,
        "ratios_run": ratios_run,
        "ratios_evaluated": ratios_evaluated,
        "plateau_at": plateau_at,
        "plateau_face_count": plateau_face_count,
        "results": results,
    }

    summary_path = run_dir / "phase6_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n[Phase6] Summary written to {summary_path}")

    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 6: full pipeline orchestrator")
    parser.add_argument("--run_id", type=str, required=True)
    parser.add_argument("--base_ratios", type=float, nargs="+", default=BASE_RATIOS)
    parser.add_argument("--min_ratio", type=float, default=MIN_RATIO)
    parser.add_argument("--max_extra_steps", type=int, default=MAX_EXTRA_STEPS)
    args = parser.parse_args()

    run_pipeline(
        run_id=args.run_id,
        base_ratios=args.base_ratios,
        min_ratio=args.min_ratio,
        max_extra_steps=args.max_extra_steps,
    )