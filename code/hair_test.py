"""Strand-based hair (Blender 4.x Curves/hair-curves object) grown from a scalp region of the
posed-neutral head, windswept + shoulder-length, blonde -- replaces the v3 hand-built tube
clumps with real hair strands and a Principled Hair BSDF."""
import sys, os, math, time, random
sys.path.insert(0, "/home/claude/work")
import numpy as np
import bpy
import mh
from common import *

OUT = os.environ.get("OUT", "/home/claude/work/out")
os.makedirs(OUT, exist_ok=True)
SAMPLES = int(os.environ.get("SAMPLES", "48"))
VIEWS = os.environ.get("VIEWS", "front,three").split(",")
N_STRANDS = int(os.environ.get("N_STRANDS", "450"))
random.seed(7)
np.random.seed(7)

reset_scene()

import shape
MACRO = shape.MACRO
DETAILS = shape.face_details()
V = mh.build_shape(macro=MACRO, details=DETAILS)

body = mh.make_mesh("Body", V)
sub = body.modifiers.new("Sub", 'SUBSURF')
sub.levels = 1
sub.render_levels = 2

# --- skin (same as head_test.py)
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
n1 = N(nt, 'ShaderNodeTexNoise', (-900, -100))
n1.inputs['Scale'].default_value = 28.0
n1.inputs['Detail'].default_value = 4.0
n1.inputs['Roughness'].default_value = 0.6
L(nt, tc.outputs['Object'], n1.inputs['Vector'])
bump1 = N(nt, 'ShaderNodeBump', (-650, -100))
bump1.inputs['Strength'].default_value = 0.12
bump1.inputs['Distance'].default_value = 0.0025
L(nt, n1.outputs['Fac'], bump1.inputs['Height'])
n2 = N(nt, 'ShaderNodeTexNoise', (-900, -350))
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
cr = N(nt, 'ShaderNodeValToRGB', (-650, 150))
cr.color_ramp.elements[0].position = 0.35
cr.color_ramp.elements[0].color = (0.36, 0.36, 0.36, 1)
cr.color_ramp.elements[1].position = 0.65
cr.color_ramp.elements[1].color = (0.50, 0.50, 0.50, 1)
L(nt, n1.outputs['Fac'], cr.inputs['Fac'])
L(nt, cr.outputs['Color'], b.inputs['Roughness'])
body.data.materials.append(m)

# --- eyes
eyeclo = mh.load_mhclo(os.path.join(mh.MH, "eyes/high-poly/high-poly.mhclo"))
EV, EF, EVT, EFT = mh.load_obj_simple(os.path.join(mh.MH, "eyes/high-poly/high-poly.obj"))
P = mh.fit_proxy(eyeclo, V)
eye = mh.mesh_from_arrays("Eyes", mh.to_bl(P), EF, EVT, EFT)
em, ent, eout = new_material("Eye")
eb = N(ent, 'ShaderNodeBsdfPrincipled', (0, 0))
L(ent, eb.outputs[0], eout.inputs[0])
setin(eb, "Base Color", (0.30, 0.47, 0.55, 1))
setin(eb, "Roughness", 0.08)
eye.data.materials.append(em)


def eye_center(side):
    grp = mh.group_verts(f"helper-{side}-eye")
    return np.mean(mh.to_bl(V[grp]), axis=0)


exL = eye_center("l")
exR = eye_center("r")
eye_span = np.linalg.norm(np.array(exL) - np.array(exR))


def build_brow(center, sign, span):
    cx, cy, cz = center
    w = span * 0.62
    rise = span * 0.16
    n = 9
    import bmesh
    bm = bmesh.new()
    top_row, bot_row = [], []
    for i in range(n):
        t = i / (n - 1)
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
    me = bpy.data.meshes.new("Brow")
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
setin(bb, "Base Color", (0.42, 0.28, 0.12, 1))  # dark-blonde brows to match the hair
setin(bb, "Roughness", 0.55)
for o in (browL, browR):
    o.data.materials.append(bm_mat)
    smooth_obj(o)

# ------------------------------------------------------------------ hair
NB = 13380
Vbl = mh.to_bl(V[:NB])
normals_dir = Vbl - np.array([0.0, Vbl[:, 1].mean() * 0.15, exL[2] - 0.01])
nlen = np.linalg.norm(normals_dir, axis=1, keepdims=True)
nlen[nlen < 1e-6] = 1
normals_dir /= nlen

top_z = Vbl[:, 2].max()
scalp_mask = (Vbl[:, 2] > exL[2] - 0.05) & (normals_dir[:, 1] > -0.45)
scalp_idx = np.where(scalp_mask)[0]
print("scalp verts", len(scalp_idx))
scalp_pts = Vbl[scalp_idx]
scalp_norm = normals_dir[scalp_idx]
head_c = np.array([0.0, scalp_pts[:, 1].mean(), exL[2] + 0.07])

hc = bpy.data.hair_curves.new("Hair")
POINTS_PER = 18
# weight sampling so the crown/part region isn't over/under represented vs a uniform pick
pick = np.random.choice(len(scalp_idx), size=N_STRANDS, replace=True)
sizes = [POINTS_PER] * N_STRANDS
hc.add_curves(sizes)
hc.attributes.new('radius', 'FLOAT', 'POINT')

