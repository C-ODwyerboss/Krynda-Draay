import sys, os, math
sys.path.insert(0, "/home/claude/work")
import numpy as np, bpy
import mh, shape, pose, posing
from common import *
OUT = os.environ.get("OUT", "/home/claude/work/out"); os.makedirs(OUT, exist_ok=True)
SAMPLES = int(os.environ.get("SAMPLES", "12"))
reset_scene()
V = mh.build_shape(macro=shape.MACRO, details=shape.face_details())
rig = pose.Rig(V)
R, P = posing.make_pose(rig)
posing.hand_pose(rig, R, "L", hand_dir=(-0.3, -0.2, 1.0), palm_normal=(0.2, 1.0, 0.0))
posing.hand_pose(rig, R, "R", hand_dir=(0.5, -0.2, 0.7), palm_normal=(-0.2, 1.0, 0.0))
Pp = rig.pose(R)
Pp[:, 2] += 0.82
body = mh.make_mesh("Body", Pp, bl=True)
body.modifiers.new("Sub", 'SUBSURF').levels = 1
m, nt, out = new_material("Skin"); b = N(nt, 'ShaderNodeBsdfPrincipled'); L(nt, b.outputs[0], out.inputs[0])
setin(b, "Base Color", (0.62, 0.38, 0.30, 1)); setin(b, "Roughness", 0.5)
body.data.materials.append(m)
floor = mh.mesh_from_arrays("Floor", [(-5,-5,0),(5,-5,0),(5,5,0),(-5,5,0)], [[0,1,2,3]])
set_world((0.25,0.25,0.28), 1.0)
setup_cycles(SAMPLES, 480, 720)
add_area("Key", (1.5, -3, 3), (0, 0, 1.2), 400, 2.5)
add_area("Fill", (-2.5, -2, 1.5), (0, 0, 1.2), 150, 3)
cams = {"front": add_camera("F", (0, -4.2, 1.2), (0, 0, 1.2), lens=60),
        "three": add_camera("T", (2.6, -3.3, 1.5), (0, 0, 1.25), lens=60),
        "side": add_camera("S", (4.2, 0, 1.2), (0, 0, 1.2), lens=60),
        "top": add_camera("Tp", (0, -1.2, 3.8), (0, -0.1, 1.2), lens=50)}
for v in os.environ.get("VIEWS", "front,three").split(","):
    render_to(os.path.join(OUT, f"pose_{v}.png"), cams[v])
np.save(os.path.join(OUT, "pose_P.npy"), Pp)
