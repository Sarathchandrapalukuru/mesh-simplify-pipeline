"""
Minimal .obj I/O -- avoids adding trimesh/imageio as a dependency since
your env only has torch/nvdiffrast/kaolin/numpy/Pillow/scipy so far.
Vertex normals/UVs are ignored on load (we only need positions+faces for
mask/depth rendering); texture is not needed for this stretch-goal track.
"""

import torch

import config


def load_obj_vertices_faces(path: str, device: torch.device = None):
    """Reads only 'v' and 'f' lines. Faces assumed triangulated; if not,
    a naive fan-triangulation is applied. Returns (vertices, faces) as
    float32/int64 tensors, centered and scaled to fit in a unit sphere
    (matches FlexiCubes grid range of roughly [-0.5, 0.5])."""
    device = device or config.DEVICE
    verts = []
    faces = []

    with open(path, "r") as f:
        for line in f:
            if line.startswith("v "):
                parts = line.strip().split()[1:4]
                verts.append([float(x) for x in parts])
            elif line.startswith("f "):
                parts = line.strip().split()[1:]
                idxs = [int(p.split("/")[0]) - 1 for p in parts]  # obj is 1-indexed
                if len(idxs) == 3:
                    faces.append(idxs)
                else:
                    # naive fan triangulation for n-gons
                    for i in range(1, len(idxs) - 1):
                        faces.append([idxs[0], idxs[i], idxs[i + 1]])

    vertices = torch.tensor(verts, dtype=torch.float32, device=device)
    faces_t = torch.tensor(faces, dtype=torch.int64, device=device)

    # center + normalize to fit FlexiCubes' [-0.5, 0.5] grid range
    center = vertices.mean(dim=0)
    vertices = vertices - center
    scale = vertices.abs().max()
    vertices = vertices / (scale * 2.2)  # small margin so it's inside the grid

    return vertices, faces_t


def save_obj(path: str, vertices: torch.Tensor, faces: torch.Tensor):
    """Writes a bare-bones .obj (positions + triangle faces only)."""
    verts = vertices.detach().cpu().numpy()
    tris = faces.detach().cpu().numpy()

    with open(path, "w") as f:
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for tri in tris:
            # back to 1-indexed for obj format
            f.write(f"f {tri[0] + 1} {tri[1] + 1} {tri[2] + 1}\n")