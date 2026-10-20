"""Garment base from the posed MakeHuman body: bodice+sleeves (offset skin) + extruded flared skirt."""
import numpy as np
import bpy
import bmesh
from mathutils import Vector
import mh
import pose

NB = 13380
Z_OFF = 0.82          # lifts feet to z = 0

# landmark heights in rest/body coordinates (before Z_OFF)
Z_WAIST = 0.315
Z_NECK = 0.662


def classes(rig):
    names = rig.wb

    def wsum(pred):
        idx = [i for i, b in enumerate(names) if pred(b)]
        return rig.W[idx][:, :NB].sum(0)
    arm = wsum(lambda b: any(k in b for k in ("upperarm", "lowerarm", "shoulder01")))
    hand = wsum(lambda b: any(k in b for k in ("wrist", "metacarpal", "finger")))
    leg = wsum(lambda b: any(k in b for k in ("upperleg", "lowerleg", "foot", "toe")))
    head = wsum(lambda b: b in ("head", "neck03", "jaw", "eye.L", "eye.R") or "special0" in b)
    return arm, hand, leg, head


def select_region(rig, sleeve_cut=0.45):
    P = rig.P[:NB]
    arm, hand, leg, head = classes(rig)
    z = P[:, 2]
    sel = np.zeros(NB, bool)
    tor = (arm < 0.5) & (hand < 0.5) & (z >= Z_WAIST) & (z <= Z_NECK)
    sel |= tor
    for side in "LR":
        S = rig.head[f"upperarm01.{side}"]
        E = rig.head[f"lowerarm01.{side}"]
        d = E - S
        L2 = np.dot(d, d)
        t = ((P - S) @ d) / L2
        a = (arm >= 0.5) & (hand < 0.5) & (t < sleeve_cut)
        a &= (P[:, 0] > 0) if side == "L" else (P[:, 0] < 0)
        sel |= a & (z <= Z_NECK + 0.02)
    sel &= head < 0.5
    return sel


def faces_for(sel):
    out = []
    for fc in mh.BODY_FACES:
        vi = [t[0] for t in fc]
        if all(v < NB and sel[v] for v in vi):
            out.append(fc)
    return out


def boundary_loops(bm):
    """Return list of ordered loops (list of BMVert) for boundary edges."""
    be = [e for e in bm.edges if e.is_boundary]
    adj = {}
    for e in be:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen = set()
    loops = []
    for v in adj:
        if v in seen:
            continue
        loop = [v]
        seen.add(v)
        cur = v
        prev = None
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            loop.append(cur)
            seen.add(cur)
        loops.append(loop)
    return loops


def build_base(rig, Ppose, ease=0.011, sleeve_cut=0.45):
    """Returns bmesh of bodice+sleeves offset along normals, plus loop info."""
    sel = select_region(rig, sleeve_cut)
    faces = faces_for(sel)
    used = sorted({t[0] for fc in faces for t in fc})
    remap = {v: i for i, v in enumerate(used)}
    bm = bmesh.new()
    pts = Ppose[:NB]
    bv = [bm.verts.new(pts[v]) for v in used]
    for fc in faces:
        try:
            bm.faces.new([bv[remap[t[0]]] for t in fc])
        except ValueError:
            pass
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    # offset along normals
    for v in bm.verts:
        v.co += v.normal * ease
    return bm, used, remap


# --------------------------------------------------------------------------- skirt
def subdivide_bm(bm, levels=1):
    for _ in range(levels):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True, use_smooth_even=False,
                                  smooth=1.0)
    bm.normal_update()
    return bm


def ordered_loop(loop):
    """loop: list of BMVert (chain ordered). Return array of positions ordered CCW by angle about its centre."""
    pts = np.array([v.co[:] for v in loop])
    c = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
    order = np.argsort(ang)
    return pts[order], [loop[i] for i in order], c


def body_outline(P, center_xy, z, band=0.05, nbin=96, base=None):
    """max radial extent of body verts around centre in a z band, per angular bin (smoothed)"""
    m = np.abs(P[:, 2] - z) < band
    q = P[m][:, :2] - center_xy
    r = np.hypot(q[:, 0], q[:, 1])
    ang = np.arctan2(q[:, 1], q[:, 0])
    bins = ((ang + np.pi) / (2 * np.pi) * nbin).astype(int) % nbin
    out = np.zeros(nbin)
    for bi, ri in zip(bins, r):
        if ri > out[bi]:
            out[bi] = ri
    # smooth (circular max-filter then average)
    k = 4
    sm = np.array([out[(np.arange(nbin) + d) % nbin] for d in range(-k, k + 1)]).max(axis=0)
    sm = (sm + np.roll(sm, 1) + np.roll(sm, -1)) / 3
    return sm


