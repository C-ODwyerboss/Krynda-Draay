# Progress: realistic MakeHuman-based mage model

## Goal
Replace the hand-built primitive mage (v1-v3, in `code/legacy_handbuilt/`) with a pipeline
built on a real human base mesh (MakeHuman, CC0-licensed), posed with a proper skeleton,
dressed in a cloth-simulated robe (hood worn down, not up), rendered in Cycles.

## What's working (code/)
- **mh.py** — loader for MakeHuman's CC0 base mesh (19158 verts, UVs, helper groups for
  eyes/teeth/tongue/etc.), applies macro targets (gender/age/muscle/weight/height/ethnicity
  blending, matching MakeHuman's own weighting formulas) and arbitrary detail targets
  (face/body morphs) by index-additive deltas. Also fits MakeHuman's high-poly eye mesh via
  its .mhclo proxy format.
- **shape.py** — the character's specific face/body morph recipe (gaunt face, high
  cheekbones, hooded eyes, aquiline nose, thin downturned mouth). Pushed further today: more
  angular skull, stronger brow, deeper-set narrower eyes, more pronounced nose hump, hollower
  cheeks, more prominent jaw/chin, longer neck, age bumped 40→46 — reads noticeably sharper
  and more mature now, less "generic/youthful" (see renders below).
- **pose.py** — numpy linear-blend-skinning using MakeHuman's default skeleton (163 bones).
  FK posing with an `aim_chain` helper and a 2-bone IK solver for arms.
- **posing.py** — the actual pose: arms raised, one hand gathering the robe at the chest,
  head turned/tilted, with per-finger curl based on rest-pose hand geometry.
- **garment.py** — builds the garment directly from the posed skin surface:
  - `build_base` — bodice torso panel, selected by bone-weight region, offset along normals
  - `build_skirt` — flared pleated skirt extruded from the waist boundary loop, with a
    body-clearance pass so it doesn't clip the legs
  - `build_sleeve` — bell-flared sleeve tube following the arm via parallel-transport frames
  - `build_hood_base` — a wide hood/cape panel attached to the back half of the neckline,
    standing up and arcing back/down so a cloth sim settles it into a believable
    worn-down-the-back drape (fixed today: was originally shrinking to an invisible point
    and attached to the front half of the neck by a sign error — now attaches to the back
    half and keeps its width as it falls)
- **robe_common.py** — Cycles cloth-sim helpers (pin groups, self-collision, wind field with
  a settle phase that tapers wind to zero near the end of the sim so everything relaxes
  instead of staying wind-whipped).
- **full_sim.py** — builds bodice + sleeves + skirt + hood together from one posed body and
  cloth-simulates all four pieces at once, colliding with the body and floor and each other.
- **viz_full.py** — loads a saved sim result and renders front/three-quarter/back views with
  flat clay materials (kept as a quick structural-check script).
- **materials_full.py** — the real materials pass on the saved sim result: a velvet/satin
  Principled shader (sheen + layered noise bump for weave/fold variation) in deep purple for
  the bodice/sleeves/skirt and a darker shade for the hood; gold metallic trim built as
  bevelled curves directly along the simulated cloth's own boundary loops (hem, both cuffs,
  hood free edge, neckline) so it conforms to the actual drape instead of being hand-placed;
  a strung pearl trim (small spheres) under the neckline trim; and a waist sash (flat ribbon
  built from the pinned, undistorted waist loop) with two hanging tapered gold tassels at
  front-centre.
- **hair_test.py** — real strand-based hair on the head_test.py scene, using Blender's
  Curves/hair-curves object (`bpy.data.hair_curves`) and a Principled Hair BSDF shader
  (COLOR parametrization, warm golden blonde), replacing the v3 hand-built tube clumps.
  Strand roots are sampled from a scalp region selected by height + outward-normal direction
  (no bone/weight data needed for this), each grown as an 18-point curve that eases from a
  small scalp-hugging root bump into a shared "windswept" flow direction with per-strand
  length/curl/phase variation, gravity pull, and a part-line bias so the crown doesn't spike
  straight up along the seam.
- Earlier single-part scripts (head_test.py, pose_test.py, skirt_test.py / skirt_sim.py /
  skirt_dbg.py / viz_skirt.py) still work and are kept for isolated testing of one part.

