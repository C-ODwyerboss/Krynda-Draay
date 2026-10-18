"""Numpy linear-blend-skinning with the MakeHuman default skeleton.
All work in Blender space (x right, y forward = -y toward camera, z up) in metres.
Rotations are specified per bone as Euler XYZ degrees in the REST-pose world axes, applied around the bone head,
then inherited down the chain (classic FK)."""
import json
import os
import numpy as np
import mh

SKEL = json.load(open(os.path.join(mh.MH, "rigs/default.mhskel")))
WGT = json.load(open(os.path.join(mh.MH, "rigs/default_weights.mhw")))["weights"]


def rot(rx=0, ry=0, rz=0):
    rx, ry, rz = np.radians([rx, ry, rz])
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def arc(a, b):
    """rotation matrix taking unit vector a onto unit vector b"""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.9999:
        # 180 deg: pick any perpendicular axis
        ax = np.cross(a, [1, 0, 0])
        if np.linalg.norm(ax) < 1e-3:
            ax = np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def axis_rot(axis, deg):
    axis = axis / np.linalg.norm(axis)
    a = np.radians(deg)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


class Rig:
    def __init__(self, V_mh):
        self.P = mh.to_bl(V_mh)             # all 19158 verts in Blender space
        self.n = len(self.P)
        self.joint = {k: self.P[v].mean(axis=0) for k, v in SKEL["joints"].items()}
        self.bones = SKEL["bones"]
        self.head = {b: self.joint[d["head"]] for b, d in self.bones.items()}
        self.tail = {b: self.joint[d["tail"]] for b, d in self.bones.items()}
        self.order = []
        seen = set()

        def visit(b):
            if b in seen:
                return
            p = self.bones[b]["parent"]
            if p:
                visit(p)
            seen.add(b)
            self.order.append(b)
        for b in self.bones:
            visit(b)
        names = [b for b in self.order if b in WGT]
        self.wb = names
        self.W = np.zeros((len(names), self.n))
        for i, b in enumerate(names):
            for vi, w in WGT[b]:
                self.W[i, vi] = w
        s = self.W.sum(axis=0)
        s[s == 0] = 1
        self.W /= s

    def dir(self, b):
        d = self.tail[b] - self.head[b]
        return d / np.linalg.norm(d)

    def pose(self, R_local, extra=None):
        """R_local: {bone: 3x3 rotation (rest-frame axes) about bone head}. Returns posed P (n,3) and the
        per-bone 4x4 transforms."""
        M = {}
        for b in self.order:
            p = self.bones[b]["parent"]
            Mp = M[p] if p else np.eye(4)
            R = R_local.get(b, np.eye(3))
            h = self.head[b]
            T = np.eye(4)
            T[:3, :3] = R
            T[:3, 3] = h - R @ h
            M[b] = Mp @ T
        out = np.zeros_like(self.P)
        for i, b in enumerate(self.wb):
            w = self.W[i]
            nz = np.nonzero(w)[0]
            if len(nz) == 0:
                continue
            Mb = M[b]
            pts = self.P[nz] @ Mb[:3, :3].T + Mb[:3, 3]
            out[nz] += pts * w[nz, None]
        self.M = M
        return out

    def world_head(self, b):
        return self.M[b][:3, :3] @ self.head[b] + self.M[b][:3, 3]

    def world_tail(self, b):
        return self.M[b][:3, :3] @ self.tail[b] + self.M[b][:3, 3]

    def total_R(self, b):
        return self.M[b][:3, :3]


def aim_chain(rig, R, bone, target_dir, twist=0.0):
    """Set R[bone] so that the posed bone points along target_dir (world)."""
    rig.pose(R)
    p = rig.bones[bone]["parent"]
    Rp = rig.total_R(p) if p else np.eye(3)
    r = rig.dir(bone)
    d = np.asarray(target_dir, dtype=float)
    d = d / np.linalg.norm(d)
    Rt = axis_rot(d, twist) @ arc(r, d)
    R[bone] = np.linalg.inv(Rp) @ Rt
    return R


def solve_two_bone(S, W, l1, l2, pole):
    S, W, pole = np.asarray(S), np.asarray(W), np.asarray(pole)
    d = W - S
    dist = min(np.linalg.norm(d), l1 + l2 - 1e-4)
    dv = d / np.linalg.norm(d)
    a = (l1 ** 2 - l2 ** 2 + dist ** 2) / (2 * dist)
    h = np.sqrt(max(l1 ** 2 - a ** 2, 0))
    perp = pole - dv * np.dot(pole, dv)
    perp /= np.linalg.norm(perp)
    return S + dv * a + perp * h
