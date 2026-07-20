# """
# pipeline/phase2_remesh/remesh.py

# Phase 2: Decimate a high-poly TripoSR mesh (mesh.obj) down to several
# low-poly ratios using PyMeshLab's quadric edge collapse, preserving UV
# coordinates so texture.png can be manually applied later (Blender, Phase 3)
# exactly as it was on the high-poly mesh.

# Input assumption (confirmed from TripoSR output folder):
#     <phase1_dir>/mesh.obj       - has vt (UV) coords, no mtllib/usemtl binding
#     <phase1_dir>/texture.png    - applied manually in Blender, not referenced by obj

# Output:
#     <phase2_dir>/ratio_<r>/mesh.obj      - decimated mesh, UVs preserved
#     <phase2_dir>/ratio_<r>/texture.png   - copied verbatim (same texture, unbaked)
# """

# import shutil
# from pathlib import Path
# import pymeshlab


# def decimate_mesh(input_obj: Path, target_ratio: float, output_obj: Path) -> dict:
#     """
#     Decimate input_obj to target_ratio of its original face count,
#     preserving UV coordinates, and save to output_obj.

#     Returns a dict of before/after stats for logging.
#     """
#     ms = pymeshlab.MeshSet()
#     ms.load_new_mesh(str(input_obj))

#     mesh = ms.current_mesh()
#     original_faces = mesh.face_number()
#     original_verts = mesh.vertex_number()

#     target_face_num = max(4, int(original_faces * target_ratio))

#     # Quadric Edge Collapse Decimation, texture-aware variant — preserves
#     # UV coordinates during collapse (extratcoordw weights UV preservation
#     # alongside geometric quadric error). Confirmed param names against
#     # installed pymeshlab version via ms.filter_parameter_values(...).
#     ms.meshing_decimation_quadric_edge_collapse_with_texture(
#         targetfacenum=target_face_num,
#         qualitythr=0.3,
#         extratcoordw=1.0,
#         preserveboundary=True,
#         boundaryweight=1.0,
#         optimalplacement=True,
#         preservenormal=True,
#         planarquadric=True,
#     )

#     output_obj.parent.mkdir(parents=True, exist_ok=True)
#     ms.save_current_mesh(str(output_obj))

#     result_mesh = ms.current_mesh()
#     final_faces = result_mesh.face_number()
#     final_verts = result_mesh.vertex_number()

#     stats = {
#         "target_ratio": target_ratio,
#         "original_faces": original_faces,
#         "original_verts": original_verts,
#         "target_face_num": target_face_num,
#         "final_faces": final_faces,
#         "final_verts": final_verts,
#         "actual_ratio": round(final_faces / original_faces, 4) if original_faces else 0,
#     }
#     return stats


# def run_phase2(phase1_dir: Path, phase2_dir: Path, ratios: list[float]) -> list[dict]:
#     """
#     Run decimation across all ratios for one run_id, copying texture.png
#     into each self-contained ratio folder.
#     """
#     input_obj = phase1_dir / "mesh.obj"
#     texture_src = phase1_dir / "texture.png"

#     if not input_obj.exists():
#         raise FileNotFoundError(f"mesh.obj not found at {input_obj}")
#     if not texture_src.exists():
#         raise FileNotFoundError(f"texture.png not found at {texture_src}")

#     all_stats = []
#     for ratio in ratios:
#         ratio_dir = phase2_dir / f"ratio_{ratio}"
#         output_obj = ratio_dir / "mesh.obj"

#         print(f"[Phase2] Decimating to ratio={ratio} -> {output_obj}")
#         stats = decimate_mesh(input_obj, ratio, output_obj)
#         print(f"  original_faces={stats['original_faces']}  "
#               f"target={stats['target_face_num']}  "
#               f"final_faces={stats['final_faces']}  "
#               f"actual_ratio={stats['actual_ratio']}")

#         # copy texture verbatim into the same self-contained folder
#         texture_dst = ratio_dir / "texture.png"
#         shutil.copy2(texture_src, texture_dst)

#         all_stats.append(stats)

#     return all_stats


# if __name__ == "__main__":
#     import argparse
#     import json

#     from pipeline import config

#     parser = argparse.ArgumentParser(description="Phase 2: remesh high-poly to low-poly ratios")
#     parser.add_argument("--run_id", type=str, required=True,
#                          help="Run identifier, matches the one used in Phase 1 (e.g. 'chair_run1')")
#     parser.add_argument("--ratios", type=float, nargs="+", default=None,
#                          help="Target face-count ratios (defaults to config.DECIMATION_RATIOS)")
#     args = parser.parse_args()

#     ratios = args.ratios if args.ratios is not None else config.DECIMATION_RATIOS
#     p1_dir = config.phase1_dir(args.run_id)
#     p2_dir = config.phase2_dir(args.run_id)

#     stats = run_phase2(p1_dir, p2_dir, ratios)

#     print("\n[Phase2] Summary:")
#     for s in stats:
#         print(s)

