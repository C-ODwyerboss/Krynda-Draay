"""Materials pass on the full cloth-sim result: velvet/satin robe shader, gold trim
(hem/cuffs/hood edge/neckline) conformed to the simulated cloth boundaries, pearl trim
along the neckline, and a waist sash with hanging tassels."""
from robe_common import *
import pickle
import bmesh

OUT = "/home/claude/work/out"
NAME = os.environ.get("NAME", "full_sim")
reset_scene()
d = np.load(f"{OUT}/{NAME}.npz", allow_pickle=True)
with open(f"{OUT}/{NAME}_topo.pkl", "rb") as fh:
    topo = pickle.load(fh)

V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)

bodice_faces_local = []
remap = {v: i for i, v in enumerate(topo["bodice_used"])}
for fc in topo["bodice_faces"]:
    bodice_faces_local.append([remap[v] for v in fc])
bodice = mh.mesh_from_arrays("Bodice", d["bodice"], bodice_faces_local)

skirt = mh.mesh_from_arrays("Skirt", d["skirt"], topo["skirt_faces"])
n = topo["sleeve_n"]
sl_faces = topo["sleeve_faces"]
sleeveL = mh.mesh_from_arrays("SleeveL", d["sleeveL"], sl_faces)
sleeveR = mh.mesh_from_arrays("SleeveR", d["sleeveR"], sl_faces)
hood = mh.mesh_from_arrays("Hood", d["hood"], topo["hood_faces"])

for o in (bodice, skirt, sleeveL, sleeveR):
    o.modifiers.new("Sub", 'SUBSURF').levels = 1

# ---------------------------------------------------------------- fabric shaders
def velvet_shader(name, base_color, rough=0.62, sheen=0.55, sheen_tint=(0.9, 0.85, 1.0, 1)):
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
    # broad weave/fold noise -> subtle bump + roughness variation, so it doesn't read as plastic
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
m3, nt3, out3 = new_material("bod")
b3 = N(nt3, 'ShaderNodeBsdfPrincipled')
L(nt3, b3.outputs[0], out3.inputs[0])
setin(b3, "Base Color", (0.62, 0.38, 0.30, 1))
setin(b3, "Roughness", 0.45)

for o in (bodice, skirt, sleeveL, sleeveR):
    o.data.materials.append(mat_robe)
hood.data.materials.append(mat_hood)
body.data.materials.append(m3)

# ---------------------------------------------------------------- trim geometry
def loop_curve(name, pts, bevel=0.006, closed=True, taper_pts=None):
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
    # convert curve -> mesh so it survives like the other sim-derived objects
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

sn = topo["sleeve_n"]
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

# pearls strung just below the gold neckline trim
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

# ---------------------------------------------------------------- sash + tassels
wp_row = 0   # the pinned waist loop -- a clean circle, unlike the flared rows just below it
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

# two tassels hanging from the front-centre of the sash (front = min Y)
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


for off in (-0.018, 0.018):
    p0 = waist_ring[front_idx].copy()
    p0[0] += off
    p0[2] -= 0.028
    t_ob = build_tassel(p0)
    mat_t, tnt, tout = new_material("TasselGold")
    tb = N(tnt, 'ShaderNodeBsdfPrincipled')
    L(tnt, tb.outputs[0], tout.inputs[0])
    setin(tb, "Base Color", (0.80, 0.60, 0.17, 1))
    setin(tb, "Metallic", 0.8)
    setin(tb, "Roughness", 0.35)
    t_ob.data.materials.append(mat_t)
    smooth_obj(t_ob)

make_floor()
set_world((0.12, 0.12, 0.14), 0.5)
setup_cycles(int(os.environ.get("SAMPLES", "24")), 480, 720, exposure=-0.5)
add_area("Key", (1.5, -3, 3), (0, 0, 1.1), 140, 2.5)
add_area("Fill", (-2.5, -2, 1.5), (0, 0, 1.1), 45, 3)
cams = {"front": add_camera("F", (0, -4.2, 1.1), (0, 0, 1.1), lens=50),
        "three": add_camera("T", (2.8, -3.4, 1.4), (0, 0, 1.1), lens=50),
        "back": add_camera("B", (0, 4.2, 1.1), (0, 0, 1.1), lens=50)}
from PIL import Image
ims = []
for v in os.environ.get("VIEWS", "front,three,back").split(","):
    render_to(f"{OUT}/{NAME}_mat_{v}.png", cams[v])
    ims.append(Image.open(f"{OUT}/{NAME}_mat_{v}.png"))
c2 = Image.new('RGB', (480 * len(ims), 720))
for i, im in enumerate(ims):
    c2.paste(im, (480 * i, 0))
c2.save(f"{OUT}/{NAME}_mat_sheet.png")
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/{NAME}_materials.blend")
print("DONE")
