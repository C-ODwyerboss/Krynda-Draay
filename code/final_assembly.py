"""Final assembly: the dressed, cloth-simulated body (materials_full.py's output) + the
sharpened head/face/eyes/brows + the windswept blonde hair, all in one scene and one render.

The garment is loaded from the already-simulated full_sim.npz (no re-sim needed -- materials
pass only, as in materials_full.py). The head assets (eyes, brow ribbons, hair strands) are
built in the SAME rest-pose space head_test.py/hair_test.py use, then rigidly carried onto the
posed body by the "head" bone's own world transform (rig.M["head"], available after
posed_body_points() calls rig.pose()) plus the same Z_OFF used to put the body's feet at
z=0 -- i.e. "attach the finished head to the body's head bone" rather than re-deriving a posed
head from scratch."""
import sys, os, math, time, random, pickle
sys.path.insert(0, "/home/claude/work")
import numpy as np
import bpy
import bmesh
from robe_common import *
import shape

OUT = "/home/claude/work/out"
SAMPLES = int(os.environ.get("SAMPLES", "32"))
VIEWS = os.environ.get("VIEWS", "front,three,back").split(",")
N_STRANDS = int(os.environ.get("N_STRANDS", "600"))
random.seed(7)
np.random.seed(7)

reset_scene()

# ------------------------------------------------------------------ posed body + garment
V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
Z_OFF = garment.Z_OFF
M_head = np.array(rig.M["head"])
Mw = Matrix.Translation((0, 0, Z_OFF)) @ Matrix(M_head.tolist())

body = mh.make_mesh("Body", Pp, bl=True)
sub = body.modifiers.new("Sub", 'SUBSURF')
sub.levels = 1
sub.render_levels = 2

# --- skin: layered bump shader (same recipe as head_test.py/hair_test.py)
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

# --- garment: load the saved sim result and apply the velvet/gold/pearl materials pass
NAME = "full_sim"
d = np.load(f"{OUT}/{NAME}.npz", allow_pickle=True)
with open(f"{OUT}/{NAME}_topo.pkl", "rb") as fh:
    topo = pickle.load(fh)

bodice_faces_local = []
remap = {v: i for i, v in enumerate(topo["bodice_used"])}
for fc in topo["bodice_faces"]:
    bodice_faces_local.append([remap[v] for v in fc])
bodice = mh.mesh_from_arrays("Bodice", d["bodice"], bodice_faces_local)
skirt = mh.mesh_from_arrays("Skirt", d["skirt"], topo["skirt_faces"])
sn = topo["sleeve_n"]
sl_faces = topo["sleeve_faces"]
sleeveL = mh.mesh_from_arrays("SleeveL", d["sleeveL"], sl_faces)
sleeveR = mh.mesh_from_arrays("SleeveR", d["sleeveR"], sl_faces)
hood = mh.mesh_from_arrays("Hood", d["hood"], topo["hood_faces"])
for o in (bodice, skirt, sleeveL, sleeveR):
    o.modifiers.new("Sub", 'SUBSURF').levels = 1


def velvet_shader(name, base_color, rough=0.6, sheen=0.3, sheen_tint=(0.9, 0.85, 1.0, 1)):
    m, nt, out = new_material(name)
    b = N(nt, 'ShaderNodeBsdfPrincipled', (0, 0))
    L(nt, b.outputs[0], out.inputs[0])
    setin(b, "Base Color", base_color)
    setin(b, "Roughness", rough)
    setin(b, "Specular IOR Level", 0.3)
    if "Sheen Weight" in b.inputs:
        setin(b, "Sheen Weight", sheen)
        setin(b, "Sheen Roughness", 0.3)
        setin(b, "Sheen Tint", sheen_tint)
    tc = N(nt, 'ShaderNodeTexCoord', (-900, -200))
    nz = N(nt, 'ShaderNodeTexNoise', (-650, -200))
    nz.inputs['Scale'].default_value = 60.0
    nz.inputs['Detail'].default_value = 5.0
    nz.inputs['Roughness'].default_value = 0.65
    L(nt, tc.outputs['Object'], nz.inputs['Vector'])
    bump = N(nt, 'ShaderNodeBump', (-400, -200))
    bump.inputs['Strength'].default_value = 0.08
    bump.inputs['Distance'].default_value = 0.004
    L(nt, nz.outputs['Fac'], bump.inputs['Height'])
    L(nt, bump.outputs['Normal'], b.inputs['Normal'])
    cr = N(nt, 'ShaderNodeValToRGB', (-400, 50))
    cr.color_ramp.elements[0].position = 0.4
    cr.color_ramp.elements[0].color = (rough * 0.82,) * 3 + (1,)
    cr.color_ramp.elements[1].position = 0.6
    cr.color_ramp.elements[1].color = (min(rough * 1.15, 1.0),) * 3 + (1,)
    L(nt, nz.outputs['Fac'], cr.inputs['Fac'])
    L(nt, cr.outputs['Color'], b.inputs['Roughness'])
    return m


