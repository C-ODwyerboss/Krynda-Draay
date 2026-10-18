from robe_common import *
OUT = "/home/claude/work/out"
NAME = os.environ.get("NAME", "skirt_sim")
reset_scene()
V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)
Pp0 = Pp.copy(); Pp0[:, 2] -= garment.Z_OFF
base_bm, used, remap = garment.build_base(rig, Pp0)
for v in base_bm.verts: v.co.z += garment.Z_OFF
garment.subdivide_bm(base_bm, int(os.environ.get("SUB", "1")))
bo = garment.bm_to_object(base_bm, "Bodice")
P = np.load(f"{OUT}/{NAME}_P.npy"); F = np.load(f"{OUT}/skirt_faces.npy")
sk = mh.mesh_from_arrays("Skirt", P, F.tolist())
sk.modifiers.new("Sub", 'SUBSURF').levels = 1
for o, col in ((bo, (0.2,0.1,0.45,1)), (sk, (0.38,0.22,0.65,1)), (body, (0.55,0.3,0.25,1))):
    m, nt, out = new_material("clay_"+o.name); b = N(nt, 'ShaderNodeBsdfPrincipled'); L(nt, b.outputs[0], out.inputs[0])
    setin(b, "Base Color", col); setin(b, "Roughness", 0.55); o.data.materials.append(m)
body.hide_render = True
make_floor()
set_world((0.25,0.25,0.28), 1.0); setup_cycles(int(os.environ.get("SAMPLES","10")), 480, 720)
add_area("Key", (1.5, -3, 3), (0, 0, 1.0), 400, 2.5); add_area("Fill", (-2.5, -2, 1.5), (0, 0, 1.0), 150, 3)
cams = {"front": add_camera("F", (0, -4.2, 1.0), (0, 0, 1.0), lens=50), "three": add_camera("T", (2.8, -3.4, 1.4), (0, 0, 1.0), lens=50),
        "side": add_camera("S", (4.2, 0, 1.0), (0, 0, 1.0), lens=50), "back": add_camera("B", (-2, 3.8, 1.2), (0, 0, 1.0), lens=50)}
views = os.environ.get("VIEWS", "front,three").split(",")
from PIL import Image
ims = []
for v in views:
    render_to(f"{OUT}/{NAME}_{v}.png", cams[v]); ims.append(Image.open(f"{OUT}/{NAME}_{v}.png"))
c = Image.new('RGB', (480 * len(ims), 720))
for i, im in enumerate(ims): c.paste(im, (480 * i, 0))
c.save(f"{OUT}/{NAME}_sheet.png")
