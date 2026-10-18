import sys, os
sys.path.insert(0, "/home/claude/work")
import numpy as np, bpy, bmesh
import mh, shape, pose, posing, garment
from common import *
OUT = "/home/claude/work/out"
reset_scene()
V = mh.build_shape(macro=shape.MACRO, details=shape.face_details())
rig = pose.Rig(V)
R, P = posing.make_pose(rig)
posing.hand_pose(rig, R, "L", hand_dir=(-0.3, -0.2, 1.0), palm_normal=(0.2, 1.0, 0.0))
posing.hand_pose(rig, R, "R", hand_dir=(0.5, -0.2, 0.7), palm_normal=(-0.2, 1.0, 0.0))
Pp = rig.pose(R)
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)
base_bm, used, remap = garment.build_base(rig, Pp)
for v in base_bm.verts:
    v.co.z += 0.0
# base was built from rig.pose positions without Z offset -> apply
Pp0 = Pp.copy(); Pp0[:, 2] -= garment.Z_OFF
base_bm, used, remap = garment.build_base(rig, Pp0)
for v in base_bm.verts: v.co.z += garment.Z_OFF
garment.subdivide_bm(base_bm, 1)
loops = garment.boundary_loops(base_bm)
loops.sort(key=lambda l: np.mean([v.co.z for v in l]))
waist = loops[0] if len(loops[0]) > 60 else [l for l in loops if len(l) > 60 and np.mean([v.co.z for v in l]) < 1.3][0]
print("loops", [(len(l), round(np.mean([v.co.z for v in l]),3)) for l in loops])
wp, wv, c = garment.ordered_loop(waist)
verts, faces, uv = garment.build_skirt(wp, rows=90)
sk = mh.mesh_from_arrays("Skirt", verts, faces)
bo = garment.bm_to_object(base_bm, "Bodice")
for o in (body, bo, sk):
    m, nt, out = new_material("clay_"+o.name); b = N(nt, 'ShaderNodeBsdfPrincipled'); L(nt, b.outputs[0], out.inputs[0])
    col = (0.55,0.30,0.25,1) if o is body else ((0.2,0.1,0.45,1) if o is bo else (0.35,0.2,0.6,1))
    setin(b, "Base Color", col); setin(b, "Roughness", 0.6); o.data.materials.append(m)
body.hide_render = True
fl = mh.mesh_from_arrays("Floor", [(-5,-5,0),(5,-5,0),(5,5,0),(-5,5,0)], [[0,1,2,3]])
set_world((0.25,0.25,0.28), 1.0); setup_cycles(10, 480, 720)
add_area("Key", (1.5, -3, 3), (0, 0, 1.0), 400, 2.5); add_area("Fill", (-2.5, -2, 1.5), (0, 0, 1.0), 150, 3)
cams = {"front": add_camera("F", (0, -4.2, 1.0), (0, 0, 1.0), lens=50), "three": add_camera("T", (2.8, -3.4, 1.4), (0, 0, 1.0), lens=50)}
for v in ("front", "three"): render_to(f"{OUT}/skirt0_{v}.png", cams[v])
