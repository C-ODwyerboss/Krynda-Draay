"""
Robed mage v2 - run inside Blender (Scripting tab > Open > Run Script)
or headless:  MAGE_RENDER=/path/out.png MAGE_BLEND=/path/out.blend python robed_mage_v2.py

Built entirely with the data API (no operators), so it also works in the bpy module.
Switch the viewport to Material Preview (or Rendered) to see colours.
"""
import bpy
import bmesh
import math
import os
import random
from mathutils import Vector

random.seed(11)
PI = math.pi

# ------------------------------------------------------------------ clean scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
            bpy.data.lights, bpy.data.cameras):
    for b in list(blk):
        blk.remove(b)

scene = bpy.context.scene
coll = scene.collection


# ------------------------------------------------------------------ materials
def mat(name, color, metallic=0.0, rough=0.5, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    m.diffuse_color = color
    return m


PURPLE = mat("RobePurple", (0.10, 0.025, 0.24, 1), rough=0.6)
DEEP = mat("RobeDeep", (0.06, 0.015, 0.14, 1), rough=0.7)
LAVENDER = mat("HoodTrim", (0.6, 0.52, 0.9, 1), rough=0.45)
GOLD = mat("Gold", (1.0, 0.72, 0.18, 1), metallic=0.9, rough=0.28)
MAGENTA = mat("Tassel", (0.6, 0.08, 0.45, 1), rough=0.5)
SKIN = mat("Skin", (0.85, 0.58, 0.46, 1), rough=0.55)
BLONDE = mat("Blonde", (0.98, 0.82, 0.38, 1), rough=0.35)
WHITE = mat("Sclera", (0.95, 0.95, 0.95, 1), rough=0.3)
IRIS = mat("Iris", (0.22, 0.3, 0.6, 1), rough=0.2)
DARK = mat("Dark", (0.05, 0.03, 0.03, 1), rough=0.4)
LIPS = mat("Lips", (0.75, 0.3, 0.33, 1), rough=0.4)
BROW = mat("Brow", (0.55, 0.4, 0.15, 1), rough=0.5)


# ------------------------------------------------------------------ helpers
def link_obj(name, data, material=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    o = bpy.data.objects.new(name, data)
    o.location, o.rotation_euler, o.scale = loc, rot, scale
    if material is not None:
        data.materials.append(material)
    coll.objects.link(o)
    return o


def finish_mesh(name, bm, material, smooth=True, **kw):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link_obj(name, me, material, **kw)


def sphere(name, material, loc, scale, rot=(0, 0, 0), seg=32, rings=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    return finish_mesh(name, bm, material, loc=loc, rot=rot, scale=scale)


def cone_between(name, material, p0, p1, r0, r1, seg=32, caps=False):
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=seg,
                          radius1=r0, radius2=r1, depth=d.length)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_euler()
    return finish_mesh(name, bm, material, loc=(p0 + p1) / 2, rot=rot)


def torus(name, material, loc, R, r, scale=(1, 1, 1), rot=(0, 0, 0), nu=56, nv=12):
    bm = bmesh.new()
    vs = []
    for i in range(nu):
        u = 2 * PI * i / nu
        row = []
        for j in range(nv):
            v = 2 * PI * j / nv
            row.append(bm.verts.new(((R + r * math.cos(v)) * math.cos(u),
                                     (R + r * math.cos(v)) * math.sin(u),
                                     r * math.sin(v))))
        vs.append(row)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((vs[i][j], vs[(i + 1) % nu][j],
                          vs[(i + 1) % nu][(j + 1) % nv], vs[i][(j + 1) % nv]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish_mesh(name, bm, material, loc=loc, rot=rot, scale=scale)


def tube(name, material, pts, radii, res=5, cyclic=False):
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
    sp.use_cyclic_u = cyclic
    return link_obj(name, cu, material)


def ramp(n, a, b, power=1.0):
    return [a + (b - a) * (i / (n - 1)) ** power for i in range(n)]


def ribbon(name, material, pts, widths, thickness=0.006):
    """Flat pointed strip following pts, width along world X."""
    bm = bmesh.new()
    rows = []
    for p, w in zip(pts, widths):
        rows.append((bm.verts.new((p[0] - w, p[1], p[2])),
                     bm.verts.new((p[0] + w, p[1], p[2]))))
    for a, b in zip(rows[:-1], rows[1:]):
        try:
            bm.faces.new((a[0], a[1], b[1], b[0]))
        except ValueError:
            pass
    o = finish_mesh(name, bm, material)
    m = o.modifiers.new("Solid", 'SOLIDIFY')
    m.thickness = thickness
    return o


# ------------------------------------------------------------------ robe surface
H = 1.85


def robe_pt(theta, t, off=0.0):
    """Point on the flowing robe. theta=-pi/2 is the front (-Y)."""
    k = 1.0 - t
    r = 0.2 + 0.62 * k ** 2.2
    amp = 0.05 * k ** 1.3
    r += amp * math.sin(7 * theta + 2.5 * t) + 0.55 * amp * math.sin(12 * theta - 3 * t + 1)
    r += off
    th = theta + 0.65 * k ** 2          # swirl
    cx = 0.14 * k ** 2                  # train drifts to +X (wind)
    cy = 0.03 - 0.05 * k
    z = H * t + 0.09 * max(0.0, 1 - t * 10) * (0.5 + 0.5 * math.sin(3 * theta + 1))
    return Vector((cx + r * math.cos(th), cy + r * math.sin(th), z))


def robe_mesh(name, material, t0, t1, center=None, halfw=None, off=0.0,
              nt=72, nz=36, thickness=0.012):
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
        row = [bm.verts.new(robe_pt(th0 + span * i / nt, t, off)) for i in range(nt + 1)]
        grid.append(row)
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
robe_mesh("HemBand", GOLD, 0.0, 0.05, off=0.012, nz=4, thickness=0.01)
robe_mesh("HemBandDark", DEEP, 0.05, 0.095, off=0.004, nz=4, thickness=0.008)
robe_mesh("FrontPanel", GOLD, 0.0, 0.74, center=-PI / 2, halfw=lambda t: 0.17,
          off=0.008, nt=8, nz=36, thickness=0.008)
robe_mesh("PanelInlay", PURPLE, 0.06, 0.70, center=-PI / 2, halfw=lambda t: 0.085,
          off=0.013, nt=6, nz=36, thickness=0.006)

# gold scroll swirls around the hem
for k in range(9):
    thc = -PI / 2 + 2 * PI * (k + 0.5) / 9 + 0.3
    pts, rad = [], []
    n = 22
    for i in range(n):
        phi = 0.5 + i / (n - 1) * 2.6 * PI
        rho = 0.115 * (1 - i / (n - 1)) + 0.012
        tt = 0.20 + rho * math.sin(phi) / H * 1.2
        pts.append(robe_pt(thc + rho * math.cos(phi) / 0.62, tt, 0.018))
        rad.append(0.0085 * (1 - 0.5 * i / (n - 1)))
    tube(f"Scroll{k}", GOLD, pts, rad, res=3)

# ------------------------------------------------------------------ torso / collar
sphere("Shoulders", PURPLE, (0, 0.0, 1.83), (0.34, 0.19, 0.17), rot=(0, 0, 0.1))
cone_between("Neck", SKIN, (0, -0.01, 1.88), (0, -0.015, 2.12), 0.05, 0.045, seg=20, caps=True)
sphere("Cowl", PURPLE, (0, 0.03, 1.95), (0.40, 0.28, 0.15))
torus("GoldCollar", GOLD, (0, -0.015, 1.95), 0.18, 0.028, scale=(1.05, 0.85, 0.55))

# ------------------------------------------------------------------ belt / sash
torus("Belt", GOLD, (0.01, 0.0, 1.33), 0.25, 0.034, scale=(1, 0.98, 1))
torus("BeltThin", GOLD, (0.01, 0.0, 1.25), 0.255, 0.014)
sphere("Buckle", GOLD, (0.01, -0.255, 1.33), (0.05, 0.022, 0.05))
for i in range(7):
    a = (i - 3) / 3.0
    top = (0.01 + a * 0.13, -0.255, 1.28)
    bot = (0.01 + a * 0.46, -0.37, 0.52 + 0.06 * abs(a))
    n = 7
    pts = [(top[0] + (bot[0] - top[0]) * s, top[1] + (bot[1] - top[1]) * s ** 1.5,
            top[2] + (bot[2] - top[2]) * s) for s in [j / (n - 1) for j in range(n)]]
    w = [0.030 + 0.020 * s for s in [j / (n - 1) for j in range(n)]]
    w[-1] = 0.002
    ribbon(f"Sash{i}", GOLD if i % 2 == 0 else MAGENTA, pts, w)
tube("TasselCord", MAGENTA, [(0.1, -0.27, 1.30), (0.12, -0.31, 1.0), (0.13, -0.33, 0.72)],
     [0.013, 0.013, 0.011])
sphere("TasselBall", MAGENTA, (0.13, -0.33, 0.69), (0.032, 0.032, 0.032))
cone_between("TasselFringe", MAGENTA, (0.13, -0.33, 0.68), (0.13, -0.33, 0.50), 0.03, 0.045, seg=16)

# ------------------------------------------------------------------ head
sphere("Head", SKIN, (0, -0.02, 2.26), (0.135, 0.14, 0.165), rot=(0, 0, 0.1))
sphere("Chin", SKIN, (0, -0.06, 2.15), (0.085, 0.085, 0.075))
for s in (-1, 1):
    sphere("Sclera", WHITE, (s * 0.052, -0.146, 2.30), (0.028, 0.012, 0.021))
    sphere("Iris", IRIS, (s * 0.052, -0.156, 2.30), (0.016, 0.006, 0.016))
    sphere("Pupil", DARK, (s * 0.052, -0.160, 2.30), (0.008, 0.003, 0.008))
    tube("Brow", BROW, [(s * 0.085, -0.135, 2.345), (s * 0.055, -0.15, 2.358), (s * 0.025, -0.15, 2.35)],
         [0.005, 0.0065, 0.004])
cone_between("Nose", SKIN, (0, -0.15, 2.245), (0, -0.172, 2.24), 0.015, 0.008, seg=12, caps=True)
sphere("Lips", LIPS, (0, -0.152, 2.19), (0.03, 0.009, 0.009))
sphere("Ear_L", SKIN, (-0.128, -0.02, 2.26), (0.012, 0.02, 0.03))
sphere("Ear_R", SKIN, (0.128, -0.02, 2.26), (0.012, 0.02, 0.03))

# ------------------------------------------------------------------ hood (open at the front) + bead trim
hc, hs = Vector((0, 0.05, 2.30)), Vector((0.27, 0.28, 0.32))
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=22, radius=1.0)
kill = [v for v in bm.verts if v.co.y < -0.30 and v.co.z > -0.72]
bmesh.ops.delete(bm, geom=kill, context='VERTS')
edge_pts = []
for e in bm.edges:
    if e.is_boundary:
        for v in e.verts:
            if v.co.z > -0.50:
                p = hc + Vector((v.co.x * hs.x, v.co.y * hs.y, v.co.z * hs.z))
                if all((p - q).length > 0.02 for q in edge_pts):
                    edge_pts.append(p)
hood = finish_mesh("Hood", bm, PURPLE, loc=hc, scale=hs)
m = hood.modifiers.new("Solid", 'SOLIDIFY')
m.thickness = 0.06
m.offset = -1
for i, p in enumerate(edge_pts):
    sphere(f"HoodBead{i}", LAVENDER, p, (0.030, 0.030, 0.032), seg=14, rings=8)

# bead rows hanging down the chest from the hood edge
for s in (-1, 1):
    path = [(s * 0.23, -0.06, 2.12), (s * 0.21, -0.14, 1.97), (s * 0.15, -0.20, 1.80), (s * 0.10, -0.215, 1.62)]
    for a, b in zip(path[:-1], path[1:]):
        for q in range(3):
            f = q / 3.0
            sphere("ChestBead", LAVENDER, tuple(a[i] + (b[i] - a[i]) * f for i in range(3)),
                   (0.026, 0.026, 0.026), seg=12, rings=8)

# ------------------------------------------------------------------ hair
def strand(name, pts, rmax=0.05, rmin=0.006, jitter=0.012):
    jp = [tuple(c + random.uniform(-jitter, jitter) for c in p) for p in pts]
    tube(name, BLONDE, jp, ramp(len(pts), rmax, rmin, 0.8), res=4)


left = [(-0.12, -0.12, 2.40), (-0.18, -0.14, 2.22), (-0.21, -0.14, 2.0), (-0.23, -0.13, 1.78),
        (-0.25, -0.1, 1.55), (-0.30, -0.06, 1.33)]
right = [(0.12, -0.12, 2.42), (0.22, -0.13, 2.30), (0.36, -0.10, 2.25), (0.52, -0.04, 2.18),
         (0.66, 0.04, 2.05), (0.80, 0.06, 1.82)]
for i in range(4):
    dx = random.uniform(-0.04, 0.04)
    strand(f"HairL{i}", [(x + dx * (j / 5), y, z + random.uniform(-0.02, 0.02) * (j / 5))
                          for j, (x, y, z) in enumerate(left)])
for i in range(5):
    dz = random.uniform(-0.06, 0.10)
    strand(f"HairR{i}", [(x, y + random.uniform(-0.03, 0.03) * (j / 5), z + dz * (j / 5))
                          for j, (x, y, z) in enumerate(right)], jitter=0.015)
for s in (-1, 1):
    for i in range(2):
        strand(f"Bang{s}_{i}", [(s * 0.02, -0.10, 2.44), (s * 0.07, -0.15, 2.41),
                                (s * 0.115, -0.155, 2.34), (s * 0.135, -0.14, 2.27 - 0.02 * i)],
               rmax=0.03, rmin=0.006, jitter=0.006)
# flyaway curls up and out
for i in range(3):
    strand(f"Fly{i}", [(0.18, -0.10, 2.44), (0.30, -0.06, 2.52 + 0.03 * i), (0.46, 0.0, 2.50 + 0.04 * i),
                       (0.58, 0.05, 2.38), (0.68, 0.08, 2.30)], rmax=0.03, rmin=0.004)

# ------------------------------------------------------------------ arms
def hand(center, direction, scale=1.0):
    d = Vector(direction).normalized()
    c = Vector(center)
    sphere("Palm", SKIN, c, (0.040 * scale, 0.026 * scale, 0.048 * scale))
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    for k in range(4):
        off = side * (-0.027 + 0.018 * k) * scale
        base = c + off
        pts = [base, base + d * 0.04 * scale + Vector((0, -0.01, 0)),
               base + d * 0.065 * scale + Vector((0, -0.022, 0.0)),
               base + d * 0.075 * scale + Vector((0, -0.03, -0.01))]
        tube(f"Finger{k}", SKIN, pts, [0.011 * scale, 0.010 * scale, 0.009 * scale, 0.007 * scale], res=3)
    pts = [c + side * 0.035 * scale, c + side * 0.05 * scale + d * 0.03 * scale,
           c + side * 0.045 * scale + d * 0.055 * scale]
    tube("Thumb", SKIN, pts, [0.012 * scale, 0.010 * scale, 0.008 * scale], res=3)


# right arm (viewer's right): raised, hand gathering the hood edge at the collar
sh, el, wr = (0.27, 0.0, 1.84), (0.50, -0.10, 1.58), (0.20, -0.22, 1.98)
tube("SleeveRaised", PURPLE, [sh, ((sh[0] + el[0]) / 2 + 0.04, -0.06, 1.74), el,
                              ((el[0] + wr[0]) / 2, -0.17, 1.8), wr],
     [0.085, 0.085, 0.080, 0.072, 0.065], res=8)
cone_between("BellSleeveR", PURPLE, wr, (0.40, -0.20, 1.55), 0.075, 0.15)
cone_between("CuffR", GOLD, (wr[0] + 0.02, wr[1] + 0.02, wr[2] - 0.02),
             (wr[0] + 0.08, wr[1] + 0.05, wr[2] - 0.08), 0.078, 0.1, seg=32)
hand((0.15, -0.23, 2.03), (-0.5, -0.2, 0.8))

# left arm (viewer's left): lowered, wide bell sleeve
sh2, el2, wr2 = (-0.27, 0.0, 1.84), (-0.43, -0.05, 1.55), (-0.41, -0.17, 1.28)
tube("SleeveDown", PURPLE, [sh2, (-0.35, -0.03, 1.70), el2, (-0.42, -0.11, 1.40), wr2],
     [0.085, 0.09, 0.10, 0.13, 0.17], res=8)
cone_between("BellSleeveL", PURPLE, wr2, (-0.48, -0.15, 0.98), 0.17, 0.25)
cone_between("CuffL", GOLD, (-0.475, -0.15, 1.02), (-0.485, -0.15, 0.97), 0.245, 0.255, seg=36)
hand((-0.45, -0.17, 1.05), (-0.1, -0.05, -1), scale=0.9)

# ------------------------------------------------------------------ stage
floor = bpy.data.meshes.new("Floor")
fb = bmesh.new()
for x, y in ((-6, -6), (6, -6), (6, 6), (-6, 6)):
    fb.verts.new((x, y, 0))
fb.faces.new(fb.verts)
fb.to_mesh(floor)
fb.free()
link_obj("Floor", floor, mat("Floor", (0.78, 0.76, 0.85, 1), rough=0.9))


def light(name, kind, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.size = size
    o = link_obj(name, ld, loc=loc)
    d = Vector((0, 0, 1.3)) - Vector(loc)
    o.rotation_euler = Vector((0, 0, -1)).rotation_difference(d.normalized()).to_euler()
    return o


light("Key", 'AREA', (2.5, -3.5, 3.8), 180, 3.0, (1.0, 0.96, 0.9))
light("Fill", 'AREA', (-3.5, -2.5, 2.0), 70, 4.0, (0.85, 0.9, 1.0))
light("Rim", 'AREA', (0.5, 3.5, 3.2), 200, 3.0, (0.9, 0.85, 1.0))

cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 62
cam = link_obj("Camera", cam_d, loc=(2.1, -5.0, 1.6))
look = Vector((0.12, 0, 1.22)) - Vector(cam.location)
cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam

world = scene.world or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
if bg:
    bg.inputs[0].default_value = (0.55, 0.58, 0.72, 1)
    bg.inputs[1].default_value = 0.45

scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.render.resolution_x, scene.render.resolution_y = 800, 1200
try:
    scene.view_settings.view_transform = 'Standard'
    scene.cycles.use_denoising = True
except Exception:
    pass

# GUI: show colours in the viewport
try:
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces[0].shading.type = 'MATERIAL'
except Exception:
    pass

out_png = os.environ.get("MAGE_RENDER")
out_blend = os.environ.get("MAGE_BLEND")
if out_blend:
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
if out_png:
    scene.render.filepath = out_png
    scene.cycles.device = 'CPU'
    bpy.ops.render.render(write_still=True)
print("Mage built.")
