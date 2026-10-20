import sys, os, math, time
sys.path.insert(0, "/home/claude/work")
import numpy as np
import bpy
import bmesh
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

# --- skin: principled BSDF + layered bump (fine pores + broader undulation) for realism
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

tc = N(nt, 'ShaderNodeTexCoord', (-1200, -200))
# broad mid-frequency undulation (cheek/forehead subtle volume variation)
n1 = N(nt, 'ShaderNodeTexNoise', (-900, -100), label="SkinUndulation")
n1.inputs['Scale'].default_value = 28.0
n1.inputs['Detail'].default_value = 4.0
n1.inputs['Roughness'].default_value = 0.6
L(nt, tc.outputs['Object'], n1.inputs['Vector'])
bump1 = N(nt, 'ShaderNodeBump', (-650, -100))
bump1.inputs['Strength'].default_value = 0.12
bump1.inputs['Distance'].default_value = 0.0025
L(nt, n1.outputs['Fac'], bump1.inputs['Height'])

# fine pore-scale detail
n2 = N(nt, 'ShaderNodeTexNoise', (-900, -350), label="Pores")
n2.inputs['Scale'].default_value = 420.0
n2.inputs['Detail'].default_value = 6.0
n2.inputs['Roughness'].default_value = 0.7
L(nt, tc.outputs['Object'], n2.inputs['Vector'])
bump2 = N(nt, 'ShaderNodeBump', (-650, -300))
bump2.inputs['Strength'].default_value = 0.045
bump2.inputs['Distance'].default_value = 0.0008
L(nt, n2.outputs['Fac'], bump2.inputs['Height'])
L(nt, bump1.outputs['Normal'], bump2.inputs['Normal'])
L(nt, bump2.outputs['Normal'], b.inputs['Normal'])

# subtle roughness variation (not perfectly uniform shine)
cr = N(nt, 'ShaderNodeValToRGB', (-650, 150))
cr.color_ramp.elements[0].position = 0.35
cr.color_ramp.elements[0].color = (0.36, 0.36, 0.36, 1)
cr.color_ramp.elements[1].position = 0.65
cr.color_ramp.elements[1].color = (0.50, 0.50, 0.50, 1)
L(nt, n1.outputs['Fac'], cr.inputs['Fac'])
L(nt, cr.outputs['Color'], b.inputs['Roughness'])

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
setin(eb, "Base Color", (0.30, 0.47, 0.55, 1))  # pale blue-green iris tint instead of flat grey
setin(eb, "Roughness", 0.08)
eye.data.materials.append(em)

# --- eyebrows: procedural ribbon mesh positioned from eye-socket geometry (no eyebrow asset in the
# sparse MakeHuman clone), coloured a warm dark-blonde to match the character's hair.
def eye_center(side):
    grp = mh.group_verts(f"helper-{side}-eye")
    return np.mean(mh.to_bl(V[grp]), axis=0)

exL = eye_center("l")
exR = eye_center("r")
eye_span = np.linalg.norm(np.array(exL) - np.array(exR))  # distance between eye centres, for scale


def build_brow(center, sign, span):
    """center: eye-centre (bl coords); sign: +1 for the +X (viewer-left in 3-quarter sense) brow,
    -1 for the other side. Builds a thin curved ribbon arching above the eye."""
    cx, cy, cz = center
    w = span * 0.62
    rise = span * 0.16
    n = 9
    bm = bmesh.new()
    top_row, bot_row = [], []
    for i in range(n):
        t = i / (n - 1)
        # arch profile: starts low near nose, peaks ~40% out, tapers toward temple
        x = cx + sign * (-w * 0.30 + t * w)
        arch = math.sin(t * math.pi) ** 0.7
        z = cz + span * 0.30 + rise * arch
        y = cy - 0.012 - 0.01 * math.sin(t * math.pi)
        thick = (0.10 + 0.55 * math.sin(min(max(t, 0.05), 0.95) * math.pi)) * span * 0.055
        top_row.append(bm.verts.new((x, y, z + thick * 0.5)))
        bot_row.append(bm.verts.new((x, y, z - thick * 0.5)))
    for i in range(n - 1):
        bm.faces.new((top_row[i], top_row[i + 1], bot_row[i + 1], bot_row[i]))
    bm.normal_update()
    me = bpy.data.meshes.new(f"Brow")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Brow", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


browL = build_brow(exL, 1, eye_span)
browR = build_brow(exR, -1, eye_span)
bm_mat, bnt, bout = new_material("Brow")
bb = N(bnt, 'ShaderNodeBsdfPrincipled', (0, 0))
L(bnt, bb.outputs[0], bout.inputs[0])
setin(bb, "Base Color", (0.17, 0.10, 0.045, 1))
setin(bb, "Roughness", 0.55)
for o in (browL, browR):
    o.data.materials.append(bm_mat)
    smooth_obj(o)

set_world((0.06, 0.06, 0.07), 1.0)
setup_cycles(SAMPLES, 800, 800)
head = mh.bl_vec(V, mh.group_verts("helper-l-eye")[0])
# find head center from eye helper verts and top
ex = exL
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
