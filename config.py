"""
Central config for the FlexiCubes + nvdiffrast learned simplification track.

Mirrors the main project's convention: no magic numbers scattered in code,
one place to tweak an experiment.
"""

import torch

# ---------------------------------------------------------------------------
# Run identity
# ---------------------------------------------------------------------------
RUN_ID = "chair_flexi_run1"
DATA_ROOT = "data"
INPUT_MESH_DIR = f"{DATA_ROOT}/input_mesh"
INPUT_MESH_PATH = f"{INPUT_MESH_DIR}/girl.obj"

RUN_DIR = f"{DATA_ROOT}/runs/{RUN_ID}"
CHECKPOINT_DIR = f"{RUN_DIR}/checkpoints"
RENDER_DIR = f"{RUN_DIR}/renders"
LOG_DIR = f"{RUN_DIR}/logs"
FINAL_MESH_PATH = f"{RUN_DIR}/final_mesh.obj"

# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---------------------------------------------------------------------------
# FlexiCubes grid (this directly controls output poly count -- coarser grid
# = fewer output vertices/faces. This REPLACES Phase 2 decimation for this
# track: there is no separate "decimate afterward" step.)
# ---------------------------------------------------------------------------
GRID_RESOLUTION = 150         # start coarse (24^3) on the 3050 Ti's 4GB --
                               # try [24, 32, 48, 64] later for a poly-count
                               # vs quality sweep, mirroring Phase 2's
                               # decimation ratio sweep [0.5, 0.2, 0.1, 0.05].
                               # Higher resolution = more voxel corners =
                               # more VRAM for the FlexiCubes extraction
                               # graph, independent of render resolution.

SDF_INIT_MODE = "from_lowpoly_mesh"  # "sphere" (from-scratch baseline) or
                               # "from_lowpoly_mesh" (warm-start from a
                               # Phase 2 PyMeshLab decimation output --
                               # FlexiCubes+nvdiffrast then REFINES that
                               # mesh toward better visual fidelity at
                               # roughly the same poly budget, rather than
                               # learning shape from nothing. Converges much
                               # faster and is the fairer head-to-head
                               # comparison against the Phase 2 baseline.)

SDF_INIT_MESH_PATH = f"{DATA_ROOT}/input_mesh/lowpoly_girl.obj"
                               # point this at a Phase 2 output, e.g.
                               # data/outputs/<run_id>/phase2_lowpoly/
                               #   ratio_0.1/mesh.obj -- copy it in as
                               # lowpoly_init.obj before running.
                               # Must be reasonably watertight for the
                               # inside/outside sign test to work well.

# ---------------------------------------------------------------------------
# Camera rig (multi-view rendering for the loss signal)
# ---------------------------------------------------------------------------
NUM_VIEWS = 9                  # split across 3 elevation rings (see
                                # camera_rig.py) = 3 views/ring. Old 4-view
                                # single-ring rig left poles unconstrained,
                                # causing real structural holes -- this is
                                # the fix, not more training steps.
CAMERA_ELEVATIONS_DEG = [-40.0, 20.0, 60.0]  # low/mid/high rings so top
                                # and bottom of the object get supervision
CAMERA_DISTANCE = 2.0
CAMERA_FOV_DEG = 45.0
RENDER_RESOLUTION = 128        # nvdiffrast render size (square). 4GB VRAM
                                # (RTX 3050 Ti) -- start small to verify the
                                # loop runs at all, then step up: 128 -> 256
                                # -> 512, watching nvidia-smi each time.

# ---------------------------------------------------------------------------
# Optimization
# ---------------------------------------------------------------------------
NUM_STEPS = 1000
LEARNING_RATE = 2e-3
LOG_EVERY = 100
RENDER_SNAPSHOT_EVERY = 100   # save an intermediate render to RENDER_DIR
CHECKPOINT_EVERY = 200

# ---------------------------------------------------------------------------
# Loss weights
# ---------------------------------------------------------------------------
MASK_LOSS_WEIGHT = 1.0
DEPTH_LOSS_WEIGHT = 1.0
SDF_REG_WEIGHT = 0.01         # small L1 regularizer on flexible weights,
                               # per FlexiCubes paper's note that it helps
                               # stability even if impact is minor for a
                               # single shape