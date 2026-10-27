#!/usr/bin/env python3
"""Blender headless: Hi3D high-poly .glb -> game-ready low-poly + baked normal/AO maps.

Run with Blender's bundled Python:
  blender --background --python blender_retopo_bake.py -- INPUT.glb OUTDIR TARGET_FACES TEX

What it does (the Blender half of the game-asset pipeline Hi3D cannot do itself):
  1. Import the Hi3D high-poly mesh (2M tris, triangle soup, no UV/material).
  2. Duplicate it; decimate the copy to ~TARGET_FACES -> the LOW-POLY game mesh.
     (Decimate is the automatic retopo proxy; true quad retopo is manual/ZRemesher,
      out of scope for a headless batch -- decimate is the honest automatable step.)
  3. Smart UV unwrap the low-poly.
  4. Bake NORMAL and AO from the high-poly onto the low-poly's UVs (selected-to-active),
     so the low mesh *looks* like the high mesh under lighting.
  5. Export low-poly .glb (with the baked textures packed) + standalone PNGs.
  6. Print a face-count / UV / bake summary.

Honest scope note: this proves the automatable path (decimate + UV + bake). A shipping
asset usually still wants hand/ZRemesher quad retopo; the normal-bake recovers the
high-poly detail visually regardless of the low-poly being tris.
"""
import bpy, sys, os, json

argv = sys.argv[sys.argv.index("--") + 1:]
INPUT = argv[0]
OUTDIR = argv[1]
TARGET_FACES = int(argv[2]) if len(argv) > 2 else 20000
TEX = int(argv[3]) if len(argv) > 3 else 2048
os.makedirs(OUTDIR, exist_ok=True)


def log(*a): print("[retopo-bake]", *a); sys.stdout.flush()


# --- clean scene ---
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- import high-poly ---
log("import", INPUT)
bpy.ops.import_scene.gltf(filepath=INPUT)
mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not mesh_objs:
    log("NO_MESH_IMPORTED"); sys.exit(3)
# join all imported meshes into one high-poly
bpy.ops.object.select_all(action="DESELECT")
for o in mesh_objs: o.select_set(True)
bpy.context.view_layer.objects.active = mesh_objs[0]
if len(mesh_objs) > 1: bpy.ops.object.join()
high = bpy.context.view_layer.objects.active
high.name = "HIGH"
high_faces = len(high.data.polygons)
log("high-poly faces:", high_faces)

# --- make low-poly copy + decimate ---
bpy.ops.object.select_all(action="DESELECT")
high.select_set(True); bpy.context.view_layer.objects.active = high
bpy.ops.object.duplicate()
low = bpy.context.view_layer.objects.active
low.name = "LOW"
ratio = min(1.0, max(0.0005, TARGET_FACES / max(1, high_faces)))
dec = low.modifiers.new("dec", "DECIMATE")
dec.ratio = ratio
bpy.ops.object.modifier_apply(modifier="dec")
low_faces = len(low.data.polygons)
log(f"low-poly faces: {low_faces} (ratio {ratio:.4f})")

# --- smart UV unwrap the low-poly ---
bpy.ops.object.select_all(action="DESELECT")
low.select_set(True); bpy.context.view_layer.objects.active = low
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
has_uv = len(low.data.uv_layers) > 0
log("low-poly has UV:", has_uv)

# --- material + image targets for baking ---
mat = bpy.data.materials.new("baked"); mat.use_nodes = True
low.data.materials.clear(); low.data.materials.append(mat)
nt = mat.node_tree

def new_image(name):
    img = bpy.data.images.new(name, TEX, TEX, alpha=False, float_buffer=False)
    return img

def bake_pass(bake_type, img, extra=None):
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img; nt.nodes.active = node
    # select high (source) then low (active target) for selected-to-active
    bpy.ops.object.select_all(action="DESELECT")
    high.select_set(True); low.select_set(True)
    bpy.context.view_layer.objects.active = low
    # cage distance MUST scale with the model, else rays miss the high-poly and the
    # normal map bakes flat-blue. Use ~8% of the low-poly bbox diagonal.
    diag = (low.dimensions.x**2 + low.dimensions.y**2 + low.dimensions.z**2) ** 0.5
    cage = max(1e-4, diag * 0.08)
    kw = dict(type=bake_type, use_selected_to_active=True,
              cage_extrusion=cage, max_ray_distance=cage * 1.5,
              margin=max(4, TEX // 256))
    if extra: kw.update(extra)
    log(f"bake {bake_type} cage={cage:.4f} (diag={diag:.3f})")
    bpy.ops.object.bake(**kw)
    nt.nodes.remove(node)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
try:
    scene.cycles.device = "GPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "CUDA"; prefs.get_devices()
    for d in prefs.devices: d.use = True
    log("cycles GPU enabled")
except Exception as e:
    log("cycles GPU unavailable, CPU:", e)
scene.cycles.samples = 16

normal_img = new_image("normal"); ao_img = new_image("ao")
log("baking NORMAL high->low ...");  bake_pass("NORMAL", normal_img)
log("baking AO high->low ...");      bake_pass("AO", ao_img)

normal_path = os.path.join(OUTDIR, "normal.png")
ao_path = os.path.join(OUTDIR, "ao.png")
for img, p in ((normal_img, normal_path), (ao_img, ao_path)):
    img.filepath_raw = p; img.file_format = "PNG"; img.save()
log("saved", normal_path, ao_path)

# wire the baked normal into the material so the exported glb shows detail
norm_node = nt.nodes.new("ShaderNodeTexImage"); norm_node.image = normal_img
norm_node.image.colorspace_settings.name = "Non-Color"
nmap = nt.nodes.new("ShaderNodeNormalMap")
bsdf = nt.nodes.get("Principled BSDF")
nt.links.new(norm_node.outputs["Color"], nmap.inputs["Color"])
if bsdf: nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

# --- export low-poly glb ---
bpy.ops.object.select_all(action="DESELECT"); low.select_set(True)
bpy.context.view_layer.objects.active = low
low_glb = os.path.join(OUTDIR, "low_poly_baked.glb")
bpy.ops.export_scene.gltf(filepath=low_glb, use_selection=True,
                          export_format="GLB", export_image_format="AUTO")
log("exported", low_glb)

summary = {"input": INPUT, "high_faces": high_faces, "low_faces": low_faces,
           "decimate_ratio": round(ratio, 5), "has_uv": has_uv, "tex_size": TEX,
           "low_glb": low_glb, "normal_map": normal_path, "ao_map": ao_path}
with open(os.path.join(OUTDIR, "retopo_summary.json"), "w") as f:
    json.dump(summary, f, indent=2)
log("SUMMARY", json.dumps(summary))
log("RETOPO_BAKE_DONE")
