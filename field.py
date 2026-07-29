"""
Field representation for the FlexiCubes learned simplifier.

Directly optimizes per-vertex SDF values + a small deformation offset on a
FlexiCubes voxel grid -- this is "Option 1" from the FlexiCubes reference
optimization example (direct gradient descent on parameters), not a network.
Simpler to verify first; swap for a small MLP later if direct optimization
doesn't converge cleanly (see notes at bottom).
"""

import torch
from kaolin.non_commercial import FlexiCubes
from kaolin.ops.mesh import index_vertices_by_faces, check_sign
from kaolin.metrics.trianglemesh import point_to_mesh_distance

import config
from extract import load_obj_vertices_faces


class FlexiCubesField:
    """
    Wraps a FlexiCubes voxel grid + learnable (sdf, deformation, weights)
    parameters. Call `.extract_mesh()` each optimization step to get a
    differentiable (vertices, faces) pair.
    """

    def __init__(self, resolution: int = None, device: torch.device = None):
        self.device = device or config.DEVICE
        self.resolution = resolution or config.GRID_RESOLUTION

        self.fc = FlexiCubes(device=self.device)

        # voxelgrid_vertices: (N, 3) corners in [-0.5, 0.5]
        # cube_idx: (num_cubes, 8) indices into voxelgrid_vertices
        self.grid_verts, self.cube_idx = self.fc.construct_voxel_grid(
            self.resolution
        )
        self.grid_verts = self.grid_verts.to(self.device)
        self.cube_idx = self.cube_idx.to(self.device)

        n_verts = self.grid_verts.shape[0]

        # --- learnable parameters ---
        if config.SDF_INIT_MODE == "sphere":
            init_sdf = self._sphere_sdf_init(self.grid_verts, radius=0.4)
        elif config.SDF_INIT_MODE == "from_lowpoly_mesh":
            init_sdf = self._mesh_sdf_init(self.grid_verts, config.SDF_INIT_MESH_PATH)
        else:
            raise NotImplementedError(
                f"SDF_INIT_MODE={config.SDF_INIT_MODE!r} not implemented -- "
                "use 'sphere' or 'from_lowpoly_mesh'."
            )

        self.sdf = torch.nn.Parameter(init_sdf.clone())
        self.deform = torch.nn.Parameter(torch.zeros_like(self.grid_verts))
        # per-cube weights FlexiCubes uses to adjust surface extraction;
        # leave as None to let FlexiCubes use its default (all-ones) --
        # only introduce as a learnable param once the basic loop converges
        self.weights = None

    @staticmethod
    def _sphere_sdf_init(verts: torch.Tensor, radius: float) -> torch.Tensor:
        """Signed distance to a sphere of given radius, centered at origin.
        Negative inside, positive outside -- matches FlexiCubes convention."""
        return torch.norm(verts, dim=-1) - radius

    def _mesh_sdf_init(self, grid_verts: torch.Tensor, mesh_path: str) -> torch.Tensor:
        """Signed distance from each FlexiCubes grid vertex to a reference
        mesh (the Phase 2 low-poly output) -- gives the optimization a
        warm start instead of a generic sphere.

        Sign is taken from the HIGH-POLY (Phase 1) mesh, not the low-poly
        one: PyMeshLab decimation can introduce small non-manifold gaps
        that make check_sign() unreliable on the low-poly mesh directly
        (this showed up in practice as a badly broken initial extraction).
        The raw TripoSR high-poly output is far more likely to be properly
        watertight, and since both meshes describe roughly the same shape,
        using its sign with the low-poly mesh's distance magnitude gives a
        clean init without losing the low-poly warm start."""
        lowpoly_verts, lowpoly_faces = load_obj_vertices_faces(mesh_path, device=self.device)

        face_verts = index_vertices_by_faces(lowpoly_verts.unsqueeze(0), lowpoly_faces)
        query_points = grid_verts.unsqueeze(0)  # (1, N, 3)

        sq_dist, _, _ = point_to_mesh_distance(query_points, face_verts)
        dist = torch.sqrt(sq_dist.clamp(min=1e-12)).squeeze(0)  # (N,)

        sign_verts, sign_faces = load_obj_vertices_faces(config.INPUT_MESH_PATH, device=self.device)
        try:
            inside = check_sign(sign_verts.unsqueeze(0), sign_faces, query_points).squeeze(0)
            sdf = torch.where(inside, -dist, dist)
        except Exception as e:
            print(f"WARNING: check_sign failed ({e}); falling back to sphere init")
            sdf = self._sphere_sdf_init(grid_verts, radius=0.4)

        return sdf

    def parameters(self):
        params = [self.sdf, self.deform]
        if self.weights is not None:
            params.append(self.weights)
        return params

    def extract_mesh(self, training: bool = True):
        """Returns (vertices, faces, l_dev) -- all differentiable w.r.t.
        self.sdf / self.deform. l_dev is FlexiCubes' regularizer term,
        add SDF_REG_WEIGHT * l_dev.mean() to your loss."""
        # small tanh-bounded deformation, keeps grid verts from crossing
        # neighboring cells -- same trick as the FlexiCubes reference example
        deformed_verts = self.grid_verts + (
            (2 - 1e-8) / (self.resolution * 2)
        ) * torch.tanh(self.deform)

        vertices, faces, l_dev = self.fc(
            voxelgrid_vertices=deformed_verts,
            scalar_field=self.sdf,
            cube_idx=self.cube_idx,
            resolution=self.resolution,
            weight_scale=0.99,
            training=training,
        )
        return vertices, faces, l_dev