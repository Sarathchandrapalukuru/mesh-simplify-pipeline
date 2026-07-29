"""
nvdiffrast rendering wrapper.

Renders a mesh (vertices, faces) from each camera in the rig, producing
per-view mask + depth buffers -- differentiable w.r.t. vertex positions.
RGB/texture rendering can be added later once mask+depth loss is verified
working (matches the FlexiCubes reference optimization example, which
starts with mask+depth only).
"""

import torch
import nvdiffrast.torch as dr

import config


class Renderer:
    def __init__(self, device: torch.device = None, resolution: int = None):
        self.device = device or config.DEVICE
        self.resolution = resolution or config.RENDER_RESOLUTION
        self.ctx = dr.RasterizeCudaContext(device=self.device)

    def render(self, vertices: torch.Tensor, faces: torch.Tensor, mvp: torch.Tensor):
        """
        vertices: (V, 3) float32, object space
        faces: (F, 3) int32/int64
        mvp: (4, 4) float32, model-view-projection for one camera

        Returns dict with 'mask' (H, W, 1) and 'depth' (H, W, 1), both in
        [0, 1] range roughly, differentiable w.r.t. `vertices`.
        """
        faces_i32 = faces.to(torch.int32)

        # homogeneous coords, project to clip space
        ones = torch.ones(vertices.shape[0], 1, device=vertices.device, dtype=vertices.dtype)
        verts_h = torch.cat([vertices, ones], dim=-1)  # (V, 4)
        verts_clip = (verts_h @ mvp.t()).unsqueeze(0)   # (1, V, 4)

        rast, _ = dr.rasterize(
            self.ctx, verts_clip, faces_i32, resolution=[self.resolution, self.resolution]
        )

        # mask: 1 where a triangle was rasterized, 0 elsewhere
        mask = (rast[..., 3:4] > 0).float()

        # depth: interpolate clip-space z (or view-space if you pass it in);
        # here we interpolate NDC z from verts_clip for a simple depth proxy
        ndc_z = (verts_clip[..., 2] / verts_clip[..., 3]).unsqueeze(-1)  # (1, V, 1)
        depth, _ = dr.interpolate(ndc_z.contiguous(), rast, faces_i32)
        depth = depth * mask  # zero out background

        return {"mask": mask[0], "depth": depth[0]}

    def render_multiview(self, vertices, faces, mvp_list):
        """Renders the same mesh from every camera in mvp_list.
        Returns list of per-view render dicts, same order as mvp_list."""
        return [self.render(vertices, faces, mvp) for mvp in mvp_list]