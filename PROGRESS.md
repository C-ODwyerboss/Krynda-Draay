# Progress: realistic MakeHuman-based mage model

## Goal
Replace the hand-built primitive mage (v1-v3, in /home/claude/robed_mage_v*.py) with a
pipeline built on a real human base mesh (MakeHuman, CC0-licensed), posed with a proper
skeleton, dressed in a cloth-simulated robe, rendered in Cycles — per your "extremely
detailed, hood down, render each part separately" request.

## What's working (this session, in /home/claude/work)
- **mh.py** — loader for MakeHuman's CC0 base mesh (`/home/claude/assets/mh`, sparse-cloned
  from github.com/makehumancommunity/makehuman): parses base.obj (19158 verts, UVs,
  helper groups for eyes/teeth/tongue/etc.), applies macro targets (gender/age/muscle/
  weight/height/ethnicity blending, matching MakeHuman's own weighting formulas) and
  arbitrary detail targets (face/body morphs) by index-additive deltas. Also fits
  MakeHuman's high-poly eye mesh via its .mhclo proxy format.
- **shape.py** — the character's specific face/body morph recipe (gaunt mature-ish face,
  high cheekbones, hooded eyes, aquiline nose, thin downturned mouth — aiming at the
  reference's stern sorceress look). Needs more passes to look as striking as the comic.
- **pose.py** — numpy linear-blend-skinning using MakeHuman's default skeleton
  (default.mhskel + default_weights.mhw, 163 bones). FK posing with per-bone rotation
  matrices, an `aim_chain` helper to point a bone at a target, and a 2-bone IK solver
  for arms.
- **posing.py** — the actual pose: arms raised, one hand gathering the robe at the chest
  (based on your reference image), head turned/tilted. Hand posing orients the wrist and
  curls fingers based on rest-pose hand geometry.
- **garment.py** — builds a bodice+sleeve mesh directly from the posed skin (selected by
  bone-weight region, offset along normals), extracts its waist boundary loop, and
  generates a flared pleated skirt extruded from that loop with procedural folds and a
  body-clearance pass so it doesn't clip the legs. Also has a proper sleeve-tube builder
  (`build_sleeve` — parallel-transport frames along an arbitrary arm path with bell flare)
  that's written but not yet wired in to replace the simple bodice sleeves.
- **robe_common.py** — Cycles cloth-sim helpers (pin groups, self-collision, wind field)
  used to drape the skirt realistically instead of hand-sculpting folds.
- Render test scripts: **head_test.py**, **pose_test.py**, **skirt_test.py / skirt_sim.py
  / skirt_dbg.py / viz_skirt.py**.

## Renders so far (out/)
- `head_front.png`, `head_three.png` — bare head/shoulders with the shape.py morph recipe
  and fitted MakeHuman eyes. Reasonable proportions but still needs more extreme
  character-specific sculpting to match the reference's sharp, stern features, plus
  brows/lashes/skin texture/hair.
- `pose_sheet.png` — full body in the final arm/head pose (nude, for rigging/garment
  reference only).
- `skirt0.png` — first skirt attempt: procedural-only folds, no simulation (too clean/
  conical, not cloth-like).
- `skirt_sim_sheet.png` / `skirt_sim.blend` — current best: cloth-simulated skirt +
  bodice on the posed body, with wind, pinned at the waist, colliding with legs and floor.
  Stable sim (fixed an earlier self-collision explosion by tightening self_distance and
  disabling collision during the free-fall phase). This is the most "handmade-robe-like"
  result so far but is still untextured gray/lavender clay and needs: UV-mapped fabric
  material (velvet/sheen shader matching the reference's deep purple), gold trim/
  embroidery conforming to the simulated surface, hood, sash, and the sleeve rebuild.

## Known gaps / next steps (in order)
1. Rebuild sleeves with `garment.build_sleeve` (bell-flared, arm-following) instead of the
   crude normal-offset sleeve currently baked into the bodice.
2. Add the hood (separate cloth sim or a hand-authored mesh fit to the fitted head/neck),
   per your "hood down" instruction — hood should hang down the back, not worn up.
3. Push `shape.py` morphs further for a closer facial match to the 3 reference panels
   (sharper cheekbones/jaw, more hooded/narrow eyes, visible age lines) — current result
   is still a bit generic/youthful.
4. Add eyebrows/eyelashes (MakeHuman has CC0 assets for both, not yet wired in) and a
   proper skin shader pass (pores/bump, SSS tuned).
5. Hair: strand-based (Blender hair curves) rooted on the scalp, not tube clumps like v3.
6. Materials: velvet/satin robe shader with sheen, gold metallic trim/embroidery meshes
   conformed to the simulated cloth surface (project or shrinkwrap onto it), pearl/bead
   trim, sash with tassels.
7. Final assembly + lighting pass; render per-part (robe alone, head alone, hands alone,
   full figure) per your request, then a combined beauty render.

## How to resume
All code is self-contained under /home/claude/work and imports the MakeHuman data from
/home/claude/assets/mh (a sparse git clone — re-run the clone commands in this session's
history if assets/ is gone in a fresh container). Everything is driven by small Python
scripts run as `python3 <script>.py` (uses the `bpy` pip module, not the Blender
executable) with env vars for quick parameter sweeps (SAMPLES, VIEWS, FRAMES, etc.) — see
each script's top. git history in /home/claude/work has one commit with all of the above.
