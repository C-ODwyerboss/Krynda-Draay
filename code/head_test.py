import sys, os, math, time
sys.path.insert(0, "/home/claude/work")
import numpy as np
import bpy
import mh
from common import *

OUT = os.environ.get("OUT", "/home/claude/work/out")
os.makedirs(OUT, exist_ok=True)
SAMPLES = int(os.environ.get("SAMPLES", "48"))
VIEWS = os.environ.get("VIEWS", "front,three").split(",")

reset_scene()

import shape
MACRO = shape.MACRO
DETAILS = shape.face_details()
V = mh.build_shape(macro=MACRO, details=DETAILS)

body = mh.make_mesh("Body", V)
sub = body.modifiers.new("Sub", 'SUBSURF')
sub.levels = 1
sub.render_levels = 2

# --- skin
m, nt, out = new_material("Skin")
b = N(nt, 'ShaderNodeBsdfPrincipled', (0, 0))
L(nt, b.outputs[0], out.inputs[0])
setin(b, "Base Color", (0.62, 0.38, 0.30, 1))
setin(b, "Roughness", 0.42)
setin(b, "Subsurface Weight", 1.0)
setin(b, "Subsurface Radius", (1.0, 0.25, 0.12))
setin(b, "Subsurface Scale", 0.03)
setin(b, "Specular IOR Level", 0.45)
try:
    b.subsurface_method = 'RANDOM_WALK_SKIN'
except Exception:
    pass
body.data.materials.append(m)

# --- eyes (fitted MakeHuman high-poly eyes)
eyeclo = mh.load_mhclo(os.path.join(mh.MH, "eyes/high-poly/high-poly.mhclo"))
EV, EF, EVT, EFT = mh.load_obj_simple(os.path.join(mh.MH, "eyes/high-poly/high-poly.obj"))
P = mh.fit_proxy(eyeclo, V)
print("eye verts", len(P), len(EV))
eye = mh.mesh_from_arrays("Eyes", mh.to_bl(P), EF, EVT, EFT)
em, ent, eout = new_material("Eye")
eb = N(ent, 'ShaderNodeBsdfPrincipled', (0, 0))
L(ent, eb.outputs[0], eout.inputs[0])
setin(eb, "Base Color", (0.8, 0.8, 0.8, 1))
setin(eb, "Roughness", 0.1)
eye.data.materials.append(em)

set_world((0.06, 0.06, 0.07), 1.0)
setup_cycles(SAMPLES, 800, 800)
head = mh.bl_vec(V, mh.group_verts("helper-l-eye")[0])
# find head center from eye helper verts and top
ex = np.mean(mh.to_bl(V[mh.group_verts("helper-l-eye")]), axis=0)
print("eye centre L", ex)
hc = Vector((0.0, ex[1], ex[2] - 0.02))
add_area("Key", (0.7, -1.4, 1.95), hc, 90, 1.2, (1.0, 0.95, 0.9))
add_area("Fill", (-1.0, -1.2, 1.7), hc, 30, 1.5, (0.9, 0.93, 1.0))
add_area("Rim", (-0.3, 1.2, 2.0), hc, 80, 1.0, (1, 1, 1))

cams = {}
cams["front"] = add_camera("CamF", (0.0, hc.y - 1.2, hc.z), hc, lens=85, fstop=8)
cams["three"] = add_camera("CamT", (0.55, hc.y - 1.05, hc.z + 0.02), hc, lens=85, fstop=8)
t = time.time()
for v in VIEWS:
    render_to(os.path.join(OUT, f"head_{v}.png"), cams[v])
    print(v, time.time() - t)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "head_test.blend"))
