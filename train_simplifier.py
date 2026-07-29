"""
Main entry point for the FlexiCubes learned simplification training loop.

Flow: FlexiCubesField -> extract_mesh() -> Renderer -> losses.compute_total_loss
-> backward() -> optimizer.step(), repeated for config.NUM_STEPS.

Reference (target) views are rendered once up front from the Phase 1
high-poly mesh and reused every step.
"""

import os
import torch

import config
from field import FlexiCubesField
from camera_rig import generate_camera_rig
from render import Renderer
from losses import compute_total_loss
from extract import load_obj_vertices_faces, save_obj


def ensure_dirs():
    for d in (config.CHECKPOINT_DIR, config.RENDER_DIR, config.LOG_DIR):
        os.makedirs(d, exist_ok=True)


def main():
    ensure_dirs()
    device = config.DEVICE
    print(f"Using device: {device}")

    # --- camera rig (shared for target + prediction renders) ---
    mvp_list = generate_camera_rig(device=device)
    renderer = Renderer(device=device)

    # --- reference mesh + target views (rendered once) ---
    print(f"Loading reference mesh: {config.INPUT_MESH_PATH}")
    ref_verts, ref_faces = load_obj_vertices_faces(config.INPUT_MESH_PATH, device=device)
    with torch.no_grad():
        target_views = renderer.render_multiview(ref_verts, ref_faces, mvp_list)
    print(f"Reference mesh: {ref_verts.shape[0]} verts, {ref_faces.shape[0]} faces")

    # --- learnable field ---
    field = FlexiCubesField(device=device)
    optimizer = torch.optim.Adam(field.parameters(), lr=config.LEARNING_RATE)

    log_path = os.path.join(config.LOG_DIR, "train_log.csv")
    with open(log_path, "w") as logf:
        logf.write("step,mask_loss,depth_loss,sdf_reg,total,num_verts,num_faces\n")

        for step in range(1, config.NUM_STEPS + 1):
            optimizer.zero_grad()

            vertices, faces, l_dev = field.extract_mesh(training=True)
            if vertices.shape[0] == 0 or faces.shape[0] == 0:
                print(f"[step {step}] WARNING: empty mesh extracted, skipping step")
                continue

            pred_views = renderer.render_multiview(vertices, faces, mvp_list)
            loss, breakdown = compute_total_loss(pred_views, target_views, l_dev)

            loss.backward()
            optimizer.step()

            if step % config.LOG_EVERY == 0 or step == 1:
                print(
                    f"[step {step}/{config.NUM_STEPS}] "
                    f"total={breakdown['total']:.5f} "
                    f"mask={breakdown['mask_loss']:.5f} "
                    f"depth={breakdown['depth_loss']:.5f} "
                    f"reg={breakdown['sdf_reg']:.5f} "
                    f"verts={vertices.shape[0]} faces={faces.shape[0]}"
                )
            logf.write(
                f"{step},{breakdown['mask_loss']:.6f},{breakdown['depth_loss']:.6f},"
                f"{breakdown['sdf_reg']:.6f},{breakdown['total']:.6f},"
                f"{vertices.shape[0]},{faces.shape[0]}\n"
            )
            logf.flush()

            if step % config.CHECKPOINT_EVERY == 0:
                ckpt_path = os.path.join(config.CHECKPOINT_DIR, f"step_{step:05d}.pt")
                torch.save(
                    {"sdf": field.sdf.detach().cpu(), "deform": field.deform.detach().cpu(), "step": step},
                    ckpt_path,
                )
                print(f"  saved checkpoint: {ckpt_path}")

            if step % config.RENDER_SNAPSHOT_EVERY == 0:
                snap_path = os.path.join(config.RENDER_DIR, f"step_{step:05d}.obj")
                save_obj(snap_path, vertices, faces)
                print(f"  saved mesh snapshot: {snap_path}")

    # --- final output ---
    with torch.no_grad():
        final_vertices, final_faces, _ = field.extract_mesh(training=False)
    save_obj(config.FINAL_MESH_PATH, final_vertices, final_faces)
    print(f"\nDone. Final mesh: {config.FINAL_MESH_PATH}")
    print(f"  {final_vertices.shape[0]} verts, {final_faces.shape[0]} faces "
          f"(reference had {ref_verts.shape[0]} verts, {ref_faces.shape[0]} faces)")


if __name__ == "__main__":
    main()