# """
# Phase 3 — Evaluation render harness (Blender 5.1, headless)

# Renders a fixed 12-view camera rig around a mesh, using a bounding box
# computed ONCE from the high-poly reference mesh and reused verbatim for
# every ratio, so framing never confounds the geometry/texture comparison.

# Usage (from PowerShell, one run_id at a time):

#     blender --background --python render_views.py -- ^
#         --run-dir "data/outputs/chair_run1" ^
#         --views 12

# Expects this directory layout (already produced by Phase 1 / Phase 2):

#     <run-dir>/phase1_highpoly/mesh.obj      (+ texture.png)
#     <run-dir>/phase2_lowpoly/ratio_0.5/mesh.obj
#     <run-dir>/phase2_lowpoly/ratio_0.2/mesh.obj
#     <run-dir>/phase2_lowpoly/ratio_0.1/mesh.obj
#     <run-dir>/phase2_lowpoly/ratio_0.05/mesh.obj

# Produces:

#     <run-dir>/phase3_renders/highpoly/view_00.png ... view_11.png
#     <run-dir>/phase3_renders/ratio_0.5/view_00.png ... view_11.png
#     ... etc for every ratio subfolder found
# """
# import argparse
# import math
# import os
# import sys

# import bpy
# import mathutils


# # --------------------------------------------------------------------------
# # CLI args (Blender passes its own args before "--", ours come after)
# # --------------------------------------------------------------------------

# def parse_args():
#     argv = sys.argv
#     if "--" in argv:
#         argv = argv[argv.index("--") + 1:]
#     else:
#         argv = []

#     p = argparse.ArgumentParser()
#     p.add_argument("--run-dir", required=True,
#                     help="Path to data/outputs/<run_id>")
#     p.add_argument("--views", type=int, default=12,
#                     help="Total number of camera views (8 ring + 4 top by default)")
#     p.add_argument("--resolution", type=int, default=1024,
#                     help="Square render resolution in pixels")
#     p.add_argument("--ring-views", type=int, default=8,
#                     help="Number of views in the lower equatorial ring")
#     p.add_argument("--top-views", type=int, default=4,
#                     help="Number of views in the upper ring")
#     return p.parse_args(argv)


# # --------------------------------------------------------------------------
# # Scene setup helpers
# # --------------------------------------------------------------------------

# def reset_scene():
#     bpy.ops.wm.read_factory_settings(use_empty=True)


# def import_obj(filepath):
#     """Import an OBJ (with its MTL/texture if present) and return the
#     imported objects as a list."""
#     before = set(bpy.data.objects)
#     bpy.ops.wm.obj_import(filepath=filepath)
#     after = set(bpy.data.objects)
#     return list(after - before)


# def compute_world_bbox(objects):
#     """Axis-aligned bounding box across all given objects, in world space."""
#     mins = mathutils.Vector((math.inf, math.inf, math.inf))
#     maxs = mathutils.Vector((-math.inf, -math.inf, -math.inf))
#     for obj in objects:
#         if obj.type != "MESH":
#             continue
#         for corner in obj.bound_box:
#             world_corner = obj.matrix_world @ mathutils.Vector(corner)
#             mins.x, mins.y, mins.z = min(mins.x, world_corner.x), min(mins.y, world_corner.y), min(mins.z, world_corner.z)
#             maxs.x, maxs.y, maxs.z = max(maxs.x, world_corner.x), max(maxs.y, world_corner.y), max(maxs.z, world_corner.z)
#     center = (mins + maxs) / 2.0
#     radius = (maxs - mins).length / 2.0
#     return center, radius


# def build_camera_rig(center, radius, ring_views, top_views, margin=1.6):
#     """
#     Build a list of (location, rotation_quaternion) pairs for a 2-ring rig:
#       - `ring_views` cameras evenly spaced around the equator at a mild
#         upward tilt (so ground-level silhouette errors are visible)
#       - `top_views` cameras in a higher ring looking down, catching
#         pole/top geometry that a flat turntable would miss

#     Distance is derived from `radius` (of the HIGH-POLY bbox) with a margin
#     so the mesh comfortably fills the frame without clipping.
#     """
#     distance = radius * margin / math.tan(math.radians(25))  # ~50mm-equiv FOV assumption, refined by camera data later
#     rig = []

#     # Lower ring: elevation ~15 deg above equator
#     elev_low = math.radians(15)
#     for i in range(ring_views):
#         azim = 2 * math.pi * i / ring_views
#         loc = center + mathutils.Vector((
#             distance * math.cos(elev_low) * math.cos(azim),
#             distance * math.cos(elev_low) * math.sin(azim),
#             distance * math.sin(elev_low),
#         ))
#         rig.append(loc)

