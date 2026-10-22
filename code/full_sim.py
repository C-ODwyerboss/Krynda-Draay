"""Full garment build: bodice (torso only, no sleeves) + build_sleeve bell sleeves +
pleated skirt + hood-down panel, all cloth-simulated together on the posed body."""
from robe_common import *

OUT = "/home/claude/work/out"
ROWS_SK = int(os.environ.get("ROWS_SK", "80"))
ROWS_SL = int(os.environ.get("ROWS_SL", "40"))
ROWS_HD = int(os.environ.get("ROWS_HD", "22"))
FR = int(os.environ.get("FRAMES", "70"))
WIND = float(os.environ.get("WIND", "9"))

reset_scene()
V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)

Pp0 = Pp.copy()
Pp0[:, 2] -= garment.Z_OFF

# torso bodice, now extended further over the shoulder/upper-arm (sleeve_cut raised from 0.06
# to 0.22) so it meets the separately-built bell sleeve instead of leaving a bare-shoulder gap
SLEEVE_CUT = float(os.environ.get("SLEEVE_CUT", "0.22"))
base_bm, used, remap = garment.build_base(rig, Pp0, sleeve_cut=SLEEVE_CUT)
for v in base_bm.verts:
    v.co.z += garment.Z_OFF
garment.subdivide_bm(base_bm, 1)
loops = garment.boundary_loops(base_bm)
loops.sort(key=lambda l: -len(l))
waist = sorted([l for l in loops if np.mean([v.co.z for v in l]) < 1.3], key=lambda l: -len(l))[0]
neck = sorted([l for l in loops if np.mean([v.co.z for v in l]) > 1.4], key=lambda l: -len(l))[0]
# arm holes: the remaining two boundary loops
others = [l for l in loops if l is not waist and l is not neck]
armholes = sorted(others, key=lambda l: -len(l))[:2]
# identify L/R by x sign of centroid
armholes.sort(key=lambda l: np.mean([v.co.x for v in l]))
arm_R, arm_L = armholes[0], armholes[1]   # robe's own R is -x (viewer's left is +x... keep consistent w/ earlier: L side x>0)
print("waist", len(waist), "neck", len(neck), "armL", len(arm_L), "armR", len(arm_R))

wp, wv, wc = garment.ordered_loop(waist)
npnts, nv, nc = garment.ordered_loop(neck)

bodice = garment.bm_to_object(base_bm, "Bodice")

# --- skirt from waist
legs_mask = Pp[:, 2] < 1.15
verts, faces, uv = garment.build_skirt(wp, rows=ROWS_SK, hem_a=0.50, hem_b=0.46, hem_shift_y=0.08,
                                       folds=11, fold_amp=0.08, body_pts=Pp[:13380][legs_mask[:13380]],
                                       clearance=0.045)
skirt = mh.mesh_from_arrays("Skirt", verts, faces, uv.reshape(-1, 2), [[k * len(wp) + i, k * len(wp) + (i + 1) % len(wp),
                            (k + 1) * len(wp) + (i + 1) % len(wp), (k + 1) * len(wp) + i] for k in range(ROWS_SK) for i in range(len(wp))])

# --- sleeves: path from armhole centre down along the (posed) arm to a bell end
sleeve_objs = []
for side, loop, sign in (("L", arm_L, 1), ("R", arm_R, -1)):
    lp = np.array([v.co[:] for v in loop])
    S = rig.head[f"upperarm01.{side}"].copy(); S[2] += garment.Z_OFF
    E = rig.head[f"lowerarm01.{side}"].copy(); E[2] += garment.Z_OFF
    W = rig.head[f"wrist.{side}"].copy(); W[2] += garment.Z_OFF
    tip = W + (W - E) * 0.55
    # the armhole ring (lp) now sits SLEEVE_CUT of the way down the upper arm (not at the
    # shoulder joint S any more), so starting the path at lp.mean then back at S would fold the
    # path backward on itself -- skip S and go straight from the armhole to the elbow
    path = np.array([lp.mean(axis=0), E, W, tip])
    sv, sf, suv, order = garment.build_sleeve(lp, path, rows=ROWS_SL, bell=0.15, bell_start=0.46,
                                              flare_pow=1.7, folds=6, fold_amp=0.025)
    sl = mh.mesh_from_arrays(f"Sleeve{side}", sv, sf, suv.reshape(-1, 2),
                              [[k * len(lp) + i, k * len(lp) + (i + 1) % len(lp), (k + 1) * len(lp) + (i + 1) % len(lp),
                                (k + 1) * len(lp) + i] for k in range(ROWS_SL) for i in range(len(lp))])
    sleeve_objs.append(sl)

