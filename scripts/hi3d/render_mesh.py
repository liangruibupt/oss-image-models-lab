#!/usr/bin/env python3
"""Headless multi-view render of a mesh (shaded + normals) to a contact sheet.
Usage: render_mesh.py <mesh.glb> <out_prefix> [label]
Renders 3 views (front, 3/4, side) as a horizontal strip PNG.
"""
import os, sys
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image, ImageDraw, ImageFont

mesh_path, out_prefix = sys.argv[1], sys.argv[2]
label = sys.argv[3] if len(sys.argv) > 3 else ""
W = H = 512

tm = trimesh.load(mesh_path, force="mesh", process=False)
# normalize to unit radius, center
tm.vertices -= tm.vertices.mean(axis=0)
scale = np.max(np.linalg.norm(tm.vertices, axis=1))
tm.vertices /= (scale + 1e-9)

def render_view(angle_deg, mode="normal"):
    m = tm.copy()
    # rotate around Y
    R = trimesh.transformations.rotation_matrix(np.radians(angle_deg), [0,1,0])
    m.apply_transform(R)
    if mode == "normal":
        m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=None)
        # color by vertex normal
        n = m.vertex_normals
        cols = ((n*0.5+0.5)*255).astype(np.uint8)
        m.visual.vertex_colors = np.concatenate([cols, np.full((len(cols),1),255,np.uint8)],axis=1)
        pm = pyrender.Mesh.from_trimesh(m, smooth=True)
    else:
        pm = pyrender.Mesh.from_trimesh(m, smooth=True)
    scene = pyrender.Scene(bg_color=[0.1,0.1,0.12,1.0], ambient_light=[0.35,0.35,0.35])
    scene.add(pm)
    cam = pyrender.PerspectiveCamera(yfov=np.pi/3.5)
    cp = np.eye(4); cp[2,3]=2.2; cp[1,3]=0.1
    scene.add(cam, pose=cp)
    light = pyrender.DirectionalLight(color=[1,1,1], intensity=3.0)
    lp = np.eye(4); lp[:3,3]=[1,2,2]
    scene.add(light, pose=lp)
    r = pyrender.OffscreenRenderer(W,H)
    color,_ = r.render(scene)
    r.delete()
    return color

views = [render_view(a) for a in (0, 45, 90)]
strip = Image.new("RGB",(W*3, H),(20,20,25))
for i,v in enumerate(views):
    strip.paste(Image.fromarray(v),(i*W,0))
d = ImageDraw.Draw(strip)
if label:
    d.rectangle([0,0,260,28],fill=(0,0,0)); d.text((6,6),label,fill=(120,255,160))
out = out_prefix + ".png"
strip.save(out)
print("SAVED", out, strip.size)
