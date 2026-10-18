from robe_common import *
OUT = "/home/claude/work/out"
ROWS = int(os.environ.get("ROWS", "90")); FR = int(os.environ.get("FRAMES", "60")); WIND = float(os.environ.get("WIND", "0"))
SUB = int(os.environ.get("SUB", "1"))
reset_scene()
V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)
Pp0 = Pp.copy(); Pp0[:, 2] -= garment.Z_OFF
base_bm, used, remap = garment.build_base(rig, Pp0)
for v in base_bm.verts: v.co.z += garment.Z_OFF
garment.subdivide_bm(base_bm, SUB)
loops = garment.boundary_loops(base_bm)
waist = sorted([l for l in loops if np.mean([v.co.z for v in l]) < 1.3], key=lambda l: -len(l))[0]
wp, wv, c = garment.ordered_loop(waist)
print("waist verts", len(wp))
legs_mask = Pp[:, 2] < 1.15
verts, faces, uv = garment.build_skirt(wp, rows=ROWS, hem_a=0.50, hem_b=0.46, hem_shift_y=0.08, folds=11, fold_amp=0.08, body_pts=Pp[:13380][legs_mask[:13380]], clearance=0.045)
sk = mh.mesh_from_arrays("Skirt", verts, faces)
n = len(wp)
vg = sk.vertex_groups.new(name="pin")
vg.add(list(range(0, n)), 1.0, 'REPLACE')
vg.add(list(range(n, 2 * n)), 0.6, 'REPLACE')
floor = make_floor()
make_collider(body); make_collider(floor, 0.004, 3)
cloth_setup(sk, frames=FR, quality=int(os.environ.get('Q','12')), mass=0.3, tension=40, compression=40, shear=25, bending=float(os.environ.get('BEND','6')), damping=8, dist=0.01, self_dist=float(os.environ.get("SD","0.004")))
if WIND > 0:
    add_wind(WIND, (1, 0.15, 0))
t = time.time()
P = run_sim(sk, FR)
print("sim done", time.time() - t)
np.save(f"{OUT}/skirt_sim_P.npy", P)
np.save(f"{OUT}/skirt_faces.npy", np.array(faces))
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/skirt_sim.blend")
