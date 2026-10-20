# Krynda-Draay

Model for Krynda Draay — a code-driven Blender pipeline building a realistic
robed-mage character from a CC0 MakeHuman base mesh, with proper skeleton
posing and a cloth-simulated robe (bodice, bell sleeves, pleated skirt,
hood-down panel).

- `code/` — the pipeline scripts (run with `python3 <script>.py`, using the `bpy`
  pip module). See `PROGRESS.md` for what each file does and current status.
- `code/legacy_handbuilt/` — earlier hand-primitive versions (v1-v3), kept for reference.
- `renders/` — preview renders and `.blend` scene files produced so far.
- `PROGRESS.md` — detailed status, what's working, what's next.

Depends on MakeHuman's CC0-licensed asset data (base mesh, morph targets, rig),
sparse-cloned from github.com/makehumancommunity/makehuman — not included here,
re-clone as needed (paths assumed under /home/claude/assets/mh).
