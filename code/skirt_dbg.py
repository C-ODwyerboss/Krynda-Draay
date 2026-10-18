from robe_common import *
ROWS=int(os.environ.get("ROWS","36")); FR=int(os.environ.get("FR","14")); SD=float(os.environ.get("SD","0.01"))
MODE = os.environ.get("MODE","none")
reset_scene()
V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)
Pp0 = Pp.copy(); Pp0[:, 2] -= garment.Z_OFF
base_bm, used, remap = garment.build_base(rig, Pp0)
for v in base_bm.verts: v.co.z += garment.Z_OFF
garment.subdivide_bm(base_bm, 1)
loops = garment.boundary_loops(base_bm)
waist = sorted([l for l in loops if np.mean([v.co.z for v in l]) < 1.3], key=lambda l: -len(l))[0]
wp, wv, c = garment.ordered_loop(waist)
legs_mask = Pp[:, 2] < 1.15
verts, faces, uv = garment.build_skirt(wp, rows=ROWS, hem_a=0.50, hem_b=0.46, hem_shift_y=0.08, folds=11, fold_amp=0.08, body_pts=Pp[:13380][legs_mask[:13380]], clearance=0.045)
sk = mh.mesh_from_arrays("Skirt", verts, faces)
n = len(wp)
vg = sk.vertex_groups.new(name="pin"); vg.add(list(range(0, n)), 1.0, 'REPLACE'); vg.add(list(range(n, 2*n)), 0.6, 'REPLACE')
floor = make_floor()
if "floor" in MODE: make_collider(floor, 0.004, 3)
if "body" in MODE: make_collider(body)
m = cloth_setup(sk, frames=FR, quality=8, mass=0.3, tension=40, compression=40, shear=25, bending=6, damping=8, dist=0.01, self_dist=SD, self_coll=("self" in MODE))
m.collision_settings.use_collision = ("floor" in MODE or "body" in MODE)
print("MODE", MODE, "start z range", verts[:,2].min(), verts[:,2].max())
P = run_sim(sk, FR)
