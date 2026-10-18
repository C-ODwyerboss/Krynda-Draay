import sys, os, time
sys.path.insert(0, "/home/claude/work")
import numpy as np, bpy, bmesh
import mh, shape, pose, posing, garment
from common import *


def posed_body_points():
    V = mh.build_shape(macro=shape.MACRO, details=shape.face_details())
    rig = pose.Rig(V)
    R, P = posing.make_pose(rig)
    posing.hand_pose(rig, R, "L", hand_dir=(-0.3, -0.2, 1.0), palm_normal=(0.2, 1.0, 0.0))
    posing.hand_pose(rig, R, "R", hand_dir=(0.5, -0.2, 0.7), palm_normal=(-0.2, 1.0, 0.0))
    Pp = rig.pose(R)
    return V, rig, R, Pp


def make_floor(size=6.0):
    return mh.mesh_from_arrays("Floor", [(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)], [[0, 1, 2, 3]])


def cloth_setup(ob, pin_group="pin", quality=8, mass=0.35, tension=25, compression=25, shear=15, bending=1.2,
                damping=6, air=1.0, self_coll=True, dist=0.006, self_dist=0.006, frames=60):
    m = ob.modifiers.new("Cloth", 'CLOTH')
    s = m.settings
    s.quality = quality
    s.mass = mass
    s.tension_stiffness = tension
    s.compression_stiffness = compression
    s.shear_stiffness = shear
    s.bending_stiffness = bending
    s.tension_damping = damping
    s.compression_damping = damping
    s.shear_damping = damping
    s.bending_damping = 0.5
    s.air_damping = air
    s.vertex_group_mass = pin_group
    s.pin_stiffness = 1.0
    c = m.collision_settings
    c.use_collision = True
    c.collision_quality = 3
    c.distance_min = dist
    c.impulse_clamp = 0.0
    c.use_self_collision = self_coll
    c.self_distance_min = self_dist
    c.self_friction = 5
    c.self_impulse_clamp = 0.0
    m.point_cache.frame_start = 1
    m.point_cache.frame_end = frames
    return m


def make_collider(ob, thickness=0.004, friction=8):
    ob.modifiers.new("Collision", 'COLLISION')
    ob.collision.thickness_outer = thickness
    ob.collision.thickness_inner = 0.02
    ob.collision.cloth_friction = friction
    ob.collision.damping = 0.3
    ob.collision.use_culling = False
    ob.collision.use_normal = False


def add_wind(strength=60, direction=(1, 0, 0), noise=1.5, loc=(-2, 0, 0.8)):
    bpy.ops.object.effector_add(type='WIND', location=loc)
    e = bpy.context.active_object
    e.name = "Wind"
    d = Vector(direction)
    # wind force points along the effector's local +Z
    e.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    e.field.strength = strength
    e.field.noise = noise
    e.field.flow = 0.0
    e.field.shape = 'PLANE'
    e.field.use_max_distance = False
    return e


def evaluated_points(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    ev.to_mesh_clear()
    return a.reshape(-1, 3)


def run_sim(ob, frames, log=print):
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, frames
    t0 = time.time()
    sc.frame_set(1)
    for f in range(2, frames + 1):
        sc.frame_set(f)
        if f % 5 == 0 or f == frames:
            p = evaluated_points(ob)
            log(f"frame {f}/{frames}  {time.time()-t0:.0f}s  zmin {p[:,2].min():.3f} xr [{p[:,0].min():.2f},{p[:,0].max():.2f}] nan={np.isnan(p).any()}")
    return evaluated_points(ob)