## Renders (renders/)
- `head_front.png`, `head_three.png` — bare head/shoulders with the sharpened shape.py morph
  recipe, fitted MakeHuman eyes (now tinted instead of flat grey), a layered-noise skin bump
  (broad undulation + fine pore scale, plus roughness variation) for a less "clay" look, and
  procedural eyebrow ribbons (MakeHuman's own eyebrow asset isn't present in this sparse
  clone, so these are hand-built from eye-socket geometry as a stand-in until real
  strand-based brows/hair are added).
- `pose_sheet.png` + views — full body in the final arm/head pose (nude, rigging reference).
- `skirt0.png` — first (non-simulated) skirt attempt, too clean/conical.
- `skirt_sim_sheet.png` / `skirt_sim.blend` — skirt-only cloth sim, stable after fixing an
  earlier self-collision explosion.
- `full_sim_sheet.png` / `full_sim.blend` — the raw cloth-sim result: bodice + bell sleeves +
  pleated skirt + hood, all simulated together on the posed body with wind that settles out
  before the end of the sim. All four pieces drape plausibly: skirt falls naturally around
  the legs without flying open, sleeves bell out without bunching into a ball, and the hood
  is a visible drape at the back of the neck/shoulders rather than collapsing to nothing.
  Kept as the untextured structural reference.
- `full_sim_mat_sheet.png` (front/three/back) / `full_sim_materials.blend` — the dressed,
  cloth-simulated body with the real materials pass (deep purple velvet, gold hem/cuff/
  hood/neckline trim, pearl trim, waist sash + tassels). Still missing hair and a combined
  head+body shot (the head and body/robe are still built and rendered by separate scripts).
- `hair_sheet.png` (front/three) / `hair_test.blend` — **current best for the head**: the
  sharpened-morph head with real strand-based blonde hair blown windswept to one side,
  shoulder-length and past. Reads well mid-strand and at the tips; the roots right at the
  crown/hairline are still a bit spiky/comb-like rather than lying flat before catching the
  wind -- worth one more pass (see gap #5 below) if it still reads that way once hair is
  combined with the dressed body at a normal viewing distance (it's more noticeable in this
  tight head-only crop than it likely will be on the full figure).

## Known gaps / next steps (in order)
1. ~~Materials~~ — done (see `materials_full.py` above): velvet/satin purple robe shader
   with sheen, gold trim conformed to the simulated cloth boundaries, pearl trim, sash with
   tassels. Embroidery is only implied by the gold trim + weave-noise bump, not an actual
   embroidered pattern texture — a further pass could add that if it's worth the extra detail.
2. ~~Push `shape.py` morphs further~~ — done (sharper skull/brow/cheek/jaw, deeper eyes,
   stronger nose, age 46). Could still go further if later full-body renders show it reading
   soft again at a distance, but it's a clear step up from the previous pass.
3. Eyelashes and a real eyebrow asset (current eyebrows are a hand-built procedural
   stand-in, not MakeHuman's own asset — that asset wasn't present in this sparse clone) are
   still outstanding; skin shader now has a first bump/roughness-variation pass (see above)
   but could use an actual pore/wrinkle texture map rather than pure procedural noise.
4. ~~Hair~~ — done (see `hair_test.py` above): real strand-based Curves hair with a
   Principled Hair BSDF, windswept and blonde. The root/hairline area could use one more
   pass to lie flatter before sweeping sideways (currently a bit spiky/comb-like close up).
5. Hood fine-tuning: it reads as a drape now but is still not unambiguously hood-shaped from
   the back even with its own darker material and gold edge trim — worth another geometry
   pass (larger/more forward-draping) rather than a materials one.
6. **Final assembly** — now the single highest-impact remaining step: the head+hair
   (head_test.py / hair_test.py) and the dressed body (materials_full.py) are still three
   separate scripts/renders using separately-posed bodies. Next is combining them into one
   script so the finished head+hair sits on the dressed, cloth-simmed body in a single
   render, then a proper lighting pass and the originally-requested per-part renders (robe
   alone, head alone, hands alone, full figure) plus a combined beauty render.

## How to resume
All code is self-contained under `code/` and imports MakeHuman data from
`/home/claude/assets/mh` (a sparse git clone of github.com/makehumancommunity/makehuman,
CC0-licensed, not included here — re-run the sparse clone if assets/ is gone in a fresh
container; see git history / ask Claude to redo it). Everything is driven by small Python
scripts run as `python3 <script>.py` (uses the `bpy` pip module, not the Blender executable)
with env vars for quick parameter sweeps (SAMPLES, VIEWS, FRAMES, WIND, ROWS_SK/SL/HD, etc.)
— see each script's top for its knobs.