#     # Upper ring: elevation ~55 deg, looking down
#     elev_high = math.radians(55)
#     for i in range(top_views):
#         azim = 2 * math.pi * i / top_views + math.pi / top_views  # offset so it doesn't align with lower ring
#         loc = center + mathutils.Vector((
#             distance * math.cos(elev_high) * math.cos(azim),
#             distance * math.cos(elev_high) * math.sin(azim),
#             distance * math.sin(elev_high),
#         ))
#         rig.append(loc)

#     return rig, distance


# def add_camera(name="EvalCamera"):
#     cam_data = bpy.data.cameras.new(name)
#     cam_data.lens_unit = "FOV"
#     cam_data.angle = math.radians(50)  # fixed FOV, consistent across all renders
#     cam_obj = bpy.data.objects.new(name, cam_data)
#     bpy.context.scene.collection.objects.link(cam_obj)
#     return cam_obj


# def point_camera_at(cam_obj, location, target):
#     cam_obj.location = location
#     direction = target - location
#     cam_obj.rotation_mode = "QUATERNION"
#     cam_obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")


# def add_three_point_lighting(center, radius):
#     """Fixed 3-point rig (key, fill, rim) sized relative to mesh radius.
#     Reused identically for every mesh in a run so shading never varies."""
#     specs = [
#         # (name, azimuth_deg, elevation_deg, energy_watts, dist_mult)
#         ("Key",  45,  45, 800, 3.0),
#         ("Fill", -60, 25, 300, 3.5),
#         ("Rim",  180, 60, 500, 3.0),
#     ]
#     for name, az_deg, el_deg, energy, dist_mult in specs:
#         az, el = math.radians(az_deg), math.radians(el_deg)
#         dist = radius * dist_mult
#         loc = center + mathutils.Vector((
#             dist * math.cos(el) * math.cos(az),
#             dist * math.cos(el) * math.sin(az),
#             dist * math.sin(el),
#         ))
#         light_data = bpy.data.lights.new(name=f"{name}Light", type="AREA")
#         light_data.energy = energy
#         light_data.size = radius * 0.5
#         light_obj = bpy.data.objects.new(name=f"{name}Light", object_data=light_data)
#         bpy.context.scene.collection.objects.link(light_obj)
#         light_obj.location = loc
#         direction = center - loc
#         light_obj.rotation_mode = "QUATERNION"
#         light_obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")


# def configure_render(resolution):
#     scene = bpy.context.scene
#     scene.render.engine = "BLENDER_EEVEE"   # Blender 5.1: enum is "BLENDER_EEVEE" even though it's Eevee Next under the hood
#     scene.render.resolution_x = resolution
#     scene.render.resolution_y = resolution
#     scene.render.film_transparent = True
#     scene.render.image_settings.file_format = "PNG"
#     scene.render.image_settings.color_mode = "RGBA"
#     # Eevee Next quality settings — keep modest for 4GB VRAM headless batches
#     scene.eevee.taa_render_samples = 64
#     scene.view_settings.view_transform = "Standard"  # avoid Filmic altering colors across comparisons


# def clear_mesh_objects():
#     for obj in list(bpy.data.objects):
#         if obj.type in ("MESH",):
#             bpy.data.objects.remove(obj, do_unlink=True)


# # --------------------------------------------------------------------------
# # Main per-mesh render routine
# # --------------------------------------------------------------------------

# def render_mesh(obj_path, out_dir, rig_locations, center, resolution):
#     os.makedirs(out_dir, exist_ok=True)

#     objects = import_obj(obj_path)
#     if not objects:
#         print(f"[WARN] No objects imported from {obj_path}, skipping.")
#         return

#     scene = bpy.context.scene
#     cam_obj = add_camera()
#     scene.camera = cam_obj

#     for i, loc in enumerate(rig_locations):
#         point_camera_at(cam_obj, loc, center)
#         scene.render.filepath = os.path.join(out_dir, f"view_{i:02d}.png")
#         bpy.ops.render.render(write_still=True)
#         print(f"  rendered {scene.render.filepath}")

#     # Clean up mesh + camera before next mesh import (lights are reused)
#     for obj in objects:
#         bpy.data.objects.remove(obj, do_unlink=True)
#     bpy.data.objects.remove(cam_obj, do_unlink=True)