def gold_shader(name="Gold"):
    m, nt, out = new_material(name)
    b = N(nt, 'ShaderNodeBsdfPrincipled', (0, 0))
    L(nt, b.outputs[0], out.inputs[0])
    setin(b, "Base Color", (0.83, 0.62, 0.18, 1))
    setin(b, "Metallic", 1.0)
    setin(b, "Roughness", 0.28)
    tc = N(nt, 'ShaderNodeTexCoord', (-600, -200))
    nz = N(nt, 'ShaderNodeTexNoise', (-400, -200))
    nz.inputs['Scale'].default_value = 120.0
    nz.inputs['Detail'].default_value = 3.0
    bump = N(nt, 'ShaderNodeBump', (-180, -200))
    bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.0015
    L(nt, tc.outputs['Object'], nz.inputs['Vector'])
    L(nt, nz.outputs['Fac'], bump.inputs['Height'])
    L(nt, bump.outputs['Normal'], b.inputs['Normal'])
    return m


def pearl_shader(name="Pearl"):
    m, nt, out = new_material(name)
    b = N(nt, 'ShaderNodeBsdfPrincipled', (0, 0))
    L(nt, b.outputs[0], out.inputs[0])
    setin(b, "Base Color", (0.95, 0.93, 0.88, 1))
    setin(b, "Roughness", 0.22)
    setin(b, "Subsurface Weight", 0.6)
    setin(b, "Subsurface Radius", (0.3, 0.3, 0.25))
    setin(b, "Subsurface Scale", 0.01)
    return m


mat_robe = velvet_shader("RobeVelvet", (0.20, 0.045, 0.34, 1), rough=0.6, sheen=0.3)
mat_hood = velvet_shader("HoodVelvet", (0.13, 0.03, 0.24, 1), rough=0.62, sheen=0.25)
mat_gold = gold_shader()
mat_pearl = pearl_shader()
for o in (bodice, skirt, sleeveL, sleeveR):
    o.data.materials.append(mat_robe)
hood.data.materials.append(mat_hood)


def loop_curve(name, pts, bevel=0.006, closed=True):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = bevel
    cu.bevel_resolution = 3
    cu.resolution_u = 2
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def trim_mesh(ob, material):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    mo = bpy.data.objects.new(ob.name + "_mesh", me)
    bpy.context.scene.collection.objects.link(mo)
    mo.data.materials.append(material)
    smooth_obj(mo)
    bpy.data.objects.remove(ob, do_unlink=True)
    return mo


len_wp = topo["skirt_faces"][0][3]
rows_sk = d["skirt"].shape[0] // len_wp - 1
hem = d["skirt"][rows_sk * len_wp:(rows_sk + 1) * len_wp]
trim_mesh(loop_curve("HemTrim", hem, bevel=0.007), mat_gold)
rows_sl = d["sleeveL"].shape[0] // sn - 1
for side, arr in (("L", d["sleeveL"]), ("R", d["sleeveR"])):
    cuff = arr[rows_sl * sn:(rows_sl + 1) * sn]
    trim_mesh(loop_curve(f"Cuff{side}Trim", cuff, bevel=0.0055), mat_gold)
hn = topo["hood_n"]
rows_hd = d["hood"].shape[0] // hn - 1
hood_edge = d["hood"][rows_hd * hn:(rows_hd + 1) * hn]
trim_mesh(loop_curve("HoodEdgeTrim", hood_edge, bevel=0.006, closed=False), mat_gold)
neckline = d["hood"][0:hn]
trim_mesh(loop_curve("NecklineTrim", neckline, bevel=0.005, closed=False), mat_gold)

bm = bmesh.new()
step = max(1, len(neckline) // 22)
for p in neckline[::step]:
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.009,
                                matrix=Matrix.Translation(Vector((p[0], p[1], p[2] - 0.012))))
me = bpy.data.meshes.new("Pearls")
bm.to_mesh(me)
bm.free()
pearls = bpy.data.objects.new("Pearls", me)
bpy.context.scene.collection.objects.link(pearls)
pearls.data.materials.append(mat_pearl)
smooth_obj(pearls)

wp_row = 0
waist_ring = d["skirt"][wp_row * len_wp:(wp_row + 1) * len_wp]
c = waist_ring.mean(axis=0)


