from robe_common import *
import pickle
OUT = "/home/claude/work/out"
NAME = os.environ.get("NAME", "full_sim")
reset_scene()
d = np.load(f"{OUT}/{NAME}.npz", allow_pickle=True)
with open(f"{OUT}/{NAME}_topo.pkl", "rb") as fh:
    topo = pickle.load(fh)

body_obj_pts = None
V, rig, R, Pp = posed_body_points()
Pp[:, 2] += garment.Z_OFF
body = mh.make_mesh("Body", Pp, bl=True)
body.hide_render = True

bodice_faces_local = []
remap = {v: i for i, v in enumerate(topo["bodice_used"])}
for fc in topo["bodice_faces"]:
    bodice_faces_local.append([remap[v] for v in fc])
bodice = mh.mesh_from_arrays("Bodice", d["bodice"], bodice_faces_local)

skirt = mh.mesh_from_arrays("Skirt", d["skirt"], topo["skirt_faces"])
n = topo["sleeve_n"]
sl_faces = topo["sleeve_faces"]
sleeveL = mh.mesh_from_arrays("SleeveL", d["sleeveL"], sl_faces)
sleeveR = mh.mesh_from_arrays("SleeveR", d["sleeveR"], sl_faces)
hood = mh.mesh_from_arrays("Hood", d["hood"], topo["hood_faces"])

for o in (bodice, skirt, sleeveL, sleeveR):
    o.modifiers.new("Sub", 'SUBSURF').levels = 1
m, nt, out = new_material("robe"); b = N(nt, 'ShaderNodeBsdfPrincipled'); L(nt, b.outputs[0], out.inputs[0])
setin(b, "Base Color", (0.30, 0.14, 0.52, 1)); setin(b, "Roughness", 0.55)
m2, nt2, out2 = new_material("hood"); b2 = N(nt2, 'ShaderNodeBsdfPrincipled'); L(nt2, b2.outputs[0], out2.inputs[0])
setin(b2, "Base Color", (0.22, 0.08, 0.40, 1)); setin(b2, "Roughness", 0.55)
m3, nt3, out3 = new_material("bod"); b3 = N(nt3, 'ShaderNodeBsdfPrincipled'); L(nt3, b3.outputs[0], out3.inputs[0])
setin(b3, "Base Color", (0.62, 0.38, 0.30, 1)); setin(b3, "Roughness", 0.5)
for o in (bodice, skirt, sleeveL, sleeveR):
    o.data.materials.append(m)
hood.data.materials.append(m2)
body.data.materials.append(m3)
body.hide_render = False

make_floor()
set_world((0.25, 0.25, 0.28), 1.0)
setup_cycles(int(os.environ.get("SAMPLES", "16")), 480, 720)
add_area("Key", (1.5, -3, 3), (0, 0, 1.1), 400, 2.5)
add_area("Fill", (-2.5, -2, 1.5), (0, 0, 1.1), 150, 3)
cams = {"front": add_camera("F", (0, -4.2, 1.1), (0, 0, 1.1), lens=50),
        "three": add_camera("T", (2.8, -3.4, 1.4), (0, 0, 1.1), lens=50),
        "back": add_camera("B", (0, 4.2, 1.1), (0, 0, 1.1), lens=50)}
from PIL import Image
ims = []
for v in os.environ.get("VIEWS", "front,three,back").split(","):
    render_to(f"{OUT}/{NAME}_{v}.png", cams[v])
    ims.append(Image.open(f"{OUT}/{NAME}_{v}.png"))
c = Image.new('RGB', (480 * len(ims), 720))
for i, im in enumerate(ims):
    c.paste(im, (480 * i, 0))
c.save(f"{OUT}/{NAME}_sheet.png")