# def main():
#     args = parse_args()
#     run_dir = os.path.abspath(args.run_dir)
#     highpoly_obj = os.path.join(run_dir, "phase1_highpoly", "mesh.obj")
#     lowpoly_root = os.path.join(run_dir, "phase2_lowpoly")
#     out_root = os.path.join(run_dir, "phase3_renders")

#     if not os.path.isfile(highpoly_obj):
#         raise FileNotFoundError(f"High-poly reference mesh not found: {highpoly_obj}")

#     # --- Step 1: reset scene, import high-poly mesh to compute the locked bbox ---
#     reset_scene()
#     hp_objects = import_obj(highpoly_obj)
#     center, radius = compute_world_bbox(hp_objects)
#     print(f"[INFO] High-poly bbox center={center[:]}, radius={radius:.4f}")

#     rig_locations, distance = build_camera_rig(
#         center, radius, args.ring_views, args.top_views
#     )
#     print(f"[INFO] Camera rig: {len(rig_locations)} views, distance={distance:.4f} (locked)")

#     configure_render(args.resolution)
#     add_three_point_lighting(center, radius)

#     # Remove high-poly mesh now that bbox/rig are locked in; re-import per mesh below
#     for obj in hp_objects:
#         bpy.data.objects.remove(obj, do_unlink=True)

#     # --- Step 2: render high-poly reference itself, using the same locked rig ---
#     render_mesh(highpoly_obj, os.path.join(out_root, "highpoly"),
#                 rig_locations, center, args.resolution)

#     # --- Step 3: render every ratio_X mesh found under phase2_lowpoly, same rig ---
#     if os.path.isdir(lowpoly_root):
#         for ratio_name in sorted(os.listdir(lowpoly_root)):
#             ratio_dir = os.path.join(lowpoly_root, ratio_name)
#             obj_path = os.path.join(ratio_dir, "mesh.obj")
#             if os.path.isfile(obj_path):
#                 print(f"[INFO] Rendering {ratio_name} ...")
#                 render_mesh(obj_path, os.path.join(out_root, ratio_name),
#                             rig_locations, center, args.resolution)
#             else:
#                 print(f"[WARN] No mesh.obj in {ratio_dir}, skipping.")
#     else:
#         print(f"[WARN] No phase2_lowpoly directory found at {lowpoly_root}")

#     print("[DONE] Phase 3 rendering complete.")


# if __name__ == "__main__":
#     main()
"""
Phase 3 — Evaluation render harness (Blender 5.1, headless)

Renders a fixed 12-view camera rig around a mesh, using a bounding box
computed ONCE from the high-poly reference mesh and reused verbatim for
every ratio, so framing never confounds the geometry/texture comparison.

Usage (from PowerShell, one run_id at a time):

    blender --background --python render_views.py -- ^
        --run-dir "data/outputs/chair_run1" ^
        --views 12

Expects this directory layout (already produced by Phase 1 / Phase 2):

    <run-dir>/phase1_highpoly/mesh.obj      (+ texture.png)
    <run-dir>/phase2_lowpoly/ratio_0.5/mesh.obj
    <run-dir>/phase2_lowpoly/ratio_0.2/mesh.obj
    <run-dir>/phase2_lowpoly/ratio_0.1/mesh.obj
    <run-dir>/phase2_lowpoly/ratio_0.05/mesh.obj

Produces:

    <run-dir>/phase3_renders/highpoly/view_00.png ... view_11.png
    <run-dir>/phase3_renders/ratio_0.5/view_00.png ... view_11.png
    ... etc for every ratio subfolder found
"""

import argparse
import math
import os
import sys

import bpy
import mathutils


# --------------------------------------------------------------------------
# CLI args (Blender passes its own args before "--", ours come after)
# --------------------------------------------------------------------------

def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True,
                    help="Path to data/outputs/<run_id>")
    p.add_argument("--views", type=int, default=12,
                    help="Total number of camera views (8 ring + 4 top by default)")
    p.add_argument("--resolution", type=int, default=1024,
                    help="Square render resolution in pixels")
    p.add_argument("--ring-views", type=int, default=8,
                    help="Number of views in the lower equatorial ring")
    p.add_argument("--top-views", type=int, default=4,
                    help="Number of views in the upper ring")
    return p.parse_args(argv)


