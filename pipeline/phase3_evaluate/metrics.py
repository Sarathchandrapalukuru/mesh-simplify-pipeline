"""
Phase 3 Evaluate: Quality evaluation harness (metrics.py).

Compares a decimated (low-poly) mesh + its rendered views against the
high-poly reference mesh + reference renders, and produces a structured
score dict via evaluate_equalness().

Geometric metrics: Chamfer distance, Hausdorff distance (both computed on
surface-sampled point clouds, not raw vertices -- vertex-only comparison is
biased because decimation changes vertex density/location non-uniformly).

Visual metrics: PSNR, SSIM averaged over the 8 matched-camera renders.

Usage:
    from pipeline.metrics import evaluate_equalness

    result = evaluate_equalness(
        ref_mesh_path="data/outputs/chair_run1/phase1_highpoly/mesh.obj",
        test_mesh_path="data/outputs/chair_run1/phase2_lowpoly/ratio_0.1/mesh.obj",
        ref_render_dir="data/outputs/chair_run1/phase3_renders/highpoly/",
        test_render_dir="data/outputs/chair_run1/phase3_renders/ratio_0.1/",
        ratio=0.1,
    )
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh
from scipy.spatial import cKDTree
from skimage.io import imread
from skimage.metrics import peak_signal_noise_ratio as sk_psnr
from skimage.metrics import structural_similarity as sk_ssim


# ---------------------------------------------------------------------------
# Thresholds -- tune these against your own data once you have a handful of
# ratios evaluated. Hausdorff is normalized by bbox diagonal so it's scale
# independent; Chamfer is reported both raw and normalized.
# ---------------------------------------------------------------------------

@dataclass
class EqualnessThresholds:
    max_chamfer_norm: float = 0.01      # mean NN dist / bbox diagonal
    max_hausdorff_norm: float = 0.05    # max NN dist / bbox diagonal
    min_psnr: float = 28.0              # dB, averaged over views
    min_ssim: float = 0.90              # averaged over views


DEFAULT_THRESHOLDS = EqualnessThresholds()


# ---------------------------------------------------------------------------
# Geometric metrics
# ---------------------------------------------------------------------------

def sample_surface_points(mesh_path: str, n_points: int = 20000, seed: int = 0) -> np.ndarray:
    """Uniformly sample points on the mesh surface (area-weighted)."""
    mesh = trimesh.load(mesh_path, force="mesh", process=False)
    rng = np.random.default_rng(seed)
    points, _ = trimesh.sample.sample_surface(mesh, n_points, seed=rng)
    return np.asarray(points)


def bbox_diagonal(mesh_path: str) -> float:
    mesh = trimesh.load(mesh_path, force="mesh", process=False)
    return float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0]))


def chamfer_distance(points_a: np.ndarray, points_b: np.ndarray) -> float:
    """Symmetric mean nearest-neighbor distance (not squared -- easier to
    reason about in the same units as the mesh)."""
    tree_a = cKDTree(points_a)
    tree_b = cKDTree(points_b)
    d_ab, _ = tree_b.query(points_a, k=1)
    d_ba, _ = tree_a.query(points_b, k=1)
    return float((d_ab.mean() + d_ba.mean()) / 2.0)


def hausdorff_distance(points_a: np.ndarray, points_b: np.ndarray) -> float:
    """Symmetric Hausdorff distance: worst-case nearest-neighbor gap.
    This is what catches localized blowups (e.g. a UV seam collapsing into
    a spike) that Chamfer's averaging hides."""
    tree_a = cKDTree(points_a)
    tree_b = cKDTree(points_b)
    d_ab, _ = tree_b.query(points_a, k=1)
    d_ba, _ = tree_a.query(points_b, k=1)
    return float(max(d_ab.max(), d_ba.max()))


def geometric_metrics(ref_mesh_path: str, test_mesh_path: str, n_points: int = 20000) -> dict:
    ref_pts = sample_surface_points(ref_mesh_path, n_points)
    test_pts = sample_surface_points(test_mesh_path, n_points)
    diag = bbox_diagonal(ref_mesh_path)

    chamfer = chamfer_distance(ref_pts, test_pts)
    hausdorff = hausdorff_distance(ref_pts, test_pts)

    return {
        "chamfer_raw": chamfer,
        "chamfer_norm": chamfer / diag,
        "hausdorff_raw": hausdorff,
        "hausdorff_norm": hausdorff / diag,
        "bbox_diagonal": diag,
    }


# ---------------------------------------------------------------------------
# Visual metrics
# ---------------------------------------------------------------------------

def _load_rgb(path: Path) -> np.ndarray:
    img = imread(str(path))
    if img.shape[-1] == 4:  # drop alpha -- renders are RGBA from Blender
        img = img[..., :3]
    return img


