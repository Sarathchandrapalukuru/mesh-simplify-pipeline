# # """
# # pipeline/phase1_reconstruct/reconstruct.py

# # Wraps TripoSR's own run.py as a subprocess call. TripoSR stays frozen and
# # untouched (aside from the two bake_texture.py patches already applied) —
# # this script does NOT reimplement model loading, it just drives the CLI
# # and reorganizes the output into pipeline's data/outputs/<run_id>/ layout.

# # TripoSR's run.py writes output as:
# #     <output-dir>/0/mesh.obj
# #     <output-dir>/0/texture.png
# #     <output-dir>/0/input.png     (or similar, exact name may vary)

# # This wrapper runs it into a temp/staging output dir, then moves the
# # contents into data/outputs/<run_id>/phase1_highpoly/ for the rest of
# # the pipeline to consume.
# # """

# # import shutil
# # import subprocess
# # import sys
# # from pathlib import Path

# # from pipeline import config


# # def run_triposr(input_image: Path, staging_dir: Path, bake_texture: bool = True) -> Path:
# #     """
# #     Calls TripoSR/run.py as a subprocess. Returns the path to the
# #     subfolder (usually '0') containing mesh.obj + texture.png.
# #     """
# #     staging_dir.mkdir(parents=True, exist_ok=True)

# #     cmd = [
# #         sys.executable, str(config.TRIPOSR_RUN_SCRIPT),
# #         str(input_image),
# #         "--output-dir", str(staging_dir),
# #     ]
# #     if bake_texture:
# #         cmd.append("--bake-texture")

# #     print(f"[Phase1] Running: {' '.join(cmd)}")
# #     result = subprocess.run(cmd, cwd=str(config.TRIPOSR_DIR), capture_output=True, text=True)

# #     if result.returncode != 0:
# #         print(result.stdout)
# #         print(result.stderr)
# #         raise RuntimeError(f"TripoSR run.py failed with exit code {result.returncode}")

# #     print(result.stdout)

# #     # TripoSR writes into a numbered subfolder (typically '0') under output-dir
# #     subfolders = [p for p in staging_dir.iterdir() if p.is_dir()]
# #     if not subfolders:
# #         raise FileNotFoundError(f"No output subfolder found in {staging_dir}")
# #     return subfolders[0]


# # def organize_output(triposr_output_subdir: Path, run_id: str) -> Path:
# #     """
# #     Moves mesh.obj + texture.png (+ input image if present) from
# #     TripoSR's raw output subfolder into data/outputs/<run_id>/phase1_highpoly/.
# #     """
# #     target_dir = config.phase1_dir(run_id)
# #     target_dir.mkdir(parents=True, exist_ok=True)

# #     expected_files = ["mesh.obj", "texture.png"]
# #     for fname in expected_files:
# #         src = triposr_output_subdir / fname
# #         if not src.exists():
# #             raise FileNotFoundError(f"Expected {fname} not found in {triposr_output_subdir}")
# #         shutil.copy2(src, target_dir / fname)

# #     # copy input image too if TripoSR saved one alongside
# #     for candidate in triposr_output_subdir.glob("input*.png"):
# #         shutil.copy2(candidate, target_dir / candidate.name)

# #     print(f"[Phase1] Output organized into: {target_dir}")
# #     return target_dir


# # def run_phase1(input_image_name: str, run_id: str, bake_texture: bool = True) -> Path:
# #     input_image = config.input_image_path(input_image_name)
# #     if not input_image.exists():
# #         raise FileNotFoundError(f"Input image not found: {input_image}")

# #     staging_dir = config.run_dir(run_id) / "_phase1_staging"
# #     output_subdir = run_triposr(input_image, staging_dir, bake_texture=bake_texture)
# #     final_dir = organize_output(output_subdir, run_id)

# #     # clean up staging dir now that files are copied into place
# #     shutil.rmtree(staging_dir, ignore_errors=True)

# #     return final_dir


# # if __name__ == "__main__":
# #     import argparse

# #     parser = argparse.ArgumentParser(description="Phase 1: run frozen TripoSR reconstruction")
# #     parser.add_argument("--input_image", type=str, required=True,
# #                          help="Filename inside data/inputs/, e.g. 'chair.png'")
# #     parser.add_argument("--run_id", type=str, required=True,
# #                          help="Identifier for this run, e.g. 'chair_run1'")
# #     parser.add_argument("--no_bake_texture", action="store_true",
# #                          help="Disable --bake-texture flag when calling run.py")
# #     args = parser.parse_args()

