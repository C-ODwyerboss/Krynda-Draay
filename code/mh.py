"""
MakeHuman (CC0) base mesh loader for Blender / bpy.
 - parses base.obj (all 19158 verts incl. helper geometry, body group faces + UVs)
 - applies macro targets (gender/age/muscle/weight/height/ethnicity) and detail targets
 - converts MH space (x right, y up, z forward, 1 unit = 10 cm)  ->  Blender (x, -z, y) metres
"""
import os
import json
import numpy as np
import bpy
import bmesh
from mathutils import Vector

MH = "/home/claude/assets/mh/makehuman/data"
CACHE = "/home/claude/work/_cache"
os.makedirs(CACHE, exist_ok=True)


# --------------------------------------------------------------------------- base.obj
def load_base():
    f = os.path.join(CACHE, "base.npz")
    if os.path.exists(f):
        z = np.load(f, allow_pickle=True)
        return z["V"], z["VT"], z["faces"].tolist(), json.loads(str(z["groups"]))
    V, VT, groups, cur = [], [], {}, None
    body = []
    for ln in open(os.path.join(MH, "3dobjs/base.obj")):
        if ln.startswith("v "):
            V.append([float(x) for x in ln.split()[1:4]])
        elif ln.startswith("vt "):
            VT.append([float(x) for x in ln.split()[1:3]])
        elif ln.startswith("g "):
            cur = ln.split()[1]
            groups.setdefault(cur, [])
        elif ln.startswith("f "):
            fc = [tuple(int(x) - 1 if x else -1 for x in t.split("/")[:2]) for t in ln.split()[1:]]
            groups[cur].append(fc)
    V = np.array(V)
    VT = np.array(VT)
    faces = groups["body"]
    gj = {k: v for k, v in groups.items()}
    np.savez(f, V=V, VT=VT, faces=np.array(faces, dtype=np.int64), groups=json.dumps(gj))
    return V, VT, faces, gj


BASE_V, BASE_VT, BODY_FACES, GROUPS = load_base()


def group_verts(name):
    return sorted({t[0] for fc in GROUPS[name] for t in fc})


# --------------------------------------------------------------------------- targets
_tcache = {}


def load_target(stem):
    """stem relative to targets/, without .target"""
    if stem in _tcache:
        return _tcache[stem]
    p = os.path.join(MH, "targets", stem + ".target")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    idx, d = [], []
    for ln in open(p):
        if ln.startswith("#") or not ln.strip():
            continue
        s = ln.split()
        idx.append(int(s[0]))
        d.append([float(s[1]), float(s[2]), float(s[3])])
    r = (np.array(idx, dtype=np.int64), np.array(d, dtype=np.float64).reshape(-1, 3))
    _tcache[stem] = r
    return r


def tri(v, lo_name, mid_name, hi_name):
    lo = max(0.0, 1 - 2 * v)
    hi = max(0.0, 2 * v - 1)
    return {lo_name: lo, mid_name: 1 - lo - hi, hi_name: hi}


def macro_weights(gender=0.0, age_years=40.0, muscle=0.5, weight=0.5, height=0.5,
                  african=0.0, asian=0.0, caucasian=1.0):
    """returns {target stem: weight}"""
    if age_years < 25:
        a = (age_years - 1) / 48.0
    else:
        a = (age_years - 25) / 130.0 + 0.5
    if a < 0.5:
        old = 0.0
        baby = max(0.0, 1 - a * 5.333)
        young = max(0.0, (a - 0.1875) * 3.2)
        child = max(0.0, min(1.0, 5.333 * a) - young)
    else:
        child = baby = 0.0
        old = max(0.0, a * 2 - 1)
        young = 1 - old
    ages = {"baby": baby, "child": child, "young": young, "old": old}
    genders = {"female": 1 - gender, "male": gender}
    mus = tri(muscle, "minmuscle", "averagemuscle", "maxmuscle")
    wei = tri(weight, "minweight", "averageweight", "maxweight")
    hei = {"minheight": max(0.0, 1 - 2 * height), "maxheight": max(0.0, 2 * height - 1)}
    races = {"african": african, "asian": asian, "caucasian": caucasian}
    out = {}
    for g, gv in genders.items():
        for an, av in ages.items():
            if gv * av <= 0:
                continue
            for mn, mv in mus.items():
                for wn, wv in wei.items():
                    w = gv * av * mv * wv
                    if w > 1e-6:
                        out[f"macrodetails/universal-{g}-{an}-{mn}-{wn}"] = w
                        for hn, hv in hei.items():
                            if hv > 1e-6:
                                out[f"macrodetails/height/{g}-{an}-{mn}-{wn}-{hn}"] = w * hv
            for rn, rv in races.items():
                if rv > 0:
                    out[f"macrodetails/{rn}-{g}-{an}"] = gv * av * rv
    return out