#     stats_path = p2_dir / "phase2_stats.json"
#     stats_path.parent.mkdir(parents=True, exist_ok=True)
#     with open(stats_path, "w") as f:
#         json.dump(stats, f, indent=2)
#     print(f"\n[Phase2] Stats saved to: {stats_path}")

"""
pipeline/phase2_remesh/remesh.py

Phase 2: Decimate a high-poly TripoSR mesh (mesh.obj) down to several
low-poly ratios using PyMeshLab's quadric edge collapse, preserving UV
coordinates so texture.png can be manually applied later (Blender, Phase 3)
exactly as it was on the high-poly mesh.

Input assumption (confirmed from TripoSR output folder):
    <phase1_dir>/mesh.obj       - has vt (UV) coords, no mtllib/usemtl binding
    <phase1_dir>/texture.png    - applied manually in Blender, not referenced by obj

Output:
    <phase2_dir>/ratio_<r>/mesh.obj      - decimated mesh, UVs preserved
    <phase2_dir>/ratio_<r>/texture.png   - copied verbatim (same texture, unbaked)
"""

import shutil
from pathlib import Path
import pymeshlab


def decimate_mesh(input_obj: Path, target_ratio: float, output_obj: Path) -> dict:
    """
    Decimate input_obj to target_ratio of its original face count,
    preserving UV coordinates, and save to output_obj.

    Returns a dict of before/after stats for logging.
    """
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(input_obj))

    mesh = ms.current_mesh()
    original_faces = mesh.face_number()
    original_verts = mesh.vertex_number()

    target_face_num = max(4, int(original_faces * target_ratio))

    # Quadric Edge Collapse Decimation, texture-aware variant — preserves
    # UV coordinates during collapse (extratcoordw weights UV preservation
    # alongside geometric quadric error). Confirmed param names against
    # installed pymeshlab version via ms.filter_parameter_values(...).
    ms.meshing_decimation_quadric_edge_collapse_with_texture(
        targetfacenum=target_face_num,
        qualitythr=0.1,
        extratcoordw=1.0,
        preserveboundary=False,
        boundaryweight=1,
        optimalplacement=True,
        preservenormal=True,
        planarquadric=True,
    )

    output_obj.parent.mkdir(parents=True, exist_ok=True)
    ms.save_current_mesh(str(output_obj))

    result_mesh = ms.current_mesh()
    final_faces = result_mesh.face_number()
    final_verts = result_mesh.vertex_number()

    stats = {
        "target_ratio": target_ratio,
        "original_faces": original_faces,
        "original_verts": original_verts,
        "target_face_num": target_face_num,
        "final_faces": final_faces,
        "final_verts": final_verts,
        "actual_ratio": round(final_faces / original_faces, 4) if original_faces else 0,
    }
    return stats


def run_phase2(phase1_dir: Path, phase2_dir: Path, ratios: list[float]) -> list[dict]:
    """
    Run decimation across all ratios for one run_id, copying texture.png
    into each self-contained ratio folder.
    """
    input_obj = phase1_dir / "mesh.obj"
    texture_src = phase1_dir / "texture.png"

    if not input_obj.exists():
        raise FileNotFoundError(f"mesh.obj not found at {input_obj}")
    if not texture_src.exists():
        raise FileNotFoundError(f"texture.png not found at {texture_src}")

    all_stats = []
    for ratio in ratios:
        ratio_dir = phase2_dir / f"ratio_{ratio}"
        output_obj = ratio_dir / "mesh.obj"

        print(f"[Phase2] Decimating to ratio={ratio} -> {output_obj}")
        stats = decimate_mesh(input_obj, ratio, output_obj)
        print(f"  original_faces={stats['original_faces']}  "
              f"target={stats['target_face_num']}  "
              f"final_faces={stats['final_faces']}  "
              f"actual_ratio={stats['actual_ratio']}")

        # copy texture verbatim into the same self-contained folder
        texture_dst = ratio_dir / "texture.png"
        shutil.copy2(texture_src, texture_dst)

        all_stats.append(stats)

    return all_stats


if __name__ == "__main__":
    import argparse
    import json

    from pipeline import config

    parser = argparse.ArgumentParser(description="Phase 2: remesh high-poly to low-poly ratios")
    parser.add_argument("--run_id", type=str, required=True,
                         help="Run identifier, matches the one used in Phase 1 (e.g. 'chair_run1')")
    parser.add_argument("--ratios", type=float, nargs="+", default=None,
                         help="Target face-count ratios (defaults to config.DECIMATION_RATIOS)")
    args = parser.parse_args()

    ratios = args.ratios if args.ratios is not None else config.DECIMATION_RATIOS
    p1_dir = config.phase1_dir(args.run_id)
    p2_dir = config.phase2_dir(args.run_id)

    stats = run_phase2(p1_dir, p2_dir, ratios)

    print("\n[Phase2] Summary:")
    for s in stats:
        print(s)

    stats_path = p2_dir / "phase2_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\n[Phase2] Stats saved to: {stats_path}")