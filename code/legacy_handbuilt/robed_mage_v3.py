"""
Robed mage v3 - more realistic build.
Run inside Blender (Scripting tab > Open > Run Script, Blender 4.x/5.x)
or headless:
    MAGE_RENDER=/path/full.png MAGE_FACE=/path/face.png MAGE_BLEND=/path/mage.blend python robed_mage_v3.py
Uses only the data API, so it also works with the `bpy` pip module.
Viewport: switch to Material Preview / Rendered to see skin, hair and cloth.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix, Euler, noise

PI = math.pi
random.seed(5)

# ------------------------------------------------------------------ clean scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
            bpy.data.lights, bpy.data.cameras):
    for b in list(blk):
        blk.remove(b)

scene = bpy.context.scene
coll = scene.collection


# ------------------------------------------------------------------ maths helpers
def sstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def gauss(dx, dz, sx, sz):
    return math.exp(-((dx / sx) ** 2 + (dz / sz) ** 2))


def tbl(t, x):
    """Cubic Hermite interpolation through (x, y) knots."""
    n = len(t)
    if x <= t[0][0]:
        return t[0][1]
    if x >= t[-1][0]:
        return t[-1][1]
    for i in range(n - 1):
        x0, y0 = t[i]
        x1, y1 = t[i + 1]
        if x0 <= x <= x1:
            def slope(k):
                a, b = max(k - 1, 0), min(k + 1, n - 1)
                return (t[b][1] - t[a][1]) / (t[b][0] - t[a][0])
            h = x1 - x0
            s = (x - x0) / h
            m0, m1 = slope(i) * h, slope(i + 1) * h
            return ((2 * s ** 3 - 3 * s ** 2 + 1) * y0 + (s ** 3 - 2 * s ** 2 + s) * m0 +
                    (-2 * s ** 3 + 3 * s ** 2) * y1 + (s ** 3 - s ** 2) * m1)
    return t[-1][1]


def mixc(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


# ------------------------------------------------------------------ materials
def set_in(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val


def mat(name, color, metallic=0.0, rough=0.5, sheen=0.0, sss=0.0, coat=0.0,
        bump=None, vcol=None, aniso=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None:
        b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    set_in(b, "Base Color", (*color[:3], 1))
    set_in(b, "Metallic", metallic)
    set_in(b, "Roughness", rough)
    if sheen:
        set_in(b, "Sheen Weight", sheen)
        set_in(b, "Sheen Roughness", 0.35)
        set_in(b, "Sheen Tint", (min(1, color[0] * 2.5 + .1), min(1, color[1] * 2.5 + .1),
                                min(1, color[2] * 2.5 + .1), 1))
    if sss:
        set_in(b, "Subsurface Weight", sss)
        set_in(b, "Subsurface Radius", (1.0, 0.35, 0.22))
        set_in(b, "Subsurface Scale", 0.012)
    if coat:
        set_in(b, "Coat Weight", coat)
        set_in(b, "Coat Roughness", 0.05)
    if aniso:
        set_in(b, "Anisotropic", aniso)
    if bump:
        scale, strength = bump
        tc = nt.nodes.new('ShaderNodeTexCoord')
        nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = scale
        nz.inputs['Detail'].default_value = 8
        bp = nt.nodes.new('ShaderNodeBump')
        bp.inputs['Strength'].default_value = strength
        bp.inputs['Distance'].default_value = 0.01
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
        nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    if vcol:
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_name = vcol
        nt.links.new(at.outputs['Color'], b.inputs['Base Color'])
    m.diffuse_color = (*color[:3], 1)
    return m


# cloth / metal / skin / hair
PURPLE = mat("RobePurple", (0.075, 0.018, 0.19), rough=0.75, sheen=0.9, bump=(900, 0.12))
DEEP = mat("RobeDeep", (0.04, 0.01, 0.10), rough=0.75, sheen=0.6, bump=(900, 0.1))
PEARL = mat("Pearl", (0.52, 0.45, 0.82), rough=0.22, coat=0.6, sheen=0.3)
GOLD = mat("Gold", (1.0, 0.70, 0.17), metallic=1.0, rough=0.24, bump=(500, 0.06))
MAGENTA = mat("Magenta", (0.40, 0.04, 0.28), rough=0.6, sheen=0.8, bump=(900, 0.1))
SKIN = mat("Skin", (0.70, 0.40, 0.31), rough=0.5, sss=0.35, bump=(1800, 0.04))
FACE = mat("Face", (0.70, 0.40, 0.31), rough=0.48, sss=0.35, bump=(1800, 0.03), vcol="Col")
SCLERA = mat("Sclera", (0.82, 0.78, 0.76), rough=0.25, coat=1.0)


def make_eye_material(R):
    m = mat("Eye", (0.82, 0.78, 0.76), rough=0.2, coat=1.0)
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    comb = nt.nodes.new('ShaderNodeCombineXYZ')
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    dv = nt.nodes.new('ShaderNodeMath')
    dv.operation = 'DIVIDE'
    dv.inputs[1].default_value = R
    gt = nt.nodes.new('ShaderNodeMath')
    gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = 0.0
    mx = nt.nodes.new('ShaderNodeMath')
    mx.operation = 'MAXIMUM'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    L = nt.links.new
    L(tc.outputs['Object'], sep.inputs['Vector'])
    L(sep.outputs['X'], comb.inputs['X'])
    L(sep.outputs['Z'], comb.inputs['Z'])
    L(comb.outputs['Vector'], ln.inputs[0])
    L(ln.outputs['Value'], dv.inputs[0])
    L(sep.outputs['Y'], gt.inputs[0])
    L(dv.outputs['Value'], mx.inputs[0])
    L(gt.outputs['Value'], mx.inputs[1])
    L(mx.outputs['Value'], ramp.inputs['Fac'])
    L(ramp.outputs['Color'], b.inputs['Base Color'])
    stops = [(0.0, (0, 0, 0)), (0.17, (0, 0, 0)), (0.20, (0.30, 0.42, 0.50)), (0.33, (0.17, 0.33, 0.52)),
             (0.44, (0.05, 0.12, 0.30)), (0.47, (0.012, 0.025, 0.06)), (0.495, (0.82, 0.78, 0.76)),
             (1.0, (0.82, 0.78, 0.76))]
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = stops[0][0], (*stops[0][1], 1)
    el[1].position, el[1].color = stops[1][0], (*stops[1][1], 1)
    for p, c in stops[2:]:
        e = el.new(p)
        e.color = (*c, 1)
    return m



LIMBAL = mat("Limbal", (0.02, 0.05, 0.13), rough=0.2, coat=1.0)
IRIS1 = mat("Iris1", (0.07, 0.20, 0.45), rough=0.2, coat=1.0)
IRIS2 = mat("Iris2", (0.22, 0.42, 0.62), rough=0.2, coat=1.0)
PUPIL = mat("Pupil", (0.0, 0.0, 0.0), rough=0.15, coat=1.0)
LASH = mat("Lash", (0.10, 0.06, 0.03), rough=0.4)
BLONDE_A = mat("BlondeA", (0.80, 0.55, 0.16), rough=0.30, aniso=0.4, sheen=0.3)
BLONDE_B = mat("BlondeB", (0.92, 0.70, 0.27), rough=0.28, aniso=0.4, sheen=0.3)
BLONDE_C = mat("BlondeC", (0.68, 0.44, 0.11), rough=0.32, aniso=0.4, sheen=0.3)
CAPMAT = mat("HairCap", (0.78, 0.53, 0.15), rough=0.35, sheen=0.4, bump=(60, 0.5))


# ------------------------------------------------------------------ object helpers
def link_obj(name, data, material=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), parent=None):
    o = bpy.data.objects.new(name, data)
    o.location, o.rotation_euler, o.scale = loc, rot, scale
    if material is not None and data is not None and hasattr(data, "materials"):
        data.materials.append(material)
    coll.objects.link(o)
    if parent is not None:
        o.parent = parent
    return o


def finish_mesh(name, bm, material, smooth=True, **kw):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link_obj(name, me, material, **kw)


def sphere(name, material, loc, scale, rot=(0, 0, 0), seg=32, rings=16, parent=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    return finish_mesh(name, bm, material, loc=loc, rot=rot, scale=scale, parent=parent)


def cone_between(name, material, p0, p1, r0, r1, seg=32, caps=False, parent=None):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg,
                          radius1=r0, radius2=r1, depth=d.length)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return finish_mesh(name, bm, material, loc=(p0 + p1) / 2, rot=rot, parent=parent)


def torus(name, material, loc, R, r, scale=(1, 1, 1), rot=(0, 0, 0), nu=64, nv=14):
    bm = bmesh.new()
    vs = []
    for i in range(nu):
        u = 2 * PI * i / nu
        vs.append([bm.verts.new(((R + r * math.cos(2 * PI * j / nv)) * math.cos(u),
                                 (R + r * math.cos(2 * PI * j / nv)) * math.sin(u),
                                 r * math.sin(2 * PI * j / nv))) for j in range(nv)])
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((vs[i][j], vs[(i + 1) % nu][j], vs[(i + 1) % nu][(j + 1) % nv], vs[i][(j + 1) % nv]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish_mesh(name, bm, material, loc=loc, rot=rot, scale=scale)


def tube(name, material, pts, radii, res=5, parent=None):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 12
    cu.bevel_depth = 1.0
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new('NURBS')
    sp.points.add(len(pts) - 1)
    for p, (x, y, z), r in zip(sp.points, pts, radii):
        p.co = (x, y, z, 1.0)
        p.radius = r
    sp.order_u = min(4, len(pts))
    sp.use_endpoint_u = True
    return link_obj(name, cu, material, parent=parent)


def displace_noise(bm, amp, scale, seed=0.0):
    bm.normal_update()
    for v in bm.verts:
        n = noise.noise(v.co * scale + Vector((seed, seed * 2, seed * 3)))
        v.co += v.normal * amp * n


# ------------------------------------------------------------------ the robe
H = 1.85
PROF = [(0.0, 0.88), (0.12, 0.76), (0.30, 0.60), (0.55, 0.42), (0.80, 0.30), (1.05, 0.235),
        (1.30, 0.175), (1.50, 0.185), (1.68, 0.215), (1.80, 0.195), (1.85, 0.17)]


def robe_pt(theta, t, off=0.0):
    """Point on the robe; theta = -pi/2 is the front (-Y). t in 0..1 from hem to shoulder."""
    z0 = H * t
    k = 1.0 - t
    r = tbl(PROF, z0)
    amp = 0.062 * (1.0 - sstep(0.0, 1.35, z0)) ** 1.1
    n = noise.noise(Vector((math.cos(theta) * 1.6, math.sin(theta) * 1.6, z0 * 2.2)))
    r += amp * (0.55 * math.sin(6 * theta + 3.2 * t) + 0.35 * math.sin(11 * theta - 4 * t + 1.0) +
                0.22 * math.sin(17 * theta + 6 * t + 2.0) + 0.55 * n)
    r += 0.0035 * math.sin(55 * t) * sstep(0.9, 1.3, z0) * (1 - sstep(1.45, 1.7, z0))   # waist creases
    r += off
    th = theta + 0.65 * k ** 2
    cx = 0.14 * k ** 2
    cy = 0.03 - 0.05 * k - 0.025 * math.exp(-((z0 - 1.68) / 0.10) ** 2)
    z = z0 + 0.09 * max(0.0, 1 - t * 10) * (0.5 + 0.5 * math.sin(3 * theta + 1))
    return Vector((cx + r * math.cos(th), cy + r * math.sin(th), z))


def robe_mesh(name, material, t0, t1, center=None, halfw=None, off=0.0, nt=200, nz=110, thickness=0.012):
    bm = bmesh.new()
    full = center is None
    grid = []
    for j in range(nz + 1):
        t = t0 + (t1 - t0) * j / nz
        if full:
            th0, span = -PI / 2, 2 * PI
        else:
            hw = halfw(t)
            th0, span = center - hw, 2 * hw
        grid.append([bm.verts.new(robe_pt(th0 + span * i / nt, t, off)) for i in range(nt + 1)])
    for j in range(nz):
        for i in range(nt):
            try:
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            except ValueError:
                pass
    if full:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    o = finish_mesh(name, bm, material)
    m = o.modifiers.new("Solid", 'SOLIDIFY')
    m.thickness = thickness
    m.offset = -1
    return o


robe_mesh("Robe", PURPLE, 0.0, 1.0)
robe_mesh("HemBand", GOLD, 0.0, 0.045, off=0.012, nz=6, thickness=0.01)
robe_mesh("HemBandDark", DEEP, 0.045, 0.085, off=0.005, nz=6, thickness=0.008)
robe_mesh("FrontPanel", GOLD, 0.0, 0.72, center=-PI / 2, halfw=lambda t: 0.17,
          off=0.008, nt=10, nz=90, thickness=0.008)
robe_mesh("PanelInlay", PURPLE, 0.05, 0.70, center=-PI / 2, halfw=lambda t: 0.085,
          off=0.013, nt=8, nz=90, thickness=0.006)

# sash: pointed feathers hanging from the belt, following the robe surface
TB = 1.30 / H
for i in range(7):
    a = i - 3
    thc = -PI / 2 + a * 0.10
    t_end = (0.40 + 0.10 * abs(a)) / H

    def hw(t, t_end=t_end):
        u = (TB - t) / (TB - t_end)
        w = 0.05 * (1 + 0.6 * u)
        if u > 0.85:
            w *= max(0.0, (1 - u) / 0.15)
        return w
    robe_mesh(f"Sash{i}", GOLD if i % 2 == 0 else MAGENTA, t_end, TB, center=thc, halfw=hw,
              off=0.016 + 0.0015 * (3 - abs(a)), nt=6, nz=50, thickness=0.005)

# gold scroll swirls around the hem
for k in range(9):
    thc = -PI / 2 + 2 * PI * (k + 0.5) / 9 + 0.3
    pts, rad = [], []
    n = 26
    for i in range(n):
        phi = 0.5 + i / (n - 1) * 2.6 * PI
        rho = 0.115 * (1 - i / (n - 1)) + 0.012
        tt = 0.19 + rho * math.sin(phi) / H * 1.2
        pts.append(robe_pt(thc + rho * math.cos(phi) / 0.60, tt, 0.020))
        rad.append(0.0085 * (1 - 0.5 * i / (n - 1)))
    tube(f"Scroll{k}", GOLD, pts, rad, res=3)

# ------------------------------------------------------------------ upper body & cowl
sphere("Shoulders", PURPLE, (0, 0.0, 1.83), (0.30, 0.18, 0.15), rot=(0, 0, 0.1), seg=48, rings=24)
cone_between("Neck", SKIN, (0, 0.0, 1.84), (0, -0.012, 2.17), 0.072, 0.049, seg=40, caps=True)

bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=48, radius=1.0)
displace_noise(bm, 0.05, 2.2, 3.0)
cowl = finish_mesh("Cowl", bm, PURPLE, loc=(0, 0.03, 1.95), scale=(0.33, 0.26, 0.14))
cowl.modifiers.new("Sub", 'SUBSURF').levels = 1
torus("GoldCollar", GOLD, (0, -0.012, 1.955), 0.175, 0.026, scale=(1.05, 0.88, 0.55))

# belt
torus("Belt", GOLD, (0.012, 0.0, 1.31), 0.205, 0.032)
torus("BeltThin", GOLD, (0.012, 0.0, 1.22), 0.214, 0.012)
sphere("Buckle", GOLD, (0.012, -0.215, 1.31), (0.05, 0.022, 0.05))
tube("TasselCord", MAGENTA, [(0.10, -0.22, 1.28), (0.12, -0.30, 1.0), (0.135, -0.34, 0.70)],
     [0.013, 0.013, 0.011])
sphere("TasselBall", MAGENTA, (0.135, -0.34, 0.67), (0.032, 0.032, 0.032))
cone_between("TasselFringe", MAGENTA, (0.135, -0.34, 0.66), (0.135, -0.34, 0.49), 0.03, 0.05, seg=20)

# ------------------------------------------------------------------ head
HZ = 0.138
HX = [(-1.0, 0.026), (-0.90, 0.046), (-0.72, 0.064), (-0.45, 0.077), (-0.2, 0.086), (0.1, 0.091),
      (0.4, 0.095), (0.72, 0.085), (0.92, 0.055), (1.0, 0.0)]
HYF = [(-1.0, 0.080), (-0.85, 0.092), (-0.5, 0.101), (0.0, 0.104), (0.35, 0.104), (0.70, 0.097),
       (0.92, 0.07), (1.0, 0.0)]
HYB = [(-1.0, 0.060), (-0.7, 0.085), (-0.3, 0.110), (0.2, 0.124), (0.6, 0.117), (0.9, 0.075), (1.0, 0.0)]
EXC, EZ, EW, EH, ETILT = 0.040, 0.012, 0.0185, 0.0095, 0.25   # eye centre x, z, opening half-width/height, tilt

SKIN_BASE = (0.70, 0.40, 0.31)
BLUSH = (0.72, 0.30, 0.25)
LIP = (0.52, 0.12, 0.14)
LIPDARK = (0.18, 0.03, 0.04)
LINER = (0.20, 0.09, 0.07)
BROWC = (0.40, 0.24, 0.08)


def head_base(ux, uy, uz):
    n = max(-1.0, min(1.0, uz))
    s = math.hypot(ux, uy)
    c, si = (1.0, 0.0) if s < 1e-9 else (ux / s, uy / s)
    x = c * tbl(HX, n)
    y = si * (tbl(HYF, n) if si < 0 else tbl(HYB, n))
    return x, y, n * HZ, si


def face_disp(x, z, si, opening=True):
    wf = sstep(0.05, 0.55, -si)
    if wf <= 0:
        return 0.0
    ax = math.sqrt(x * x + 1.5e-4)
    d = 0.0
    if -0.085 < z < 0.05:
        a = tbl([(-0.085, 0.0), (-0.068, 0.016), (-0.058, 0.021), (-0.045, 0.017), (-0.02, 0.011),
                 (0.01, 0.007), (0.03, 0.003), (0.05, 0.0)], z)
        wn = tbl([(-0.085, 0.012), (-0.06, 0.017), (-0.03, 0.013), (0.0, 0.011), (0.05, 0.012)], z)
        d -= a * math.exp(-(x / wn) ** 2)
    d -= 0.011 * gauss(ax - 0.017, z + 0.052, 0.008, 0.008)        # nostril wings
    d += 0.008 * gauss(ax - 0.008, z + 0.073, 0.005, 0.004)        # nostrils
    d += 0.012 * gauss(ax - EXC, z - EZ, 0.030, 0.021)             # eye sockets
    d -= 0.008 * gauss(ax - 0.042, z - 0.040, 0.034, 0.011)        # brow ridge
    d -= 0.006 * gauss(ax - 0.060, z + 0.030, 0.024, 0.024)        # cheekbones
    d -= 0.0125 * gauss(x, z + 0.0885, 0.022, 0.0068)              # upper lip
    d -= 0.004 * gauss(abs(x) - 0.006, z + 0.0925, 0.007, 0.004)   # cupid's bow
    d -= 0.014 * gauss(x, z + 0.1055, 0.019, 0.0088)               # lower lip
    d += 0.007 * gauss(x, z + 0.0965, 0.022, 0.0016)               # mouth line
    d -= 0.008 * gauss(x, z + 0.134, 0.020, 0.014)                 # chin
    d += 0.004 * gauss(x, z + 0.122, 0.020, 0.004)                 # under-lip dip
    if opening:
        dx = ax - EXC
        dz = (z - EZ) - ETILT * dx
        e = math.sqrt((dx / EW) ** 2 + (dz / EH) ** 2)
        d += 0.035 * (1 - sstep(0.78, 1.0, e))
    return d * wf


def surface_y(x, z, opening=False):
    n = max(-1.0, min(1.0, z / HZ))
    hx = max(tbl(HX, n), 1e-4)
    return -tbl(HYF, n) * math.sqrt(max(0.0, 1 - (x / hx) ** 2)) + face_disp(x, z, -1.0, opening)


def face_color(x, z, si):
    wf = sstep(0.0, 0.4, -si)
    ax = abs(x)
    c = SKIN_BASE
    c = mixc(c, BLUSH, 0.55 * gauss(ax - 0.058, z + 0.040, 0.026, 0.020) * wf)
    c = mixc(c, BLUSH, 0.25 * gauss(0, z - 0.095, 0.05, 0.03) * wf)
    lip = max(gauss(x, z + 0.0885, 0.021, 0.0078), gauss(x, z + 0.1055, 0.018, 0.0098))
    c = mixc(c, LIP, sstep(0.25, 0.7, lip) * wf)
    c = mixc(c, LIPDARK, gauss(x, z + 0.0968, 0.022, 0.0011) * wf)
    c = mixc(c, LIPDARK, 0.7 * gauss(ax - 0.008, z + 0.073, 0.005, 0.0035) * wf)
    dx = ax - EXC
    dz = (z - EZ) - ETILT * dx
    e = math.sqrt((dx / EW) ** 2 + (dz / EH) ** 2)
    c = mixc(c, LINER, wf * 0.85 * sstep(0.7, 1.0, e) * (1 - sstep(1.15, 1.7, e)))
    c = mixc(c, (0.55, 0.25, 0.25), 0.25 * wf * sstep(1.2, 1.6, e) * (1 - sstep(2.2, 3.2, e)) * (1 if dz > 0 else 0.3))
    if 0.014 < ax < 0.080:
        zb = 0.047 + 0.009 * (1 - ((ax - 0.045) / 0.032) ** 2)
        th = 0.0058 * (1 - 0.65 * (ax - 0.02) / 0.06)
        w = (1 - sstep(th * 0.45, th, abs(z - zb))) * sstep(0.014, 0.024, ax) * (1 - sstep(0.068, 0.080, ax))
        c = mixc(c, BROWC, 0.9 * w * wf)
    return c


def build_head():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=288, v_segments=200, radius=1.0)
    cols = []
    for v in bm.verts:
        x, y, z, si = head_base(v.co.x, v.co.y, v.co.z)
        if si < 0:
            y += face_disp(x, z, si)
        v.co = Vector((x, y, z))
        cols.append(face_color(x, z, si))
    me = bpy.data.meshes.new("Head")
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ca = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    for i, c in enumerate(cols):
        ca.data[i].color = (*c, 1.0)
    me.materials.append(FACE)
    return me


HEAD_LOC = Vector((0, -0.005, 2.27))
HEAD_ROT = Euler((0.04, -0.07, 0.38), 'XYZ')
rig = bpy.data.objects.new("HeadRig", None)
rig.location, rig.rotation_euler = HEAD_LOC, HEAD_ROT
coll.objects.link(rig)
HEAD_M = Matrix.Translation(HEAD_LOC) @ HEAD_ROT.to_matrix().to_4x4()


def H2W(p):
    return HEAD_M @ Vector(p)


head = link_obj("Head", build_head(), parent=rig)
sm = head.modifiers.new("Sub", 'SUBSURF')
sm.levels, sm.render_levels = 0, 1

# ears
for s in (-1, 1):
    sphere("Ear", SKIN, (s * 0.088, 0.008, -0.002), (0.011, 0.020, 0.030), rot=(0, 0, s * 0.25),
           seg=24, rings=12, parent=rig)

# eyes
ye = surface_y(EXC + 0.018, EZ) + 0.0165
EYE_MAT = make_eye_material(1.0)
R_EYE = 0.0225
for s in (-1, 1):
    c = (s * EXC, ye, EZ)
    sphere("Eyeball", EYE_MAT, c, (R_EYE, R_EYE, R_EYE), seg=96, rings=64, parent=rig)
    # eyelashes
    for k in range(11):
        t = -1 + 2 * k / 10
        dx = t * EW
        ax = EXC + dx
        z = EZ + ETILT * dx + EH * math.sqrt(max(0, 1 - t * t))
        x = s * ax
        y = surface_y(ax, z) - 0.0015
        out = Vector((s * (0.4 * t + 0.25), -0.5, 0.8)).normalized() * 0.0105 * (0.7 + 0.3 * math.sqrt(1 - t * t))
        tube("Lash", LASH, [(x, y, z), (x + out.x * 0.5, y + out.y * 0.5, z + out.z * 0.55),
                            (x + out.x, y + out.y, z + out.z)], [0.0009, 0.0007, 0.0003], res=2, parent=rig)

# ------------------------------------------------------------------ hair
def build_cap():
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=200, v_segments=140, radius=1.0)
    kill = []
    for v in bm.verts:
        x, y, z, si = head_base(v.co.x, v.co.y, v.co.z)
        h = 0.02 + 0.085 * max(0, -si) - 0.065 * max(0, si)
        if z < h:
            kill.append(v)
            continue
        v.co = Vector((x * 1.05, y * 1.05, z * 1.025 + 0.002))
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    displace_noise(bm, 0.0018, 25.0, 1.0)
    return bm


cap = finish_mesh("HairCap", build_cap(), CAPMAT, parent=rig)
m = cap.modifiers.new("Solid", 'SOLIDIFY')
m.thickness = 0.008
m.offset = 1
cap.modifiers.new("Sub", 'SUBSURF').levels = 1


def sample_guide(G, f):
    f = max(0.0, min(1.0, f)) * (len(G) - 1)
    i = min(int(f), len(G) - 2)
    return G[i].lerp(G[i + 1], f - i)


def hair_clump(name, mat_, guide, n, spread_root, spread_tip, rad, seed=0, wave=0.012, wv=(0.0, 0.0, 0.0), fr=6.0):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 6
    cu.bevel_depth = 1.0
    cu.bevel_resolution = 1
    cu.use_fill_caps = False
    rnd = random.Random(seed)
    G = [Vector(p) for p in guide]
    m_ = len(G)
    cph = rnd.uniform(0, 6.28)
    for _ in range(n):
        sp = cu.splines.new('NURBS')
        sp.points.add(m_ - 1)
        o = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
        ph, ln = rnd.uniform(0, 6.28), rnd.uniform(0.86, 1.0)
        for k, p in enumerate(sp.points):
            f = k / (m_ - 1)
            q = sample_guide(G, f * ln)
            sprd = spread_root + (spread_tip - spread_root) * f
            q = q + o * sprd * (0.65 + 0.35 * math.sin(ph + f * 5))
            q.z += wave * math.sin(ph + f * 9) * f
            wph = math.sin(f * fr + cph + 0.35 * math.sin(ph)) * min(1.0, f * 3)
            q += Vector((wv[0] * wph, wv[1] * wph, wv[2] * wph))
            p.co = (q.x, q.y, q.z, 1.0)
            p.radius = rad * (1 - 0.75 * f ** 1.6)
        sp.order_u = 4
        sp.use_endpoint_u = True
    return link_obj(name, cu, mat_)


def robe_front_y(x, z, clear):
    t = min(1.0, z / H)
    best = None
    for i in range(121):
        th = -PI + PI * i / 120
        p = robe_pt(th, t)
        if best is None or abs(p.x - x) < abs(best.x - x):
            best = p
    return best.y - clear


def drape(xs_zs_clear):
    return [(x, robe_front_y(x, z, c), z) for x, z, c in xs_zs_clear]


# left cascade: hairline -> over the cowl -> down the chest
L_local = [(-0.060, -0.082, 0.100), (-0.085, -0.085, 0.060), (-0.098, -0.072, 0.012),
           (-0.108, -0.050, -0.050)]
for j, (mt, sd, sx) in enumerate(((BLONDE_A, 1, 0.0), (BLONDE_B, 2, 0.018), (BLONDE_C, 3, -0.016))):
    gl = [H2W(p) + Vector((sx, 0, 0)) for p in L_local]
    gl += [Vector(p) + Vector((sx, 0, 0)) for p in
           [(-0.17, -0.10, 2.10)] + drape([(-0.22, 1.98, 0.030), (-0.23, 1.80, 0.032), (-0.21, 1.62, 0.034),
                                          (-0.20, 1.45, 0.036), (-0.20, 1.30, 0.040), (-0.22, 1.18, 0.044)])]
    hair_clump(f"HairLeft{j}", mt, gl, 240, 0.012, 0.020, 0.0011, seed=sd, wave=0.006, wv=(0.022, 0.012, 0.0), fr=7.0)

# right: windswept to +X
R_local = [(0.060, -0.082, 0.100), (0.090, -0.085, 0.060), (0.115, -0.080, 0.030)]
R_world = [[(0.36, -0.06, 2.34), (0.52, 0.00, 2.31), (0.66, 0.05, 2.20), (0.78, 0.08, 2.02), (0.84, 0.08, 1.84)],
           [(0.34, -0.05, 2.38), (0.50, 0.02, 2.40), (0.65, 0.07, 2.30), (0.78, 0.10, 2.14), (0.88, 0.10, 1.96)],
           [(0.34, -0.03, 2.28), (0.50, 0.03, 2.22), (0.62, 0.08, 2.10), (0.72, 0.10, 1.92), (0.76, 0.10, 1.72)]]
for j, (mt, sd) in enumerate(((BLONDE_B, 11), (BLONDE_A, 12), (BLONDE_C, 13))):
    gl = [H2W(p) for p in R_local] + [Vector(p) for p in R_world[j]]
    hair_clump(f"HairRight{j}", mt, gl, 220, 0.012, 0.026, 0.0011, seed=sd, wave=0.01, wv=(0.0, 0.02, 0.07), fr=6.0)

# crown sweep up and right
T_local = [(0.020, -0.060, 0.135), (0.060, -0.020, 0.150)]
gl = [H2W(p) for p in T_local] + [Vector(p) for p in
                                   [(0.20, -0.02, 2.54), (0.36, 0.0, 2.60), (0.54, 0.04, 2.57),
                                    (0.70, 0.07, 2.45), (0.80, 0.08, 2.28)]]
hair_clump("HairTop", BLONDE_B, gl, 200, 0.012, 0.022, 0.0011, seed=21, wave=0.01, wv=(0.0, 0.02, 0.06), fr=7.0)

def cap_pt(x, z, lift=0.003):
    n = max(-1.0, min(1.0, z / HZ))
    hx = max(tbl(HX, n) * 1.05, 1e-4)
    return (x, -1.05 * tbl(HYF, n) * math.sqrt(max(0.0, 1 - (x / hx) ** 2)) - lift, z)


# front wisps framing the face
for s, sd in ((-1, 31), (1, 32)):
    for q, x0 in enumerate((0.004, 0.026, 0.050)):
        pts = [cap_pt(s * x0, 0.112), cap_pt(s * (x0 + 0.030), 0.104), cap_pt(s * (x0 + 0.058), 0.086),
               cap_pt(s * (x0 + 0.074), 0.058), cap_pt(s * min(0.097, x0 + 0.085), 0.020),
               cap_pt(s * 0.100, -0.030, 0.0)]
        gl = [H2W(p) for p in pts]
        hair_clump(f"Fringe{sd}_{q}", BLONDE_B if q != 1 else BLONDE_A, gl, 70, 0.006, 0.010, 0.0010,
                   seed=sd * 10 + q, wave=0.002, wv=(0.003, 0.0, 0.003), fr=5.0)

# ------------------------------------------------------------------ hood (open at the front) + pearl trim
hc, hs = Vector((0, 0.05, 2.30)), Vector((0.27, 0.28, 0.32))
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=36, radius=1.0)
kill = [v for v in bm.verts if v.co.y < -0.30 and v.co.z > -0.72]
bmesh.ops.delete(bm, geom=kill, context='VERTS')
edge_pts = []
for e in bm.edges:
    if e.is_boundary:
        for v in e.verts:
            if v.co.z > -0.50:
                p = hc + Vector((v.co.x * hs.x, v.co.y * hs.y, v.co.z * hs.z))
                if all((p - q).length > 0.034 for q in edge_pts):
                    edge_pts.append(p)
displace_noise(bm, 0.045, 2.0, 7.0)
hood = finish_mesh("Hood", bm, PURPLE, loc=hc, scale=hs)
m = hood.modifiers.new("Solid", 'SOLIDIFY')
m.thickness = 0.06
m.offset = -1
hood.modifiers.new("Sub", 'SUBSURF').levels = 1
for i, p in enumerate(edge_pts):
    sphere(f"HoodPearl{i}", PEARL, p, (0.030, 0.030, 0.034), seg=20, rings=12)
for s in (-1, 1):
    path = [(s * 0.23, -0.06, 2.10), (s * 0.20, -0.17, 1.97), (s * 0.15, -0.215, 1.80), (s * 0.10, -0.225, 1.62)]
    for a_, b_ in zip(path[:-1], path[1:]):
        for q in range(3):
            f = q / 3.0
            sphere("ChestPearl", PEARL, tuple(a_[i] + (b_[i] - a_[i]) * f for i in range(3)),
                   (0.024, 0.024, 0.026), seg=16, rings=10)


# ------------------------------------------------------------------ arms & hands
def two_bone_ik(S, W, l1, l2, pole):
    S, W, pole = Vector(S), Vector(W), Vector(pole)
    d = W - S
    dist = min(d.length, l1 + l2 - 1e-4)
    dirv = d.normalized()
    a = (l1 ** 2 - l2 ** 2 + dist ** 2) / (2 * dist)
    h = math.sqrt(max(l1 ** 2 - a ** 2, 0.0))
    perp = (pole - dirv * pole.dot(dirv)).normalized()
    return S + dirv * a + perp * h


def make_hand(name, wrist, f_dir, palm_dir, side=1, curl=0.5, thumb=0.4, scale=1.0):
    hr = bpy.data.objects.new(name + "Rig", None)
    coll.objects.link(hr)
    hr.location = wrist
    Y = Vector(f_dir).normalized()
    Z = -Vector(palm_dir).normalized()
    Z = (Z - Y * Z.dot(Y)).normalized()
    X = Y.cross(Z)
    hr.rotation_euler = Matrix((X, Y, Z)).transposed().to_euler()
    hr.scale = (scale, scale, scale)
    sphere(name + "Palm", SKIN, (0, 0.060, 0), (0.056, 0.064, 0.021), seg=32, rings=16, parent=hr)
    cone_between(name + "Wrist", SKIN, (0, -0.07, 0), (0, 0.01, 0), 0.030, 0.032, seg=24, caps=True, parent=hr)
    xs = [0.039, 0.013, -0.013, -0.037]
    ys = [0.112, 0.120, 0.114, 0.103]
    lens = [0.95, 1.0, 0.95, 0.78]
    for k in range(4):
        P = Vector((xs[k] * -side, ys[k], 0))
        pts = [P]
        a = 0.0
        L = [0.052 * lens[k], 0.032 * lens[k], 0.024 * lens[k]]
        for j, fl in enumerate((curl * 0.9, curl * 1.15, curl * 0.8)):
            a += fl
            P = P + Vector((0.002 * (k - 1.5) * j, math.cos(a), -math.sin(a))) * L[j]
            pts.append(P)
        tube(f"{name}Finger{k}", SKIN, [(p.x, p.y, p.z) for p in pts], [0.0096, 0.0088, 0.0080, 0.0066], res=4, parent=hr)
    th = thumb
    sx = -side
    tp = [(sx * 0.046, 0.020, -0.004), (sx * 0.070, 0.055 - th * 0.01, -0.012 - th * 0.01),
          (sx * (0.080 - 0.020 * th), 0.085, -0.022 - th * 0.02),
          (sx * (0.072 - 0.045 * th), 0.104, -0.030 - th * 0.03)]
    tube(f"{name}Thumb", SKIN, tp, [0.0130, 0.0118, 0.0105, 0.0088], res=4, parent=hr)
    return hr


# raised arm (viewer's right): hand gathers the hood edge at the collar
S1 = Vector((0.27, 0.0, 1.84))
hand_f = Vector((-0.35, -0.25, 0.9)).normalized()
T1 = Vector((0.15, -0.215, 2.02))
W1 = T1 - hand_f * 0.075
E1 = two_bone_ik(S1, W1, 0.36, 0.34, (0.8, 0.3, -0.9))
tube("SleeveUpperR", PURPLE, [S1, S1.lerp(E1, 0.5) + Vector((0.01, -0.01, 0)), E1], [0.078, 0.072, 0.066], res=10)
sphere("ElbowR", PURPLE, E1, (0.066, 0.066, 0.066))
make_hand("HandR", W1, hand_f, (-0.55, 0.6, -0.1), side=1, curl=0.48, thumb=0.5, scale=1.18)


def bell(name, mat_, p0, p1, r0, r1, s0=0.0, s1=1.0, off=0.0, fold=0.05, seed=0.0,
         nth=120, nl=30, thickness=0.01, hem=0.025):
    p0, p1 = Vector(p0), Vector(p1)
    ax = p1 - p0
    Lh = ax.length
    a = ax.normalized()
    helper = Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))
    u = (helper - a * helper.dot(a)).normalized()
    v = a.cross(u)
    bm = bmesh.new()
    rows = []
    for j in range(nl + 1):
        s = s0 + (s1 - s0) * j / nl
        row = []
        for i in range(nth + 1):
            th = 2 * PI * i / nth
            rr = r0 + (r1 - r0) * s ** 1.5
            n = noise.noise(Vector((math.cos(th) * 1.7, math.sin(th) * 1.7, s * 2.5 + seed)))
            f = fold * s ** 1.2 * (math.sin(5 * th + seed) + 0.6 * math.sin(9 * th + 2 * seed) + 0.8 * n)
            rr = rr * (1 + f) + off
            along = Lh * s + hem * s ** 6 * math.sin(3 * th + seed)
            row.append(bm.verts.new(p0 + a * along + (u * math.cos(th) + v * math.sin(th)) * rr))
        rows.append(row)
    for j in range(nl):
        for i in range(nth):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    o = finish_mesh(name, bm, mat_)
    mm = o.modifiers.new("Solid", 'SOLIDIFY')
    mm.thickness = thickness
    mm.offset = -1
    return o


# right bell sleeve pulled back along the forearm, bare forearm shows to the hand
bend = (W1 + (E1 - W1) * 0.42)
bell("BellR", PURPLE, E1, bend, 0.074, 0.19, fold=0.07, seed=1.3)
bell("CuffR", GOLD, E1, bend, 0.074, 0.19, s0=0.93, s1=1.0, off=0.006, fold=0.0, nl=3, thickness=0.01, hem=0.0)
cone_between("ForearmR", SKIN, bend - (W1 - bend).normalized() * 0.03, W1, 0.040, 0.028, seg=28, caps=True)

# lowered arm (viewer's left): long bell sleeve over the forearm, hand hangs below
S2 = Vector((-0.27, 0.0, 1.84))
W2 = Vector((-0.43, -0.10, 1.10))
E2 = two_bone_ik(S2, W2, 0.36, 0.34, (-0.4, 0.8, -0.2))
tube("SleeveUpperL", PURPLE, [S2, S2.lerp(E2, 0.5) + Vector((-0.01, -0.01, 0)), E2], [0.085, 0.085, 0.080], res=10)
sphere("ElbowL", PURPLE, E2, (0.080, 0.080, 0.080))
end2 = W2 + Vector((0.0, 0.0, 0.05))
bell("BellL", PURPLE, E2, end2, 0.078, 0.20, fold=0.07, seed=4.1, hem=0.03)
bell("CuffL", GOLD, E2, end2, 0.078, 0.20, s0=0.94, s1=1.0, off=0.006, fold=0.0, nl=3, thickness=0.01, hem=0.0)
make_hand("HandL", W2 + Vector((0, 0.0, -0.02)), (-0.05, -0.15, -1), (0.9, 0.2, 0), side=-1, curl=0.22, thumb=0.2, scale=1.18)

# ------------------------------------------------------------------ stage, lights, cameras
floor = bpy.data.meshes.new("Floor")
fb = bmesh.new()
for x, y in ((-8, -8), (8, -8), (8, 8), (-8, 8)):
    fb.verts.new((x, y, 0))
fb.faces.new(fb.verts)
fb.to_mesh(floor)
fb.free()
link_obj("Floor", floor, mat("Floor", (0.10, 0.09, 0.12), rough=0.45))


def light(name, loc, energy, size, color=(1, 1, 1), target=(0, 0, 1.4)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.color, ld.size = energy, color, size
    o = link_obj(name, ld, loc=loc)
    d = Vector(target) - Vector(loc)
    o.rotation_euler = Vector((0, 0, -1)).rotation_difference(d.normalized()).to_euler()


light("Key", (2.6, -3.4, 3.6), 520, 3.2, (1.0, 0.95, 0.88))
light("Fill", (-3.6, -2.4, 2.0), 150, 4.0, (0.80, 0.86, 1.0))
light("Rim", (-1.8, 3.2, 3.4), 420, 2.5, (0.85, 0.80, 1.0))
light("RimR", (2.8, 2.6, 2.8), 260, 2.5, (1.0, 0.92, 0.85))

cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 62
cam = link_obj("Camera", cam_d, loc=(2.1, -5.0, 1.6))
cam.rotation_euler = (Vector((0.12, 0, 1.22)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam_d.dof.use_dof = True
cam_d.dof.focus_distance = (HEAD_LOC - cam.location).length
cam_d.dof.aperture_fstop = 9.0
scene.camera = cam

face_d = bpy.data.cameras.new("CamFace")
face_d.lens = 85
facing = (HEAD_ROT.to_matrix() @ Vector((0, -1, 0)))
fcam = link_obj("CameraFace", face_d, loc=HEAD_LOC + facing * 0.95 + Vector((0.0, 0, 0.02)))
fcam.rotation_euler = ((HEAD_LOC + Vector((0, 0, 0.0))) - fcam.location).to_track_quat('-Z', 'Y').to_euler()
face_d.dof.use_dof = True
face_d.dof.focus_distance = (HEAD_LOC + Vector((0, -0.09, 0.01)) - fcam.location).length
face_d.dof.aperture_fstop = 8.0

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
if bg:
    bg.inputs[0].default_value = (0.045, 0.05, 0.07, 1)
    bg.inputs[1].default_value = 1.0

scene.render.engine = 'CYCLES'
scene.cycles.samples = int(os.environ.get("MAGE_SAMPLES", "64"))
scene.cycles.use_adaptive_sampling = True
scene.cycles.max_bounces = 6
scene.render.resolution_x, scene.render.resolution_y = 800, 1200
try:
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.cycles.use_denoising = True
except Exception:
    pass

try:
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].shading.type = 'MATERIAL'
except Exception:
    pass

out_png = os.environ.get("MAGE_RENDER")
out_face = os.environ.get("MAGE_FACE")
out_blend = os.environ.get("MAGE_BLEND")
if out_blend:
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
scene.cycles.device = 'CPU'
if out_face:
    scene.view_settings.exposure = -0.45
    scene.camera = fcam
    scene.render.resolution_x, scene.render.resolution_y = 800, 800
    scene.render.filepath = out_face
    bpy.ops.render.render(write_still=True)
if out_png:
    scene.view_settings.exposure = 0.0
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 800, 1200
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)
print("Mage v3 built.")
