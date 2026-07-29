"""
Blender headless render script -- visual verification for the FlexiCubes
learned-simplifier output.

Usage (from PowerShell, adjust the blender.exe path to your install):
    blender --background --python render_check.py -- ^
        --obj "data/runs/chair_flexi_run1/final_mesh.obj" ^
        --out "data/runs/chair_flexi_run1/renders/verify" ^
        --views 8

Renders `--views` turntable images around the mesh at a fixed elevation,
same style as the Phase 3 evaluation harness's fixed camera rig -- useful
here just for a quick visual sanity check, not for PSNR/SSIM scoring.
"""

import argparse
import math
import os
import sys

import bpy


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    p = argparse.ArgumentParser()
    p.add_argument("--obj", required=True, help="Path to the .obj to render")
    p.add_argument("--out", required=True, help="Output directory for renders")
    p.add_argument("--views", type=int, default=8, help="Number of turntable views")
    p.add_argument("--elevation", type=float, default=20.0, help="Camera elevation in degrees")
    p.add_argument("--distance", type=float, default=3.0, help="Camera distance from origin")
    p.add_argument("--resolution", type=int, default=512, help="Square render resolution")
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def setup_light():
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 5))
    sun = bpy.context.object
    sun.data.energy = 3.0
    bpy.ops.object.light_add(type="SUN", location=(5, -5, 3))
    fill = bpy.context.object
    fill.data.energy = 1.0


def setup_camera(distance, elevation_deg):
    bpy.ops.object.camera_add(location=(distance, 0, 0))
    cam = bpy.context.object
    cam.data.lens_unit = "FOV"
    cam.data.angle = math.radians(45.0)
    bpy.context.scene.camera = cam
    return cam


def point_camera_at_origin(cam, azim_rad, elev_rad, distance):
    x = distance * math.cos(elev_rad) * math.cos(azim_rad)
    y = distance * math.cos(elev_rad) * math.sin(azim_rad)
    z = distance * math.sin(elev_rad)
    cam.location = (x, y, z)

    direction = (-x, -y, -z)
    # point -Z (camera forward) at origin, +Y up -- track_to constraint
    quat = (
        bpy.data.objects.new("tmp", None).rotation_quaternion
    )
    # simpler: use track-to via matrix construction
    import mathutils
    loc = mathutils.Vector((x, y, z))
    look_dir = (mathutils.Vector((0, 0, 0)) - loc).normalized()
    rot_quat = look_dir.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot_quat.to_euler()


def main():
    args = parse_args()
    args.obj = os.path.abspath(args.obj)
    args.out = os.path.abspath(args.out)
    os.makedirs(args.out, exist_ok=True)

    clear_scene()
    bpy.ops.wm.obj_import(filepath=args.obj)

    # FlexiCubes' topology changes every optimization step, so face winding
    # order isn't guaranteed consistent -- recalculate normals and disable
    # backface culling so inconsistent winding doesn't render as false holes
    obj = bpy.context.selected_objects[0]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    mat = bpy.data.materials.new(name="verify_mat")
    mat.use_backface_culling = False
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

    setup_light()
    cam = setup_camera(args.distance, args.elevation)

    scene = bpy.context.scene
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"
    scene.render.engine = "BLENDER_EEVEE"  # fast, sufficient for a
                                                  # visual sanity check;
                                                  # switch to CYCLES in
                                                  # Phase 3 if you need
                                                  # more accurate shading
                                                  # for PSNR/SSIM scoring

    elev_rad = math.radians(args.elevation)
    for i in range(args.views):
        azim_rad = 2.0 * math.pi * i / args.views
        point_camera_at_origin(cam, azim_rad, elev_rad, args.distance)

        scene.render.filepath = os.path.join(args.out, f"view_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered view {i+1}/{args.views} -> {scene.render.filepath}")

    print(f"\nDone. {args.views} views saved to: {args.out}")


if __name__ == "__main__":
    main()