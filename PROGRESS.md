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
  cheekbones, hooded eyes, aquiline nose, thin downturned mouth). Still needs more passes to
  match the reference's striking, sharp features.
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
- **viz_full.py** — loads a saved sim result and renders front/three-quarter/back views.
- Earlier single-part scripts (head_test.py, pose_test.py, skirt_test.py / skirt_sim.py /
  skirt_dbg.py / viz_skirt.py) still work and are kept for isolated testing of one part.

## Renders (renders/)
- `head_front.png`, `head_three.png` — bare head/shoulders with the shape.py morph recipe
  and fitted MakeHuman eyes.
- `pose_sheet.png` + views — full body in the final arm/head pose (nude, rigging reference).
- `skirt0.png` — first (non-simulated) skirt attempt, too clean/conical.
- `skirt_sim_sheet.png` / `skirt_sim.blend` — skirt-only cloth sim, stable after fixing an
  earlier self-collision explosion.
- `full_sim_sheet.png` / `full_sim.blend` — **current best**: bodice + bell sleeves +
  pleated skirt + hood, all cloth-simulated together on the posed body with wind that settles
  out before the end of the sim. All four pieces now drape plausibly: skirt falls naturally
  around the legs without flying open, sleeves bell out without bunching into a ball, and the
  hood is a visible drape at the back of the neck/shoulders rather than collapsing to nothing.
  Still untextured gray/lavender clay — no robe color, gold trim, or face/hair detail yet.

## Known gaps / next steps (in order)
1. **Materials**: velvet/satin purple robe shader with sheen (closer to the comic reference's
   deep purple), gold metallic trim/embroidery meshes conformed to the simulated cloth
   surface, pearl/bead trim, sash with tassels — this is the single highest-impact remaining
   step since everything is currently flat gray/lavender clay.
2. Push `shape.py` morphs further for a closer facial match to the reference (sharper
   cheekbones/jaw, more hooded/narrow eyes, visible age lines) — current result is still a
   bit generic/youthful.
3. Add eyebrows/eyelashes (MakeHuman has CC0 assets for both, not yet wired in) and a proper
   skin shader pass (pores/bump, SSS tuned).
4. Hair: strand-based (Blender hair curves) rooted on the scalp, not tube clumps like v3.
5. Hood fine-tuning: it reads as a drape now but could be larger/more voluminous to read
   unambiguously as a hood rather than a ruffled collar at a glance — worth one more pass
   once materials make it color-distinct from the bodice.
6. Final assembly + lighting pass; render per-part (robe alone, head alone, hands alone,
   full figure) per the original request, then a combined beauty render.

## How to resume
All code is self-contained under `code/` and imports MakeHuman data from
`/home/claude/assets/mh` (a sparse git clone of github.com/makehumancommunity/makehuman,
CC0-licensed, not included here — re-run the sparse clone if assets/ is gone in a fresh
container; see git history / ask Claude to redo it). Everything is driven by small Python
scripts run as `python3 <script>.py` (uses the `bpy` pip module, not the Blender executable)
with env vars for quick parameter sweeps (SAMPLES, VIEWS, FRAMES, WIND, ROWS_SK/SL/HD, etc.)
— see each script's top for its knobs.
