#!/usr/bin/env python3
"""Color a mesh with Hunyuan3D-2 Paint (texture synthesis), conditioned on a ref image.

Usage: paint_mesh.py INPUT_MESH.glb REF_IMAGE.png OUTPUT.glb

Hunyuan3D-Paint renders the mesh from multiple views, runs a view-consistent diffusion
conditioned on REF_IMAGE, and bakes the result into a UV texture -> a *colored* glb.
This is the step Hi3D cannot do (Hi3D = geometry only). ~16GB VRAM with shape+paint.
"""
import sys, os, time, trimesh

INP, REF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

from hy3dgen.texgen import Hunyuan3DPaintPipeline

print(f"=== load paint pipeline (tencent/Hunyuan3D-2) ===", flush=True)
pipe = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2")

print(f"=== load mesh {INP} ===", flush=True)
mesh = trimesh.load(INP, force="mesh")
print(f"mesh verts={len(mesh.vertices)} faces={len(mesh.faces)}", flush=True)

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
