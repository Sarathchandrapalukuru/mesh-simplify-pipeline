# 2D-to-3D Mesh Reconstruction and Quality-Preserving Compression Pipeline

## Overview

This project implements an end-to-end pipeline that reconstructs a 3D textured mesh from a single 2D input image and systematically evaluates how mesh quality degrades under compression (decimation). The pipeline takes an image, generates a high-poly mesh using a frozen TripoSR backbone, decimates it to several low-poly variants, renders both, and quantifies the resulting geometric and visual quality loss.

## Motivation

Prior work on 3D reconstruction and mesh compression exists largely as two separate lineages: reconstruction-quality papers and compression-efficiency papers, rarely evaluated jointly. This project's contribution is not a new reconstruction architecture, but a systematic, empirical evaluation of quality degradation under compression constraints — closing that gap with controlled, per-ratio measurement across geometric (Chamfer, Hausdorff) and image-based (PSNR, SSIM) metrics.

## Pipeline Stages

1. **Reconstruction** — A single input image is passed through frozen TripoSR to produce a high-poly textured 3D mesh (implicit SDF/occupancy + marching cubes; no explicit point-cloud step).
2. **Decimation** — The high-poly mesh is decimated to multiple low-poly variants (ratios 0.5 / 0.2 / 0.1 / 0.05) using PyMeshLab's quadric edge-collapse with texture preservation.
3. **Rendering** — Each mesh variant (high-poly and decimated) is rendered from a fixed 2-ring camera rig (8 views) in Blender headless (Eevee), with cameras locked to the high-poly bounding box for consistent, comparable framing. (for ref)
4.  **Simplifing** - (present in other branch) using flexicubes with ref to the high poly we constructed new model this new one will retain shape and structure even after a good amount of compression
.

## Repository Structure(master)

```
── TripoSR\                      # untouched, frozen, vendor code
│
├── pipeline\                      # your actual project code — new
│   ├── __init__.py
│   ├── config.py                  # shared paths, constants (ratios, dirs)
│   │
│   ├── phase1_reconstruct\        # wraps calls into TripoSR
│   │   └── reconstruct.py
│   │
│   ├── phase2_remesh\             # new — this phase
│   │   ├── __init__.py
│   │   ├── remesh.py              # decimate() using pymeshlab
│   │   └── io_utils.py            # load/save mesh + texture-copy helper
│   │
│   ├── phase3_evaluate\           # next phase — Blender render + PSNR/SSIM, Chamfer
│       ├── render_harness.py
│       └── metrics.py             # equalness function lives here
│   
│   
│       
│       
│
├── data\
│   ├── inputs\                    # source 2D images
│   ├── outputs\
│   │   ├── phase1_highpoly\
│   │   │   └── <run_id>\model.obj, model.mtl, texture.png
│   │   ├── phase2_lowpoly\
│   │   │   └── <run_id>\ratio_0.5\, ratio_0.2\, ratio_0.1\, ratio_0.05\
│   │   │       each containing model.obj, model.mtl, texture.png (copied)
│   │   └── phase3_eval\
│   │       └── <run_id>\renders\, metrics.json
│
├── notebooks\                     # optional scratch/exploration
├── tests\                         # unit tests per phase, once you want them
├── environment.yml                # conda env export (2d_to_3d)
└── README.md
```

## Tools & Environment

- **Reconstruction:** TripoSR (frozen, subprocess-wrapped)
- **Decimation:** PyMeshLab (quadric edge-collapse with texture)
- **Rendering:** Blender 5.1.2 headless (Eevee)
- **Environment:** Windows, Anaconda, conda env `2d_to_3d`

## Ref to the Readme folder for debugging and more info