def build_skirt(waist_pts, rows=120, z_hem=0.02, hem_a=0.66, hem_b=0.60, hem_shift_y=0.10,
                folds=13, fold_amp=0.12, seed=0.0, gather=1.0, body_pts=None, clearance=0.04):
    """waist_pts ordered CCW (n,3). Returns verts (rows+1, n, 3), faces list, uv."""
    n = len(waist_pts)
    c0 = waist_pts.mean(axis=0)
    off = waist_pts - c0
    th = np.arctan2(off[:, 1], off[:, 0])
    z_w = waist_pts[:, 2].mean()
    verts = np.zeros((rows + 1, n, 3))
    rng = np.random.RandomState(7)
    ph = rng.uniform(0, 6.28, 4)
    for k in range(rows + 1):
        t = k / rows
        w = t ** 0.85
        z = z_w + (z_hem - z_w) * t
        center = c0 + np.array([0.0, hem_shift_y * t ** 1.5, 0.0])
        hem = np.stack([hem_a * np.cos(th), hem_b * np.sin(th)], axis=1)
        ring_xy = (1 - w) * (waist_pts[:, :2] - c0[:2]) + w * hem
        a = fold_amp * gather * (t ** 1.1)
        tw = th + 0.55 * t + 0.25 * np.sin(3 * t + ph[0])
        mod = (np.sin(folds * tw + 2.2 * np.sin(2.1 * t + ph[1])) +
               0.55 * np.sin(2.7 * folds * tw + 3 * t + ph[2]) +
               0.30 * np.sin(5.1 * folds * tw + ph[3] + 4 * t))
        r = 1 + a * mod
        ring_xy = ring_xy * r[:, None]
        if body_pts is not None and k > 0:
            ol = body_outline(body_pts, center[:2], z)
            ang = np.arctan2(ring_xy[:, 1], ring_xy[:, 0])
            bi = ((ang + np.pi) / (2 * np.pi) * len(ol)).astype(int) % len(ol)
            need = ol[bi] + clearance * min(1.0, k / 4.0)
            rad = np.hypot(ring_xy[:, 0], ring_xy[:, 1])
            sc = np.maximum(1.0, need / np.maximum(rad, 1e-6))
            ring_xy = ring_xy * sc[:, None]
        verts[k, :, 0] = center[0] + ring_xy[:, 0]
        verts[k, :, 1] = center[1] + ring_xy[:, 1]
        verts[k, :, 2] = z
    faces = []
    for k in range(rows):
        for i in range(n):
            j = (i + 1) % n
            faces.append((k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i))
    uv = np.zeros((rows + 1, n, 2))
    u = np.linspace(0, 1, n, endpoint=False)
    for k in range(rows + 1):
        uv[k, :, 0] = u
        uv[k, :, 1] = 1.0 - k / rows
    return verts.reshape(-1, 3), faces, uv


def bm_to_object(bm, name, collection=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


# --------------------------------------------------------------------------- sleeves (extruded along the arm)
def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def polyline_frames(path, n):
    """path (m,3) -> n rings: centers, tangents, u, v (parallel transport)"""
    seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    s = np.linspace(0, cum[-1], n)
    C = np.stack([np.interp(s, cum, path[:, i]) for i in range(3)], axis=1)
    # smooth the path (moving average) for smooth tangents
    k = 5
    Cs = C.copy()
    for i in range(3):
        pad = np.pad(C[:, i], k, mode='edge')
        Cs[:, i] = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode='valid')
    Cs[0] = C[0]
    T = np.gradient(Cs, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    u = np.zeros_like(T)
    v = np.zeros_like(T)
    ref = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0, 0])
    u0 = np.cross(T[0], ref)
    u0 /= np.linalg.norm(u0)
    u[0] = u0
    v[0] = np.cross(T[0], u0)
    for i in range(1, n):
        # rotate previous frame to new tangent
        a = np.cross(T[i - 1], T[i])
        sn = np.linalg.norm(a)
        if sn < 1e-8:
            u[i], v[i] = u[i - 1], v[i - 1]
        else:
            ax = a / sn
            ang = np.arctan2(sn, np.dot(T[i - 1], T[i]))
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            Rm = np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K
            u[i] = Rm @ u[i - 1]
            v[i] = Rm @ v[i - 1]
    return Cs, T, u, v, s