def build_sash(ring, centre, out_amt=0.012, half_h=0.028):
    n = len(ring)
    bm = bmesh.new()
    top, bot = [], []
    for i in range(n):
        p = Vector(ring[i])
        rad = (p - Vector(centre))
        rad.z = 0
        if rad.length > 1e-6:
            rad = rad.normalized()
        pp = p + Vector((rad.x, rad.y, 0)) * out_amt
        top.append(bm.verts.new((pp.x, pp.y, pp.z + half_h)))
        bot.append(bm.verts.new((pp.x, pp.y, pp.z - half_h)))
    bm.verts.ensure_lookup_table()
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top[i], top[j], bot[j], bot[i]))
    me = bpy.data.meshes.new("Sash")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Sash", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


sash = build_sash(waist_ring, c)
mat_sash, snt, sout = new_material("Sash")
sb = N(snt, 'ShaderNodeBsdfPrincipled')
L(snt, sb.outputs[0], sout.inputs[0])
setin(sb, "Base Color", (0.12, 0.03, 0.22, 1))
setin(sb, "Roughness", 0.5)
if "Sheen Weight" in sb.inputs:
    setin(sb, "Sheen Weight", 0.5)
sash.data.materials.append(mat_sash)
smooth_obj(sash)

front_idx = int(np.argmin(waist_ring[:, 1]))


def build_tassel(origin, length=0.14, segs=6, r0=0.009, r1=0.002):
    bm = bmesh.new()
    rings = []
    for k in range(segs + 1):
        t = k / segs
        z = origin[2] - length * t
        r = r0 * (1 - t) + r1 * t
        ring = []
        for a in range(8):
            ang = a / 8 * 2 * math.pi
            ring.append(bm.verts.new((origin[0] + r * math.cos(ang), origin[1] + r * math.sin(ang), z)))
        rings.append(ring)
    for k in range(segs):
        for a in range(8):
            a2 = (a + 1) % 8
            bm.faces.new((rings[k][a], rings[k][a2], rings[k + 1][a2], rings[k + 1][a]))
    me = bpy.data.meshes.new("Tassel")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Tassel", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


mat_t, tnt, tout = new_material("TasselGold")
tb = N(tnt, 'ShaderNodeBsdfPrincipled')
L(tnt, tb.outputs[0], tout.inputs[0])
setin(tb, "Base Color", (0.80, 0.60, 0.17, 1))
setin(tb, "Metallic", 0.8)
setin(tb, "Roughness", 0.35)
for off in (-0.018, 0.018):
    p0 = waist_ring[front_idx].copy()
    p0[0] += off
    p0[2] -= 0.028
    t_ob = build_tassel(p0)
    t_ob.data.materials.append(mat_t)
    smooth_obj(t_ob)

# (bodice is the torso/shoulder-covering cloth piece and IS rendered, same as in
# materials_full.py -- it must stay visible here, unlike in full_sim.py where that flag is a
# harmless leftover from the sim pass, which never renders at all)

# ------------------------------------------------------------------ head: eyes, brows, hair
# all built in the SAME rest-pose Blender space head_test.py/hair_test.py use, then carried
# onto the posed body by the head bone's own transform (Mw) set up above.
eyeclo = mh.load_mhclo(os.path.join(mh.MH, "eyes/high-poly/high-poly.mhclo"))
EV, EF, EVT, EFT = mh.load_obj_simple(os.path.join(mh.MH, "eyes/high-poly/high-poly.obj"))
Peye = mh.fit_proxy(eyeclo, V)
eye = mh.mesh_from_arrays("Eyes", mh.to_bl(Peye), EF, EVT, EFT)
eye.matrix_world = Mw
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
browL.matrix_world = Mw
browR.matrix_world = Mw
bm_mat, bnt, bout = new_material("Brow")
bb = N(bnt, 'ShaderNodeBsdfPrincipled', (0, 0))
L(bnt, bb.outputs[0], bout.inputs[0])
setin(bb, "Base Color", (0.42, 0.28, 0.12, 1))
setin(bb, "Roughness", 0.55)
for o in (browL, browR):
    o.data.materials.append(bm_mat)
    smooth_obj(o)

# --- hair
NB = garment.NB
Vbl = mh.to_bl(V[:NB])
normals_dir = Vbl - np.array([0.0, Vbl[:, 1].mean() * 0.15, exL[2] - 0.01])
nlen = np.linalg.norm(normals_dir, axis=1, keepdims=True)
nlen[nlen < 1e-6] = 1
normals_dir /= nlen
scalp_mask = (Vbl[:, 2] > exL[2] - 0.05) & (normals_dir[:, 1] > -0.45)
scalp_idx = np.where(scalp_mask)[0]
scalp_pts = Vbl[scalp_idx]
scalp_norm = normals_dir[scalp_idx]
head_c = np.array([0.0, scalp_pts[:, 1].mean(), exL[2] + 0.07])

