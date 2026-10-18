"""The character's pose (arms gathering the robe at the chest, head turned) built on pose.Rig."""
import numpy as np
import pose
from pose import aim_chain, axis_rot, rot, solve_two_bone, arc

FEET_Z = None


def curl_fingers(rig, R, side, amounts, palm_normal_world, spread=0.0):
    """Curl fingers about hinge axis = (finger dir x palm normal)."""
    S = side
    for f, (a1, a2, a3) in amounts.items():
        for j, ang in zip((1, 2, 3), (a1, a2, a3)):
            b = f"{f}-{j}.{S}"
            if b not in rig.bones:
                continue
            rig.pose(R)
            p = rig.bones[b]["parent"]
            Rp = rig.total_R(p)
            d = Rp @ rig.dir(b)                 # current world dir with parent rotation
            hinge = np.cross(d, palm_normal_world)
            hinge /= np.linalg.norm(hinge)
            Rt = axis_rot(hinge, ang) @ Rp
            R[b] = np.linalg.inv(Rp) @ Rt @ np.eye(3)
            # R[b] expressed in rest-frame: total = Rp @ Rb  -> Rb = Rp^-1 @ Rt  where Rt = rot(hinge)@Rp
    return R


def make_pose(rig, params=None):
    P = dict(
        wristL=(0.075, -0.165, 0.455), wristR=(-0.10, -0.205, 0.395),
        poleL=(0.9, 0.0, -0.7), poleR=(-0.9, 0.1, -0.8),
        headyaw=26.0, headtilt=-7.0, headpitch=-3.0,
    )
    if params:
        P.update(params)
    R = {}
    # head turn (distribute across neck + head)
    for b, f in (("neck01", 0.25), ("neck02", 0.25), ("neck03", 0.2), ("head", 0.3)):
        R[b] = rot(P["headpitch"] * f, P["headtilt"] * f, P["headyaw"] * f)
    for side, tw in (("L", 1), ("R", -1)):
        W = np.array(P["wrist" + side])
        pole = np.array(P["pole" + side])
        S = rig.head[f"upperarm01.{side}"]
        E0 = rig.head[f"lowerarm01.{side}"]
        W0 = rig.head[f"wrist.{side}"]
        l1 = np.linalg.norm(E0 - S)
        l2 = np.linalg.norm(W0 - E0)
        E = solve_two_bone(S, W, l1, l2, pole)
        aim_chain(rig, R, f"upperarm01.{side}", E - S)
        for b in (f"upperarm02.{side}",):
            rig.pose(R)
            h = rig.world_head(b)
            aim_chain(rig, R, b, E - h)
        rig.pose(R)
        for b in (f"lowerarm01.{side}", f"lowerarm02.{side}"):
            rig.pose(R)
            h = rig.world_head(b)
            aim_chain(rig, R, b, W - h)
    return R, P


def hand_pose(rig, R, side, hand_dir, palm_normal, curl=(35, 45, 30), thumb=20):
    """Orient the hand: wrist aims toward hand_dir with palm facing palm_normal; curl fingers."""
    rig.pose(R)
    b = f"wrist.{side}"
    # metacarpal middle direction as hand axis
    ref = rig.dir(f"metacarpal2.{side}") if f"metacarpal2.{side}" in rig.bones else rig.dir(b)
    # aim wrist so hand axis -> hand_dir
    rig.pose(R)
    Rp = rig.total_R(rig.bones[b]["parent"])
    rest_axis = rig.tail[f"finger3-1.{side}"] - rig.head[b]
    rest_axis /= np.linalg.norm(rest_axis)
    # rest palm normal: perpendicular to hand plane; estimate from finger2-1/finger5-1 heads
    f2 = rig.head[f"finger2-1.{side}"]
    f5 = rig.head[f"finger5-1.{side}"]
    across = f5 - f2
    across -= rest_axis * np.dot(across, rest_axis)
    across /= np.linalg.norm(across)
    rest_n = np.cross(rest_axis, across)
    # choose sign so that rest_n points toward body centre (palm side = towards x=0)
    toward = -np.sign(rig.head[b][0]) * np.array([1, 0, 0])
    if np.dot(rest_n, toward) < 0:
        rest_n = -rest_n
    # target frame
    d = np.asarray(hand_dir, float)
    d /= np.linalg.norm(d)
    n = np.asarray(palm_normal, float)
    n = n - d * np.dot(n, d)
    n /= np.linalg.norm(n)
    A = np.column_stack([rest_axis, rest_n, np.cross(rest_axis, rest_n)])
    B = np.column_stack([d, n, np.cross(d, n)])
    Rt = B @ A.T
    R[b] = np.linalg.inv(Rp) @ Rt
    # fingers curl: hinge axis so fingers bend toward palm normal
    rig.pose(R)
    for f, k in (("finger2", 1.0), ("finger3", 1.05), ("finger4", 1.0), ("finger5", 0.85)):
        for j, ang in zip((1, 2, 3), curl):
            bn = f"{f}-{j}.{side}"
            rig.pose(R)
            Rpb = rig.total_R(rig.bones[bn]["parent"])
            dd = Rpb @ rig.dir(bn)
            hinge = np.cross(dd, n)
            hinge /= np.linalg.norm(hinge)
            # rotate dd toward n  => rotation about hinge by +ang (check sign)
            test = axis_rot(hinge, ang) @ dd
            if np.dot(test, n) < np.dot(dd, n):
                hinge = -hinge
            Rt2 = axis_rot(hinge, ang * k) @ Rpb
            R[bn] = np.linalg.inv(Rpb) @ Rt2
    # thumb (finger1)
    for j, ang in zip((1, 2, 3), (thumb, thumb * 0.8, thumb * 0.6)):
        bn = f"finger1-{j}.{side}"
        rig.pose(R)
        Rpb = rig.total_R(rig.bones[bn]["parent"])
        dd = Rpb @ rig.dir(bn)
        hinge = np.cross(dd, n)
        hinge /= np.linalg.norm(hinge)
        test = axis_rot(hinge, ang) @ dd
        if np.dot(test, n) < np.dot(dd, n):
            hinge = -hinge
        R[bn] = np.linalg.inv(Rpb) @ axis_rot(hinge, ang) @ Rpb
    return R
