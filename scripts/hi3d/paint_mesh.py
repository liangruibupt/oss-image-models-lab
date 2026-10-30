#!/usr/bin/env python3
"""Color a mesh with Hunyuan3D-2 Paint (texture synthesis), conditioned on a ref image.

Usage: paint_mesh.py INPUT_MESH.glb REF_IMAGE.png OUTPUT.glb [TARGET_FACES]

Hunyuan3D-Paint renders the mesh from multiple views, runs a view-consistent diffusion
conditioned on REF_IMAGE, and bakes the result into a UV texture -> a *colored* glb.
This is the step Hi3D cannot do (Hi3D = geometry only). ~16GB VRAM with shape+paint.

IMPORTANT: the paint pipeline's UV-unwrap (xatlas) + rasterize-bake step runs on CPU and
HANGS on a raw, ultra-dense Hi3D-refined mesh (1M+ faces, non-manifold). Hunyuan's own
demos paint a reduced ~40K-face mesh. So we clean (remove floaters/degenerate faces) and
reduce to TARGET_FACES (default 40000) BEFORE painting -- this also yields the game-ready
low-poly textured asset the task wants.
"""
import sys, os, time, trimesh

INP, REF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
TARGET_FACES = int(sys.argv[4]) if len(sys.argv) > 4 else 40000

from hy3dgen.texgen import Hunyuan3DPaintPipeline

print(f"=== load paint pipeline (tencent/Hunyuan3D-2) ===", flush=True)
pipe = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2")

print(f"=== load mesh {INP} ===", flush=True)
mesh = trimesh.load(INP, force="mesh")
print(f"mesh verts={len(mesh.vertices)} faces={len(mesh.faces)}", flush=True)

# --- clean + reduce BEFORE paint (avoids the xatlas UV-unwrap hang on dense meshes) ---
print(f"=== preprocess: clean + reduce to ~{TARGET_FACES} faces ===", flush=True)
tP = time.time()
try:
    from hy3dgen.shapegen import FloaterRemover, DegenerateFaceRemover, FaceReducer
    mesh = FloaterRemover()(mesh)
    mesh = DegenerateFaceRemover()(mesh)
    mesh = FaceReducer()(mesh, max_facenum=TARGET_FACES)
    print(f"  hy3dgen reducers -> verts={len(mesh.vertices)} faces={len(mesh.faces)}", flush=True)
except Exception as e:
    print(f"  hy3dgen reducers unavailable ({e}); trying trimesh quadric decimation", flush=True)
    try:
        mesh = mesh.simplify_quadric_decimation(face_count=TARGET_FACES)
    except Exception as e2:
        print(f"  trimesh decimation failed ({e2}); painting as-is (may be slow)", flush=True)
    print(f"  after reduce -> verts={len(mesh.vertices)} faces={len(mesh.faces)}", flush=True)
# merge duplicate verts + drop unreferenced so UV-unwrap gets a clean manifold
mesh.merge_vertices()
mesh.remove_unreferenced_vertices()
print(f"  cleaned -> verts={len(mesh.vertices)} faces={len(mesh.faces)} ({time.time()-tP:.1f}s)", flush=True)

print(f"=== paint conditioned on {REF} ===", flush=True)
t0 = time.time()
painted = pipe(mesh, image=REF)
print(f"paint elapsed {time.time()-t0:.1f}s", flush=True)

# painted may be a trimesh.Trimesh with a visual/material (texture)
painted.export(OUT)
print(f"=== exported {OUT} ===", flush=True)
try:
    v = painted.visual
    print("visual kind:", type(v).__name__)
    if hasattr(v, "material") and getattr(v.material, "baseColorTexture", None) is not None:
        print("has baseColorTexture:", v.material.baseColorTexture.size)
except Exception as e:
    print("visual inspect:", e)
print("PAINT_DONE", flush=True)