# --- hood: panel from the back half of the neck loop
back_mask = (npnts - nc) @ np.array([0, 1, 0]) > 0    # +Y = back (person faces -Y toward the camera)
if back_mask.sum() < 3:
    back_mask = ~back_mask
back_pts = npnts[back_mask]
# reorder back_pts along the loop (they're already a contiguous arc of the ordered loop ideally)
hv, hf, huv, hn = garment.build_hood_base(back_pts, up=(0, 0, 1), out_dir=(0, 1, 0), length=0.52, rows=ROWS_HD)
hood = mh.mesh_from_arrays("Hood", hv, hf, huv.reshape(-1, 2), None)

# --- pin groups & cloth
def pin_vg(ob, n_pin, extra=None, w=1.0):
    vg = ob.vertex_groups.new(name="pin")
    vg.add(list(range(n_pin)), w, 'REPLACE')
    if extra:
        vg.add(extra, w * 0.5, 'REPLACE')
    return vg


pin_vg(skirt, len(wp))
for sl, loop in zip(sleeve_objs, (arm_L, arm_R)):
    pin_vg(sl, len(loop))
pin_vg(hood, hn)

make_collider(body)
floor = make_floor()
make_collider(floor, 0.004, 3)

for ob, bend, sd in ((skirt, float(os.environ.get("BEND_SK", "6")), 0.008),
                     (sleeve_objs[0], 10, 0.006), (sleeve_objs[1], 10, 0.006),
                     (hood, 8, 0.006)):
    cloth_setup(ob, frames=FR, quality=7, mass=0.28, tension=35, compression=35, shear=22,
               bending=bend, damping=8, dist=0.01, self_dist=sd, self_coll=True)

bodice.hide_render = True  # keep as rigid base reference; skirt/sleeves/hood are simmed
body.hide_render = True

wind_obj = add_wind(WIND, (1, 0.15, 0)) if WIND > 0 else None

t = time.time()
sc = bpy.context.scene
sc.frame_start, sc.frame_end = 1, FR
SETTLE = int(FR * 0.55)
for f in range(1, FR + 1):
    if wind_obj is not None and f == SETTLE:
        wind_obj.field.strength = 0.0
    sc.frame_set(f)
    if f % 10 == 0 or f == FR:
        print(f"frame {f}/{FR} {time.time()-t:.0f}s")

Psk = evaluated_points(skirt)
Psl = [evaluated_points(o) for o in sleeve_objs]
Phd = evaluated_points(hood)
np.savez(f"{OUT}/full_sim.npz", skirt=Psk, skirt_faces=np.array(faces, dtype=object if False else object),
         sleeveL=Psl[0], sleeveR=Psl[1], hood=Phd,
         bodice=np.array([v.co[:] for v in base_bm.verts]))
import pickle
with open(f"{OUT}/full_sim_topo.pkl", "wb") as fh:
    pickle.dump(dict(skirt_faces=faces, sleeve_faces=sf, sleeve_n=len(arm_L), hood_faces=hf, hood_n=hn,
                     bodice_faces=[tuple(t[0] for t in fc) for fc in garment.faces_for(garment.select_region(rig, SLEEVE_CUT))],
                     bodice_used=used), fh)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/full_sim.blend")
print("DONE")
