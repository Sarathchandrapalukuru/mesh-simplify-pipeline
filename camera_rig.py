"""
Camera rig: generates view/projection matrices for multi-view rendering.

Cameras are placed on a ring around the origin at a fixed elevation,
evenly spaced in azimuth. Produces MVP matrices nvdiffrast can use directly
via rasterize() on clip-space vertices.
"""

import math
import torch

import config


def _look_at(eye, target, up):
    """Right-handed view matrix, eye/target/up as (3,) tensors."""
    f = (target - eye)
    f = f / f.norm()
    s = torch.cross(f, up, dim=0)
    s = s / s.norm()
    u = torch.cross(s, f, dim=0)

    view = torch.eye(4, device=eye.device, dtype=eye.dtype)
    view[0, :3] = s
    view[1, :3] = u
    view[2, :3] = -f
    view[0, 3] = -torch.dot(s, eye)
    view[1, 3] = -torch.dot(u, eye)
    view[2, 3] = torch.dot(f, eye)
    return view


def _perspective(fov_deg, aspect, near=0.1, far=10.0, device=None, dtype=None):
    fov_rad = math.radians(fov_deg)
    f = 1.0 / math.tan(fov_rad / 2.0)
    proj = torch.zeros(4, 4, device=device, dtype=dtype)
    proj[0, 0] = f / aspect
    proj[1, 1] = f
    proj[2, 2] = (far + near) / (near - far)
    proj[2, 3] = (2 * far * near) / (near - far)
    proj[3, 2] = -1.0
    return proj


def generate_camera_rig(
    num_views: int = None,
    elevations_deg=None,
    distance: float = None,
    fov_deg: float = None,
    device: torch.device = None,
):
    """
    Returns a list of (mvp, view, proj) tuples. Views are spread across
    MULTIPLE elevation rings, not just one -- a single elevation leaves the
    top/bottom of the object unconstrained during optimization (nothing
    penalizes holes there), which shows up as real structural gaps in the
    extracted mesh. `elevations_deg` defaults to three rings covering low,
    mid, and high angles so poles get supervision too.
    """
    device = device or config.DEVICE
    num_views = num_views or config.NUM_VIEWS
    if elevations_deg is None:
        elevations_deg = getattr(config, "CAMERA_ELEVATIONS_DEG", [-40.0, 20.0, 60.0])
    distance = distance or config.CAMERA_DISTANCE
    fov_deg = fov_deg or config.CAMERA_FOV_DEG

    dtype = torch.float32
    up = torch.tensor([0.0, 1.0, 0.0], device=device, dtype=dtype)
    target = torch.zeros(3, device=device, dtype=dtype)

    proj = _perspective(fov_deg, aspect=1.0, device=device, dtype=dtype)

    # distribute num_views evenly across the elevation rings, then spread
    # each ring's views evenly in azimuth
    n_rings = len(elevations_deg)
    views_per_ring = max(1, num_views // n_rings)

    rig = []
    for elevation_deg in elevations_deg:
        elev_rad = math.radians(elevation_deg)
        for i in range(views_per_ring):
            azim_rad = 2.0 * math.pi * i / views_per_ring
            x = distance * math.cos(elev_rad) * math.cos(azim_rad)
            y = distance * math.sin(elev_rad)
            z = distance * math.cos(elev_rad) * math.sin(azim_rad)
            eye = torch.tensor([x, y, z], device=device, dtype=dtype)

            view = _look_at(eye, target, up)
            mvp = proj @ view
            rig.append(mvp)

    return rig