all_pos = np.zeros((N_STRANDS * POINTS_PER, 3), dtype=np.float32)
all_rad = np.zeros(N_STRANDS * POINTS_PER, dtype=np.float32)

# wind/flow direction for the windswept look: mostly back-and-to-one-side, varying by height
flow = np.array([0.55, 0.35, -0.15])
flow /= np.linalg.norm(flow)
side = np.array([1.0, 0.0, 0.0])

for si in range(N_STRANDS):
    idx = pick[si]
    root = scalp_pts[idx].copy()
    nrm = scalp_norm[idx].copy()
    # jitter the root slightly within the local tangent plane so strands rooted at nearby mesh
    # verts don't all stack into visible "comb teeth" -- breaks up the clumping
    tang = np.cross(nrm, np.array([0.0, 0.0, 1.0]))
    if np.linalg.norm(tang) < 1e-6:
        tang = np.array([1.0, 0.0, 0.0])
    tang /= np.linalg.norm(tang)
    bitang = np.cross(nrm, tang)
    root = root + tang * np.random.uniform(-0.008, 0.008) + bitang * np.random.uniform(-0.008, 0.008)
    # part line: strands very close to the centre top get pushed slightly left/right so hair
    # doesn't spike straight up along the crown seam
    local_x = root[0] - head_c[0]
    part_bias = 0.012 * (1 if local_x >= 0 else -1) * max(0.0, 1.0 - abs(local_x) / 0.03)

    length = 0.46 + random.uniform(-0.05, 0.14)  # past-shoulder length, varied
    jitter = np.random.normal(0, 1, 3)
    curl_amp = 0.028 + 0.022 * random.random()
    curl_freq = 1.5 + random.random() * 1.1
    phase = random.random() * math.tau
    rad0 = 0.0011 + random.uniform(-0.0002, 0.0003)

    pts = []
    for k in range(POINTS_PER):
        t = k / (POINTS_PER - 1)
        # small, quickly-decaying outward bulge at the root (keeps strands hugging the scalp
        # instead of spiking straight out), eased smoothly into the flow direction
        ease = t * t * t * (t * (t * 6 - 15) + 10)  # smootherstep: 0 at root, 1 by the tip
        out_amt = 0.014 * (1 - min(t / 0.12, 1.0))
        fall = length * t
        p = root + nrm * out_amt
        p = p + flow * fall * (0.35 + 0.65 * ease)
        p[0] += part_bias * (1 - t)
        # gravity pulls strands down as they lengthen
        p[2] -= 0.5 * fall ** 1.5
        # windswept wave, strongest mid-strand, tapering at the very root and tip
        wave_env = math.sin(min(t, 1.0) * math.pi) * ease
        p += side * curl_amp * wave_env * math.sin(t * curl_freq * math.tau + phase)
        p += np.array([0, 1, 0]) * 0.35 * curl_amp * wave_env * math.cos(t * curl_freq * math.tau * 0.7 + phase)
        p += jitter * 0.003 * t
        pts.append(p)
    pts = np.array(pts, dtype=np.float32)
    all_pos[si * POINTS_PER:(si + 1) * POINTS_PER] = pts
    all_rad[si * POINTS_PER:(si + 1) * POINTS_PER] = np.linspace(rad0, rad0 * 0.12, POINTS_PER)

hc.points.foreach_set('position', all_pos.ravel())
hc.attributes['radius'].data.foreach_set('value', all_rad)

hair_ob = bpy.data.objects.new("HairCurves", hc)
bpy.context.scene.collection.objects.link(hair_ob)

hmat, hnt, hout = new_material("Hair")
hb = N(hnt, 'ShaderNodeBsdfHairPrincipled', (0, 0))
L(hnt, hb.outputs[0], hout.inputs[0])
hb.parametrization = 'COLOR'
setin(hb, "Color", (0.52, 0.32, 0.09, 1))  # warm golden blonde (darkened to survive transmission)
setin(hb, "Roughness", 0.3)
setin(hb, "Radial Roughness", 0.4)
setin(hb, "Random Roughness", 0.2)
setin(hb, "Random Color", 0.12)
setin(hb, "IOR", 1.55)
hc.materials.append(hmat)

set_world((0.05, 0.05, 0.06), 0.7)
setup_cycles(SAMPLES, 800, 800, exposure=-0.2)
ex = exL
hc_cam = Vector((0.0, ex[1], ex[2] + 0.08))
add_area("Key", (0.7, -1.4, 1.95), hc_cam, 55, 1.2, (1.0, 0.95, 0.9))
add_area("Fill", (-1.0, -1.2, 1.7), hc_cam, 20, 1.5, (0.9, 0.93, 1.0))
add_area("Rim", (-0.3, 1.2, 2.0), hc_cam, 50, 1.0, (1, 1, 1))

cams = {}
cams["front"] = add_camera("CamF", (0.0, hc_cam.y - 1.3, hc_cam.z - 0.1), hc_cam, lens=85, fstop=8)
cams["three"] = add_camera("CamT", (0.6, hc_cam.y - 1.15, hc_cam.z - 0.05), hc_cam, lens=85, fstop=8)
t = time.time()
for v in VIEWS:
    render_to(os.path.join(OUT, f"hair_{v}.png"), cams[v])
    print(v, time.time() - t)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "hair_test.blend"))