# #     out_dir = run_phase1(
# #         input_image_name=args.input_image,
# #         run_id=args.run_id,
# #         bake_texture=not args.no_bake_texture,
# #     )
# #     print(f"\n[Phase1] Done. High-poly mesh + texture at: {out_dir}")
# """
# pipeline/phase1_reconstruct/reconstruct.py

# Wraps TripoSR's own run.py as a subprocess call. TripoSR stays frozen and
# untouched (aside from the two bake_texture.py patches already applied) —
# this script does NOT reimplement model loading, it just drives the CLI
# and reorganizes the output into pipeline's data/outputs/<run_id>/ layout.

# TripoSR's run.py writes output as:
#     <output-dir>/0/mesh.obj
#     <output-dir>/0/texture.png
#     <output-dir>/0/input.png     (or similar, exact name may vary)

# This wrapper runs it into a temp/staging output dir, then moves the
# contents into data/outputs/<run_id>/phase1_highpoly/ for the rest of
# the pipeline to consume.
# """

# import shutil
# import subprocess
# import sys
# from pathlib import Path

# from pipeline import config


# def run_triposr(input_image: Path, staging_dir: Path, bake_texture: bool = True) -> Path:
#     """
#     Calls TripoSR/run.py as a subprocess. Returns the path to the
#     subfolder (usually '0') containing mesh.obj + texture.png.
#     """
#     staging_dir.mkdir(parents=True, exist_ok=True)
#     # TripoSR's xatlas.export doesn't create the numbered output subfolder
#     # itself (e.g. '0/'), it just writes into it — pre-create it here.
#     (staging_dir / "0").mkdir(parents=True, exist_ok=True)

#     cmd = [
#         sys.executable, str(config.TRIPOSR_RUN_SCRIPT),
#         str(input_image),
#         "--output-dir", str(staging_dir),
#     ]
#     if bake_texture:
#         cmd.append("--bake-texture")

#     print(f"[Phase1] Running: {' '.join(cmd)}")
#     result = subprocess.run(cmd, cwd=str(config.TRIPOSR_DIR), capture_output=True, text=True)

#     if result.returncode != 0:
#         print(result.stdout)
#         print(result.stderr)
#         raise RuntimeError(f"TripoSR run.py failed with exit code {result.returncode}")

#     print(result.stdout)

#     # TripoSR writes into a numbered subfolder (typically '0') under output-dir
#     subfolders = [p for p in staging_dir.iterdir() if p.is_dir()]
#     if not subfolders:
#         raise FileNotFoundError(f"No output subfolder found in {staging_dir}")
#     return subfolders[0]


# def organize_output(triposr_output_subdir: Path, run_id: str) -> Path:
#     """
#     Moves mesh.obj + texture.png (+ input image if present) from
#     TripoSR's raw output subfolder into data/outputs/<run_id>/phase1_highpoly/.
#     """
#     target_dir = config.phase1_dir(run_id)
#     target_dir.mkdir(parents=True, exist_ok=True)

#     expected_files = ["mesh.obj", "texture.png"]
#     for fname in expected_files:
#         src = triposr_output_subdir / fname
#         if not src.exists():
#             raise FileNotFoundError(f"Expected {fname} not found in {triposr_output_subdir}")
#         shutil.copy2(src, target_dir / fname)

#     # copy input image too if TripoSR saved one alongside
#     for candidate in triposr_output_subdir.glob("input*.png"):
#         shutil.copy2(candidate, target_dir / candidate.name)

#     print(f"[Phase1] Output organized into: {target_dir}")
#     return target_dir


# def run_phase1(input_image_name: str, run_id: str, bake_texture: bool = True) -> Path:
#     input_image = config.input_image_path(input_image_name)
#     if not input_image.exists():
#         raise FileNotFoundError(f"Input image not found: {input_image}")

#     staging_dir = config.run_dir(run_id) / "_phase1_staging"
#     output_subdir = run_triposr(input_image, staging_dir, bake_texture=bake_texture)
#     final_dir = organize_output(output_subdir, run_id)

#     # clean up staging dir now that files are copied into place
#     shutil.rmtree(staging_dir, ignore_errors=True)

#     return final_dir


# if __name__ == "__main__":
#     import argparse

#     parser = argparse.ArgumentParser(description="Phase 1: run frozen TripoSR reconstruction")
#     parser.add_argument("--input_image", type=str, required=True,
#                          help="Filename inside data/inputs/, e.g. 'chair.png'")
#     parser.add_argument("--run_id", type=str, required=True,
#                          help="Identifier for this run, e.g. 'chair_run1'")
#     parser.add_argument("--no_bake_texture", action="store_true",
#                          help="Disable --bake-texture flag when calling run.py")
#     args = parser.parse_args()