def build_sleeve(loop_pts, path, rows=90, bell=0.16, bell_start=0.45, flare_pow=1.8, folds=7, fold_amp=0.06,
                 overhang=0.0, tight_end=False):
    """loop_pts: start ring positions (unordered), path: polyline through centreline (starts at loop centre).
    Returns verts (rows+1, n, 3), faces, uv, and order index."""
    n = len(loop_pts)
    c0 = loop_pts.mean(axis=0)
    path = np.array(path, float)
    path[0] = c0
    C, T, U, Vv, s = polyline_frames(path, rows + 1)
    # order loop by angle in the (U,V) plane of ring 0
    off0 = loop_pts - c0
    ang0 = np.arctan2(off0 @ Vv[0], off0 @ U[0])
    order = np.argsort(ang0)
    off0 = off0[order]
    ang0 = ang0[order]
    r0 = np.linalg.norm(off0, axis=1)
    verts = np.zeros((rows + 1, n, 3))
    rng = np.random.RandomState(3)
    ph = rng.uniform(0, 6.28, 3)
    for k in range(rows + 1):
        t = k / rows
        w = smoothstep(bell_start, 1.0, t) ** flare_pow
        R = r0 * (1 - w) + (bell + 0.0) * w
        a = fold_amp * smoothstep(bell_start, 1.0, t)
        R = R * (1 + a * (np.sin(folds * ang0 + 3 * t + ph[0]) + 0.5 * np.sin(2.3 * folds * ang0 + ph[1] - 2 * t)))
        ca, sa = np.cos(ang0), np.sin(ang0)
        verts[k] = C[k] + (U[k][None, :] * ca[:, None] + Vv[k][None, :] * sa[:, None]) * R[:, None]
    faces = []
    for k in range(rows):
        for i in range(n):
            j = (i + 1) % n
            faces.append((k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i))
    uv = np.zeros((rows + 1, n, 2))
    uu = np.linspace(0, 1, n, endpoint=False)
    for k in range(rows + 1):
        uv[k, :, 0] = uu
        uv[k, :, 1] = 1.0 - k / rows
    return verts.reshape(-1, 3), faces, uv, order


# --------------------------------------------------------------------------- hood (worn down, draped on the back)
def build_hood_base(neck_back_pts, up=(0, 0, 1), out_dir=(0, 1, 0), length=0.52, rows=22, taper=0.15,
                    widen=1.6):
    """A big hood/cape panel attached along the back half of the neckline, standing up and
    widening before arcing back and down over the shoulders -- a cloth sim then lets it settle
    and drape down the back, colliding with the body, instead of collapsing to a point."""
    n = len(neck_back_pts)
    c = neck_back_pts.mean(axis=0)
    up = np.asarray(up, float); up /= np.linalg.norm(up)
    out_dir = np.asarray(out_dir, float); out_dir /= np.linalg.norm(out_dir)
    side = np.cross(up, out_dir)
    verts = [neck_back_pts.copy()]
    for k in range(1, rows + 1):
        t = k / rows
        # widen for the first half (shoulders), then taper only a little toward the tip
        grow = 1.0 + (widen - 1.0) * np.sin(min(t, 0.6) / 0.6 * np.pi / 2)
        shrink = grow * (1.0 - taper * max(0.0, t - 0.6) / 0.4)
        ring = c + (neck_back_pts - c) * shrink
        # path: rises, arcs backward/out, then curls down -- gives the sim a believable start pose
        rise = np.sin(min(t, 0.5) / 0.5 * np.pi / 2)
        fall = max(0.0, t - 0.5) / 0.5
        ring = (ring + up[None, :] * (length * 0.55 * rise - length * 0.35 * fall)
                + out_dir[None, :] * (length * 0.75 * t))
        verts.append(ring)
    V = np.array(verts)
    faces = []
    for k in range(rows):
        for i in range(n - 1):
            faces.append((k * n + i, k * n + i + 1, (k + 1) * n + i + 1, (k + 1) * n + i))
    uv = np.zeros((rows + 1, n, 2))
    uu = np.linspace(0, 1, n)
    for k in range(rows + 1):
        uv[k, :, 0] = uu
        uv[k, :, 1] = k / rows
    return V.reshape(-1, 3), faces, uv, n