def visual_metrics(ref_render_dir: str, test_render_dir: str, n_views: int = 8,
                    pattern: str = "view_{:02d}.png") -> dict:
    """Averages PSNR/SSIM across matched-index view pairs. Filenames in both
    dirs must follow the same indexing convention from your Phase 3 camera rig."""
    ref_dir = Path(ref_render_dir)
    test_dir = Path(test_render_dir)

    psnr_vals, ssim_vals = [], []
    per_view = []

    for i in range(n_views):
        fname = pattern.format(i)
        ref_img = _load_rgb(ref_dir / fname)
        test_img = _load_rgb(test_dir / fname)

        if ref_img.shape != test_img.shape:
            raise ValueError(
                f"Render size mismatch on {fname}: {ref_img.shape} vs {test_img.shape}. "
                "Check the Phase 3 camera rig / resolution config matches for both runs."
            )

        p = sk_psnr(ref_img, test_img, data_range=255)
        s = sk_ssim(ref_img, test_img, data_range=255, channel_axis=-1)

        psnr_vals.append(p)
        ssim_vals.append(s)
        per_view.append({"view": i, "psnr": float(p), "ssim": float(s)})

    return {
        "psnr_mean": float(np.mean(psnr_vals)),
        "psnr_min": float(np.min(psnr_vals)),
        "ssim_mean": float(np.mean(ssim_vals)),
        "ssim_min": float(np.min(ssim_vals)),
        "per_view": per_view,
    }


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def evaluate_equalness(
    ref_mesh_path: str,
    test_mesh_path: str,
    ref_render_dir: str,
    test_render_dir: str,
    ratio: float,
    n_points: int = 20000,
    n_views: int = 8,
    thresholds: EqualnessThresholds = DEFAULT_THRESHOLDS,
    save_json: Optional[str] = None,
) -> dict:
    """Runs the full geometric + visual comparison for one decimation ratio
    and returns a structured score dict, e.g.:

    {
        "ratio": 0.1,
        "geometry": {...},
        "visual": {...},
        "pass": True,
        "failures": [],
    }
    """
    geo = geometric_metrics(ref_mesh_path, test_mesh_path, n_points=n_points)
    vis = visual_metrics(ref_render_dir, test_render_dir, n_views=n_views)

    failures = []
    if geo["chamfer_norm"] > thresholds.max_chamfer_norm:
        failures.append(
            f"chamfer_norm {geo['chamfer_norm']:.4f} > {thresholds.max_chamfer_norm}"
        )
    if geo["hausdorff_norm"] > thresholds.max_hausdorff_norm:
        failures.append(
            f"hausdorff_norm {geo['hausdorff_norm']:.4f} > {thresholds.max_hausdorff_norm}"
        )
    if vis["psnr_mean"] < thresholds.min_psnr:
        failures.append(f"psnr_mean {vis['psnr_mean']:.2f} < {thresholds.min_psnr}")
    if vis["ssim_mean"] < thresholds.min_ssim:
        failures.append(f"ssim_mean {vis['ssim_mean']:.4f} < {thresholds.min_ssim}")

    result = {
        "ratio": ratio,
        "geometry": geo,
        "visual": vis,
        "pass": len(failures) == 0,
        "failures": failures,
        "thresholds": asdict(thresholds),
    }

    if save_json:
        Path(save_json).parent.mkdir(parents=True, exist_ok=True)
        with open(save_json, "w") as f:
            json.dump(result, f, indent=2)

    return result


def evaluate_all_ratios(
    run_dir: str,
    ratios: list[float] = (0.5, 0.2, 0.1, 0.05),
    n_points: int = 20000,
    n_views: int = 8,
    thresholds: EqualnessThresholds = DEFAULT_THRESHOLDS,
) -> dict:
    """Convenience wrapper matching your directory convention:
    data/outputs/<run_id>/phase1_highpoly/, phase2_lowpoly/ratio_X/,
    phase3_renders/highpoly/, phase3_renders/ratio_X/

    Returns {ratio: result_dict} and writes each result + a combined
    summary JSON into phase3_evaluate/ under run_dir.
    """
    run_dir = Path(run_dir)
    ref_mesh = run_dir / "phase1_highpoly" / "mesh.obj"
    ref_renders = run_dir / "phase3_renders" / "highpoly"
    eval_dir = run_dir / "phase3_evaluate"

    results = {}
    for ratio in ratios:
        test_mesh = run_dir / "phase2_lowpoly" / f"ratio_{ratio}" / "mesh.obj"
        test_renders = run_dir / "phase3_renders" / f"ratio_{ratio}"

        result = evaluate_equalness(
            ref_mesh_path=str(ref_mesh),
            test_mesh_path=str(test_mesh),
            ref_render_dir=str(ref_renders),
            test_render_dir=str(test_renders),
            ratio=ratio,
            n_points=n_points,
            n_views=n_views,
            thresholds=thresholds,
            save_json=str(eval_dir / f"ratio_{ratio}.json"),
        )
        results[ratio] = result
        status = "PASS" if result["pass"] else "FAIL"
        print(f"[ratio {ratio}] {status}  "
              f"chamfer_norm={result['geometry']['chamfer_norm']:.4f}  "
              f"hausdorff_norm={result['geometry']['hausdorff_norm']:.4f}  "
              f"psnr={result['visual']['psnr_mean']:.2f}  "
              f"ssim={result['visual']['ssim_mean']:.4f}")

    eval_dir.mkdir(parents=True, exist_ok=True)
    with open(eval_dir / "summary.json", "w") as f:
        json.dump({str(k): v for k, v in results.items()}, f, indent=2)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 3 Evaluate: metrics harness")
    parser.add_argument("run_dir", help="e.g. data/outputs/chair_run1")
    parser.add_argument("--ratios", nargs="+", type=float, default=[0.5, 0.2, 0.1, 0.05])
    parser.add_argument("--n_points", type=int, default=20000)
    parser.add_argument("--n_views", type=int, default=8)
    args = parser.parse_args()

    evaluate_all_ratios(args.run_dir, ratios=args.ratios,
                         n_points=args.n_points, n_views=args.n_views)