#     out_dir = run_phase1(
#         input_image_name=args.input_image,
#         run_id=args.run_id,
#         bake_texture=not args.no_bake_texture,
#     )
#     print(f"\n[Phase1] Done. High-poly mesh + texture at: {out_dir}")



"""
pipeline/phase1_reconstruct/reconstruct.py

Wraps TripoSR's own run.py as a subprocess call. TripoSR stays frozen and
untouched (aside from the two bake_texture.py patches already applied) —
this script does NOT reimplement model loading, it just drives the CLI
and reorganizes the output into pipeline's data/outputs/<run_id>/ layout.

TripoSR's run.py writes output as:
    <output-dir>/0/mesh.obj
    <output-dir>/0/texture.png
    <output-dir>/0/input.png     (or similar, exact name may vary)

This wrapper runs it into a temp/staging output dir, then moves the
contents into data/outputs/<run_id>/phase1_highpoly/ for the rest of
the pipeline to consume.
"""

import shutil
import subprocess
import sys
from pathlib import Path

from pipeline import config


def run_triposr(input_image: Path, staging_dir: Path, bake_texture: bool = True,
                 mc_resolution: int = 256) -> Path:
    """
    Calls TripoSR/run.py as a subprocess. Returns the path to the
    subfolder (usually '0') containing mesh.obj + texture.png.

    mc_resolution controls marching-cubes extraction density (TripoSR
    default is 256). Higher = finer/denser high-poly mesh, more faces.
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    # TripoSR's xatlas.export doesn't create the numbered output subfolder
    # itself (e.g. '0/'), it just writes into it — pre-create it here.
    (staging_dir / "0").mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(config.TRIPOSR_RUN_SCRIPT),
        str(input_image),
        "--output-dir", str(staging_dir),
    ]
    if bake_texture:
        cmd.append("--bake-texture")
    if mc_resolution is not None:
        cmd += ["--mc-resolution", str(mc_resolution)]

    print(f"[Phase1] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(config.TRIPOSR_DIR), capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise RuntimeError(f"TripoSR run.py failed with exit code {result.returncode}")

    print(result.stdout)

    # TripoSR writes into a numbered subfolder (typically '0') under output-dir
    subfolders = [p for p in staging_dir.iterdir() if p.is_dir()]
    if not subfolders:
        raise FileNotFoundError(f"No output subfolder found in {staging_dir}")
    return subfolders[0]


def organize_output(triposr_output_subdir: Path, run_id: str) -> Path:
    """
    Moves mesh.obj + texture.png (+ input image if present) from
    TripoSR's raw output subfolder into data/outputs/<run_id>/phase1_highpoly/.
    """
    target_dir = config.phase1_dir(run_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    expected_files = ["mesh.obj", "texture.png"]
    for fname in expected_files:
        src = triposr_output_subdir / fname
        if not src.exists():
            raise FileNotFoundError(f"Expected {fname} not found in {triposr_output_subdir}")
        shutil.copy2(src, target_dir / fname)

    # copy input image too if TripoSR saved one alongside
    for candidate in triposr_output_subdir.glob("input*.png"):
        shutil.copy2(candidate, target_dir / candidate.name)

    print(f"[Phase1] Output organized into: {target_dir}")
    return target_dir


def run_phase1(input_image_name: str, run_id: str, bake_texture: bool = True,
                mc_resolution: int = None) -> Path:
    input_image = config.input_image_path(input_image_name)
    if not input_image.exists():
        raise FileNotFoundError(f"Input image not found: {input_image}")

    staging_dir = config.run_dir(run_id) / "_phase1_staging"
    output_subdir = run_triposr(input_image, staging_dir, bake_texture=bake_texture,
                                 mc_resolution=mc_resolution)
    final_dir = organize_output(output_subdir, run_id)

    # clean up staging dir now that files are copied into place
    shutil.rmtree(staging_dir, ignore_errors=True)

    return final_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 1: run frozen TripoSR reconstruction")
    parser.add_argument("--input_image", type=str, required=True,
                         help="Filename inside data/inputs/, e.g. 'chair.png'")
    parser.add_argument("--run_id", type=str, required=True,
                         help="Identifier for this run, e.g. 'chair_run1'")
    parser.add_argument("--no_bake_texture", action="store_true",
                         help="Disable --bake-texture flag when calling run.py")
    parser.add_argument("--mc_resolution", type=int, default=None,
                         help="Marching cubes resolution (TripoSR default 256). Higher = more detail/faces.")
    args = parser.parse_args()

    out_dir = run_phase1(
        input_image_name=args.input_image,
        run_id=args.run_id,
        bake_texture=not args.no_bake_texture,
        mc_resolution=args.mc_resolution,
    )
    print(f"\n[Phase1] Done. High-poly mesh + texture at: {out_dir}")