# --------------------------------------------------------------------------
# Scene setup helpers
# --------------------------------------------------------------------------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_obj(filepath, texture_path=None):
    """Import an OBJ and return the imported objects as a list.

    - forward_axis/up_axis correct for OBJ's Y-up convention vs Blender's
      Z-up (this replaces any manual -90deg X rotation).
    - If texture_path is given and an object has no image texture already
      linked (common for TripoSR output, which ships mesh.obj + texture.png
      with no .mtl connecting them), a Principled BSDF material is built
      manually and the image is wired into Base Color.
    """
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(
        filepath=filepath,
        forward_axis="Y",
        up_axis="Z",
    )
    after = set(bpy.data.objects)
    imported = list(after - before)

    if texture_path and os.path.isfile(texture_path):
        for obj in imported:
            if obj.type != "MESH":
                continue
            if not _has_image_texture(obj):
                _attach_texture(obj, texture_path)

    return imported


def _has_image_texture(obj):
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                return True
    return False


def _attach_texture(obj, texture_path):
    mat = bpy.data.materials.new(name=f"{obj.name}_mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.image = bpy.data.images.load(texture_path)
    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

    obj.data.materials.clear()
    obj.data.materials.append(mat)


def compute_world_bbox(objects):
    """Axis-aligned bounding box across all given objects, in world space."""
    mins = mathutils.Vector((math.inf, math.inf, math.inf))
    maxs = mathutils.Vector((-math.inf, -math.inf, -math.inf))
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            mins.x, mins.y, mins.z = min(mins.x, world_corner.x), min(mins.y, world_corner.y), min(mins.z, world_corner.z)
            maxs.x, maxs.y, maxs.z = max(maxs.x, world_corner.x), max(maxs.y, world_corner.y), max(maxs.z, world_corner.z)
    center = (mins + maxs) / 2.0
    radius = (maxs - mins).length / 2.0
    return center, radius


def build_camera_rig(center, radius, ring_views, top_views, margin=1.6):
    """
    Build a list of (location, rotation_quaternion) pairs for a 2-ring rig:
      - `ring_views` cameras evenly spaced around the equator at a mild
        upward tilt (so ground-level silhouette errors are visible)
      - `top_views` cameras in a higher ring looking down, catching
        pole/top geometry that a flat turntable would miss

    Distance is derived from `radius` (of the HIGH-POLY bbox) with a margin
    so the mesh comfortably fills the frame without clipping.
    """
    distance = radius * margin / math.tan(math.radians(25))  # ~50mm-equiv FOV assumption, refined by camera data later
    rig = []

    # Lower ring: elevation ~15 deg above equator
    elev_low = math.radians(15)
    for i in range(ring_views):
        azim = 2 * math.pi * i / ring_views
        loc = center + mathutils.Vector((
            distance * math.cos(elev_low) * math.cos(azim),
            distance * math.cos(elev_low) * math.sin(azim),
            distance * math.sin(elev_low),
        ))
        rig.append(loc)

    # Upper ring: elevation ~55 deg, looking down
    elev_high = math.radians(55)
    for i in range(top_views):
        azim = 2 * math.pi * i / top_views + math.pi / top_views  # offset so it doesn't align with lower ring
        loc = center + mathutils.Vector((
            distance * math.cos(elev_high) * math.cos(azim),
            distance * math.cos(elev_high) * math.sin(azim),
            distance * math.sin(elev_high),
        ))
        rig.append(loc)

    return rig, distance


def add_camera(name="EvalCamera"):
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens_unit = "FOV"
    cam_data.angle = math.radians(50)  # fixed FOV, consistent across all renders
    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    return cam_obj


def point_camera_at(cam_obj, location, target):
    cam_obj.location = location
    direction = target - location
    cam_obj.rotation_mode = "QUATERNION"
    cam_obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")


LIGHT_BRIGHTNESS_MULTIPLIER = 0.15  # single knob to tune overall exposure; lower = dimmer


def add_three_point_lighting(center, radius):
    """Fixed 3-point rig (key, fill, rim) sized relative to mesh radius.
    Reused identically for every mesh in a run so shading never varies.

    Energies were originally too high (800/300/500W), blowing out detail
    needed to spot decimation/UV errors. Scaled down + routed through
    LIGHT_BRIGHTNESS_MULTIPLIER so you can tune brightness in one place."""
    specs = [
        # (name, azimuth_deg, elevation_deg, energy_watts, dist_mult)
        ("Key",  45,  45, 150, 3.0),
        ("Fill", -60, 25,  60, 3.5),
        ("Rim",  180, 60,  90, 3.0),
    ]
    for name, az_deg, el_deg, energy, dist_mult in specs:
        energy = energy * LIGHT_BRIGHTNESS_MULTIPLIER
        az, el = math.radians(az_deg), math.radians(el_deg)
        dist = radius * dist_mult
        loc = center + mathutils.Vector((
            dist * math.cos(el) * math.cos(az),
            dist * math.cos(el) * math.sin(az),
            dist * math.sin(el),
        ))
        light_data = bpy.data.lights.new(name=f"{name}Light", type="AREA")
        light_data.energy = energy
        light_data.size = radius * 0.5
        light_obj = bpy.data.objects.new(name=f"{name}Light", object_data=light_data)
        bpy.context.scene.collection.objects.link(light_obj)
        light_obj.location = loc
        direction = center - loc
        light_obj.rotation_mode = "QUATERNION"
        light_obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")


def configure_render(resolution):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"  # Blender 5.1: enum is "BLENDER_EEVEE" even though it's Eevee Next under the hood
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    # Eevee Next quality settings — keep modest for 4GB VRAM headless batches
    scene.eevee.taa_render_samples = 64
    scene.view_settings.view_transform = "Standard"  # avoid Filmic altering colors across comparisons


def clear_mesh_objects():
    for obj in list(bpy.data.objects):
        if obj.type in ("MESH",):
            bpy.data.objects.remove(obj, do_unlink=True)


# --------------------------------------------------------------------------
# Main per-mesh render routine
# --------------------------------------------------------------------------

def render_mesh(obj_path, out_dir, rig_locations, center, resolution):
    os.makedirs(out_dir, exist_ok=True)

    texture_path = os.path.join(os.path.dirname(obj_path), "texture.png")
    objects = import_obj(obj_path, texture_path=texture_path)
    if not objects:
        print(f"[WARN] No objects imported from {obj_path}, skipping.")
        return

    scene = bpy.context.scene
    cam_obj = add_camera()
    scene.camera = cam_obj

    for i, loc in enumerate(rig_locations):
        point_camera_at(cam_obj, loc, center)
        scene.render.filepath = os.path.join(out_dir, f"view_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  rendered {scene.render.filepath}")

    # Clean up mesh + camera before next mesh import (lights are reused)
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.objects.remove(cam_obj, do_unlink=True)


def main():
    args = parse_args()
    run_dir = os.path.abspath(args.run_dir)
    highpoly_obj = os.path.join(run_dir, "phase1_highpoly", "mesh.obj")
    lowpoly_root = os.path.join(run_dir, "phase2_lowpoly")
    out_root = os.path.join(run_dir, "phase3_renders")

    if not os.path.isfile(highpoly_obj):
        raise FileNotFoundError(f"High-poly reference mesh not found: {highpoly_obj}")

    # --- Step 1: reset scene, import high-poly mesh to compute the locked bbox ---
    reset_scene()
    hp_texture = os.path.join(os.path.dirname(highpoly_obj), "texture.png")
    hp_objects = import_obj(highpoly_obj, texture_path=hp_texture)
    center, radius = compute_world_bbox(hp_objects)
    print(f"[INFO] High-poly bbox center={center[:]}, radius={radius:.4f}")

    rig_locations, distance = build_camera_rig(
        center, radius, args.ring_views, args.top_views
    )
    print(f"[INFO] Camera rig: {len(rig_locations)} views, distance={distance:.4f} (locked)")

    configure_render(args.resolution)
    add_three_point_lighting(center, radius)

    # Remove high-poly mesh now that bbox/rig are locked in; re-import per mesh below
    for obj in hp_objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    # --- Step 2: render high-poly reference itself, using the same locked rig ---
    render_mesh(highpoly_obj, os.path.join(out_root, "highpoly"),
                rig_locations, center, args.resolution)

    # --- Step 3: render every ratio_X mesh found under phase2_lowpoly, same rig ---
    if os.path.isdir(lowpoly_root):
        for ratio_name in sorted(os.listdir(lowpoly_root)):
            ratio_dir = os.path.join(lowpoly_root, ratio_name)
            obj_path = os.path.join(ratio_dir, "mesh.obj")
            if os.path.isfile(obj_path):
                print(f"[INFO] Rendering {ratio_name} ...")
                render_mesh(obj_path, os.path.join(out_root, ratio_name),
                            rig_locations, center, args.resolution)
            else:
                print(f"[WARN] No mesh.obj in {ratio_dir}, skipping.")
    else:
        print(f"[WARN] No phase2_lowpoly directory found at {lowpoly_root}")

    print("[DONE] Phase 3 rendering complete.")


if __name__ == "__main__":
    main()