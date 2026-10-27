#!/usr/bin/env python3
"""Hi3D refined .glb -> printable STL, with watertightness validation + repair.

Usage: to_printable_stl.py INPUT.glb OUTPUT.stl [REPORT.json]

Pipeline:
  1. Load the Hi3D geometry (.glb).
  2. Measure print-readiness BEFORE repair: watertight?, # boundary edges (holes),
     winding consistency, # components, volume.
  3. Repair toward a watertight manifold: merge duplicate verts, drop degenerate +
     duplicate faces, fix winding/normals, fill holes, keep the largest component.
  4. Re-measure AFTER repair; export binary STL.
  5. Emit a JSON report (and print a human summary).

Uses trimesh for the mesh algebra; pymeshlab (if present) for robust hole-filling.
No GPU needed. STL carries geometry only -- exactly what a slicer/printer consumes.
"""
import sys, json, math

import numpy as np
import trimesh


def stats(m: trimesh.Trimesh) -> dict:
    """Print-readiness facts for a mesh."""
    # boundary (open) edges = edges referenced by exactly one face -> holes
    edges_sorted = np.sort(m.edges, axis=1)
    _, idx, counts = np.unique(edges_sorted, axis=0, return_index=True, return_counts=True)
    boundary_edges = int((counts == 1).sum())
    try:
        vol = float(m.volume)
    except Exception:
        vol = float("nan")
    return {
        "vertices": int(len(m.vertices)),
        "faces": int(len(m.faces)),
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "boundary_edges_holes": boundary_edges,
        "components": int(len(m.split(only_watertight=False))),
        "volume_mm3_or_units3": round(vol, 4) if vol == vol else None,
        "is_volume": bool(m.is_volume),  # watertight + consistent winding + positive volume
        "bbox": [round(x, 4) for x in m.extents.tolist()],
    }


def repair(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Two-stage: try light topological repair; if still not a watertight volume,
    fall back to a voxel remesh (the industry-standard fix for AI triangle-soup
    meshes going to print -- watertight + 2-manifold by construction)."""
    m = m.copy()
    # 1) basic cleanup
    m.merge_vertices()
    m.update_faces(m.unique_faces())
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    # 2) keep the largest connected component (drop stray floaters)
    comps = m.split(only_watertight=False)
    if len(comps) > 1:
        m = max(comps, key=lambda c: len(c.faces))
    # 3) consistent winding + outward normals
    trimesh.repair.fix_winding(m)
    trimesh.repair.fix_inversion(m)
    trimesh.repair.fix_normals(m)
    # 4) light hole fill
    if not m.is_watertight:
        trimesh.repair.fill_holes(m)
    # 5) if still not a printable solid, voxel-remesh (guaranteed watertight manifold)
    if not (m.is_watertight and m.is_volume):
        print("  [not a clean solid after topo repair -> voxel remesh]")
        vr = _voxel_remesh(m)
        if vr is not None:
            m = vr
    return m


def _voxel_remesh(m: trimesh.Trimesh, target_long_axis_voxels: int = 320):
    """Rebuild a watertight manifold by voxelizing + marching cubes.
    pitch is chosen so the longest bbox axis spans ~target_long_axis_voxels,
    preserving surface detail while guaranteeing a closed solid."""
    try:
        pitch = float(max(m.extents)) / target_long_axis_voxels
        vg = m.voxelized(pitch=pitch).fill()   # fill() makes the interior solid
        r = vg.marching_cubes
        r.merge_vertices()
        r.update_faces(r.nondegenerate_faces())
        trimesh.repair.fix_normals(r)
        # keep largest component (marching cubes is already manifold/closed)
        comps = r.split(only_watertight=False)
        if len(comps) > 1:
            r = max(comps, key=lambda c: len(c.faces))
        print(f"  [voxel remesh pitch={pitch:.5f} -> verts {len(r.vertices)} faces {len(r.faces)} "
              f"watertight={r.is_watertight}]")
        return r
    except Exception as e:
        print(f"  [voxel remesh failed: {e}]")
        return None


def _pymeshlab_close(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Robust hole-closing via pymeshlab, if available."""
    try:
        import pymeshlab
    except Exception as e:
        print(f"  [pymeshlab unavailable: {e} -- skipping heavy hole-fill]")
        return m
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(m.vertices, m.faces))
    for fn in ("meshing_remove_duplicate_vertices", "meshing_remove_duplicate_faces",
               "meshing_remove_null_faces", "meshing_remove_unreferenced_vertices"):
        try: getattr(ms, fn)()
        except Exception: pass
    # pymeshlab close_holes REQUIRES 2-manifold edges; Hi3D meshes have non-manifold
    # edges (shared by >2 faces). Repair those first, then re-clean, then close holes.
    for fn in ("meshing_repair_non_manifold_edges", "meshing_repair_non_manifold_vertices"):
        try: getattr(ms, fn)()
        except Exception as e: print(f"  [{fn}: {e}]")
    for fn in ("meshing_remove_duplicate_faces", "meshing_remove_null_faces",
               "meshing_remove_unreferenced_vertices"):
        try: getattr(ms, fn)()
        except Exception: pass
    # close holes up to a generous boundary size
    try:
        ms.meshing_close_holes(maxholesize=100000, newfaceselected=False)
    except Exception as e:
        print(f"  [close_holes: {e}]")
    # a final non-manifold sweep in case hole-closing reintroduced any
    try: ms.meshing_repair_non_manifold_edges()
    except Exception: pass
    out = ms.current_mesh()
    r = trimesh.Trimesh(vertices=out.vertex_matrix(), faces=out.face_matrix(), process=True)
    trimesh.repair.fix_normals(r)
    return r


def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    inp, outp = sys.argv[1], sys.argv[2]
    report_path = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"=== load {inp} ===")
    m = trimesh.load(inp, force="mesh")
    before = stats(m)
    print("BEFORE repair:", json.dumps(before, indent=2, ensure_ascii=False))

    print("=== repair ===")
    r = repair(m)
    after = stats(r)
    print("AFTER repair: ", json.dumps(after, indent=2, ensure_ascii=False))

    r.export(outp)  # .stl -> binary STL
    print(f"=== exported {outp} ===")

    verdict = "PRINTABLE" if after["watertight"] and after["is_volume"] else \
              ("LIKELY_PRINTABLE" if after["boundary_edges_holes"] == 0 else "NEEDS_MANUAL_REPAIR")
    report = {"input": inp, "output": outp, "before": before, "after": after,
              "verdict": verdict}
    if report_path:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"=== report -> {report_path} ===")
    print(f"VERDICT: {verdict}")
    print("PRINTABLE_DONE")


if __name__ == "__main__":
    main()
