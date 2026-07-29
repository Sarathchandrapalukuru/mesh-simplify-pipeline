"""
Losses for the FlexiCubes optimization loop.

Mask + depth loss, computed against renders of the reference (Phase 1
high-poly) mesh from the same camera rig. This mirrors the FlexiCubes
paper's own reference optimization setup.
"""

import torch

import config


def mask_loss(pred_mask: torch.Tensor, target_mask: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.mse_loss(pred_mask, target_mask)


def depth_loss(pred_depth: torch.Tensor, target_depth: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Only penalize depth where the target mask says there's geometry --
    background depth is meaningless to compare."""
    diff = (pred_depth - target_depth) * mask
    return (diff ** 2).sum() / mask.sum().clamp(min=1.0)


def sdf_regularizer(l_dev: torch.Tensor) -> torch.Tensor:
    """FlexiCubes' own L_dev regularizer -- keeps dual vertices from
    deviating too far, improves stability."""
    return l_dev.mean()


def compute_total_loss(pred_views, target_views, l_dev):
    """
    pred_views / target_views: lists of {'mask': ..., 'depth': ...} dicts,
    one per camera, same order.
    """
    total_mask = 0.0
    total_depth = 0.0
    for pred, target in zip(pred_views, target_views):
        total_mask = total_mask + mask_loss(pred["mask"], target["mask"])
        total_depth = total_depth + depth_loss(pred["depth"], target["depth"], target["mask"])

    n = len(pred_views)
    total_mask = total_mask / n
    total_depth = total_depth / n
    reg = sdf_regularizer(l_dev)

    total = (
        config.MASK_LOSS_WEIGHT * total_mask
        + config.DEPTH_LOSS_WEIGHT * total_depth
        + config.SDF_REG_WEIGHT * reg
    )

    breakdown = {
        "mask_loss": total_mask.item(),
        "depth_loss": total_depth.item(),
        "sdf_reg": reg.item(),
        "total": total.item(),
    }
    return total, breakdown