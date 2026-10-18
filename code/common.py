import math
import os
import numpy as np
import bpy
import bmesh
from mathutils import Vector, Matrix, Euler


def reset_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.lights,
                bpy.data.cameras, bpy.data.images, bpy.data.node_groups, bpy.data.armatures,
                bpy.data.hair_curves if hasattr(bpy.data, "hair_curves") else []):
        for b in list(blk):
            blk.remove(b)


def N(nt, kind, loc=None, **kw):
    n = nt.nodes.new(kind)
    if loc:
        n.location = loc
    for k, v in kw.items():
        if k == "label":
            n.label = v
        else:
            try:
                setattr(n, k, v)
            except Exception:
                pass
    return n


def L(nt, a, b):
    nt.links.new(a, b)


def setin(node, name, val):
    if name in node.inputs:
        node.inputs[name].default_value = val


def new_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != 'OUTPUT_MATERIAL':
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    return m, nt, out


def setup_cycles(samples=64, w=800, h=800, device='CPU', denoise=True, exposure=0.0):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = device
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 4
    sc.cycles.use_denoising = denoise
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = 'Filmic' if 'Filmic' in [
        i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'AgX'
    try:
        sc.view_settings.look = 'None'
    except Exception:
        pass
    sc.view_settings.exposure = exposure
    return sc


def add_area(name, loc, target, energy, size, color=(1, 1, 1), shape='SQUARE'):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.color, ld.size = energy, color, size
    ld.shape = shape
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    d = Vector(target) - Vector(loc)
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def add_camera(name, loc, target, lens=85, fstop=None, focus=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start, cd.clip_end = 0.01, 100
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus or (Vector(target) - Vector(loc)).length
    return o


def set_world(color=(0.05, 0.05, 0.06), strength=1.0):
    w = bpy.data.worlds.new("W") if bpy.context.scene.world is None else bpy.context.scene.world
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (*color, 1)
    bg.inputs[1].default_value = strength


def render_to(path, cam):
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def smooth_obj(ob):
    for p in ob.data.polygons:
        p.use_smooth = True