hc = bpy.data.hair_curves.new("Hair")
POINTS_PER = 18
pick = np.random.choice(len(scalp_idx), size=N_STRANDS, replace=True)
hc.add_curves([POINTS_PER] * N_STRANDS)
hc.attributes.new('radius', 'FLOAT', 'POINT')
all_pos = np.zeros((N_STRANDS * POINTS_PER, 3), dtype=np.float32)
all_rad = np.zeros(N_STRANDS * POINTS_PER, dtype=np.float32)
flow = np.array([0.55, 0.35, -0.15])
flow /= np.linalg.norm(flow)
side = np.array([1.0, 0.0, 0.0])

for si in range(N_STRANDS):
    idx = pick[si]
    root = scalp_pts[idx].copy()
    nrm = scalp_norm[idx].copy()
    tang = np.cross(nrm, np.array([0.0, 0.0, 1.0]))
    if np.linalg.norm(tang) < 1e-6:
        tang = np.array([1.0, 0.0, 0.0])
    tang /= np.linalg.norm(tang)
    bitang = np.cross(nrm, tang)
    root = root + tang * np.random.uniform(-0.008, 0.008) + bitang * np.random.uniform(-0.008, 0.008)
    local_x = root[0] - head_c[0]
    part_bias = 0.012 * (1 if local_x >= 0 else -1) * max(0.0, 1.0 - abs(local_x) / 0.03)
    length = 0.46 + random.uniform(-0.05, 0.14)
    jitter = np.random.normal(0, 1, 3)
    curl_amp = 0.028 + 0.022 * random.random()
    curl_freq = 1.5 + random.random() * 1.1
    phase = random.random() * math.tau
    rad0 = 0.0011 + random.uniform(-0.0002, 0.0003)
    pts = []
    for k in range(POINTS_PER):
        t = k / (POINTS_PER - 1)
        ease = t * t * t * (t * (t * 6 - 15) + 10)
        out_amt = 0.014 * (1 - min(t / 0.12, 1.0))
        fall = length * t
        p = root + nrm * out_amt
        p = p + flow * fall * (0.35 + 0.65 * ease)
        p[0] += part_bias * (1 - t)
        p[2] -= 0.5 * fall ** 1.5
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
hair_ob.matrix_world = Mw

hmat, hnt, hout = new_material("Hair")
hb = N(hnt, 'ShaderNodeBsdfHairPrincipled', (0, 0))
L(hnt, hb.outputs[0], hout.inputs[0])
hb.parametrization = 'COLOR'
setin(hb, "Color", (0.40, 0.19, 0.035, 1))  # darker/more saturated amber-gold -- the thin,
# densely-overlapping strands scatter a lot of light and read much paler than this base color
setin(hb, "Roughness", 0.3)
setin(hb, "Radial Roughness", 0.4)
setin(hb, "Random Roughness", 0.2)
setin(hb, "Random Color", 0.1)
setin(hb, "IOR", 1.55)
if "Transmission" in hb.inputs:
    setin(hb, "Transmission", 0.55)  # less backlit glow-through, less washed-out overall
hc.materials.append(hmat)

# ------------------------------------------------------------------ lighting + cameras
make_floor()
set_world((0.12, 0.12, 0.14), 0.5)
setup_cycles(SAMPLES, 640, 960, exposure=-0.45)
add_area("Key", (1.5, -3, 3), (0, 0, 1.1), 150, 2.5)
add_area("Fill", (-2.5, -2, 1.5), (0, 0, 1.1), 50, 3)
add_area("Rim", (0, 3, 2.6), (0, 0, 1.4), 35, 2.0)  # halved -- was blowing the hair out white
cams = {"front": add_camera("F", (0, -4.2, 1.1), (0, 0, 1.1), lens=50),
        "three": add_camera("T", (2.8, -3.4, 1.4), (0, 0, 1.1), lens=50),
        "back": add_camera("B", (0, 4.2, 1.1), (0, 0, 1.1), lens=50)}

from PIL import Image
ims = []
for v in VIEWS:
    render_to(f"{OUT}/final_{v}.png", cams[v])
    ims.append(Image.open(f"{OUT}/final_{v}.png"))
c2 = Image.new('RGB', (640 * len(ims), 960))
for i, im in enumerate(ims):
    c2.paste(im, (640 * i, 0))
c2.save(f"{OUT}/final_sheet.png")
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/final_assembly.blend")
print("DONE")