def build_shape(macro=None, details=None):
    V = BASE_V.copy()
    allw = {}
    if macro is not None:
        allw.update(macro_weights(**macro))
    if details:
        for k, w in details.items():
            allw[k] = allw.get(k, 0.0) + w
    missing = []
    for stem, w in allw.items():
        try:
            idx, d = load_target(stem)
        except FileNotFoundError:
            missing.append(stem)
            continue
        V[idx] += d * w
    if missing:
        print("[mh] missing targets:", missing[:10])
    return V


# --------------------------------------------------------------------------- coordinates
def to_bl(V, scale=0.1):
    """MH (x, y up, z fwd) -> Blender metres (x, -z, y)"""
    V = np.asarray(V)
    out = np.empty_like(V)
    out[..., 0] = V[..., 0] * scale
    out[..., 1] = -V[..., 2] * scale
    out[..., 2] = V[..., 1] * scale
    return out


def make_mesh(name, V, faces=None, uv=True, collection=None, bl=False):
    """Create body mesh object from MH-space V (all verts) or Blender-space (bl=True). Only body faces kept."""
    faces = faces if faces is not None else BODY_FACES
    P = np.asarray(V) if bl else to_bl(V)
    nb = 13380
    me = bpy.data.meshes.new(name)
    me.vertices.add(nb)
    me.vertices.foreach_set("co", P[:nb].ravel())
    nf = len(faces)
    me.loops.add(nf * 4)
    me.polygons.add(nf)
    me.polygons.foreach_set("loop_start", np.arange(nf) * 4)
    me.polygons.foreach_set("loop_total", np.full(nf, 4))
    vi = np.array([[t[0] for t in fc] for fc in faces], dtype=np.int64)
    me.loops.foreach_set("vertex_index", vi.ravel())
    me.update(calc_edges=True)
    if uv:
        uvl = me.uv_layers.new(name="UVMap")
        ti = np.array([[t[1] for t in fc] for fc in faces], dtype=np.int64).ravel()
        uvl.data.foreach_set("uv", BASE_VT[ti].ravel())
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


# --------------------------------------------------------------------------- proxies (mhclo)
def load_mhclo(path):
    d = {"verts": [], "scale": {}}
    mode = None
    for ln in open(path):
        s = ln.split()
        if not s or s[0].startswith("#"):
            continue
        if s[0] in ("x_scale", "y_scale", "z_scale"):
            d["scale"][s[0][0]] = (int(s[1]), int(s[2]), float(s[3]))
        elif s[0] == "obj_file":
            d["obj"] = s[1]
        elif s[0] == "verts":
            mode = "verts"
        elif mode == "verts":
            if len(s) == 9:
                d["verts"].append((int(s[0]), int(s[1]), int(s[2]), float(s[3]), float(s[4]), float(s[5]),
                                   float(s[6]), float(s[7]), float(s[8])))
            elif len(s) == 1:
                d["verts"].append((int(s[0]),))
    return d


def load_obj_simple(path):
    V, F, VT, FT = [], [], [], []
    for ln in open(path):
        if ln.startswith("v "):
            V.append([float(x) for x in ln.split()[1:4]])
        elif ln.startswith("vt "):
            VT.append([float(x) for x in ln.split()[1:3]])
        elif ln.startswith("f "):
            F.append([int(t.split("/")[0]) - 1 for t in ln.split()[1:]])
            FT.append([int(t.split("/")[1]) - 1 if "/" in t and t.split("/")[1] else -1 for t in ln.split()[1:]])
    return np.array(V), F, np.array(VT), FT


def fit_proxy(mhclo, V):
    """Return fitted proxy vertices in MH space for base-vertex array V."""
    sc = {}
    for ax, i in (("x", 0), ("y", 1), ("z", 2)):
        a, b, den = mhclo["scale"][ax]
        sc[i] = abs(V[a, i] - V[b, i]) / den
    out = []
    for t in mhclo["verts"]:
        if len(t) == 1:
            out.append(V[t[0]])
            continue
        a, b, c, wa, wb, wc, ox, oy, oz = t
        p = V[a] * wa + V[b] * wb + V[c] * wc + np.array([ox * sc[0], oy * sc[1], oz * sc[2]])
        out.append(p)
    return np.array(out)


def mesh_from_arrays(name, P, F, VT=None, FT=None, smooth=True, collection=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(P))
    me.vertices.foreach_set("co", np.asarray(P, dtype=np.float64).ravel())
    nl = sum(len(f) for f in F)
    me.loops.add(nl)
    me.polygons.add(len(F))
    starts, tots, flat = [], [], []
    s = 0
    for f in F:
        starts.append(s)
        tots.append(len(f))
        flat.extend(f)
        s += len(f)
    me.polygons.foreach_set("loop_start", starts)
    me.polygons.foreach_set("loop_total", tots)
    me.loops.foreach_set("vertex_index", flat)
    me.update(calc_edges=True)
    if VT is not None and FT is not None:
        uvl = me.uv_layers.new(name="UVMap")
        ft = [i for f in FT for i in f]
        uvl.data.foreach_set("uv", VT[ft].ravel())
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob


def bl_vec(V, i):
    p = to_bl(V[i])
    return Vector((float(p[0]), float(p[1]), float(p[2])))
