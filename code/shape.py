"""Character shape definition (MakeHuman macro + detail targets)."""
import os

AGE = float(os.environ.get("AGE", "40"))

MACRO = dict(gender=0.0, age_years=AGE, muscle=0.30, weight=0.36, height=0.58)


def sym(group, name, w, prefix=("l-", "r-")):
    return {f"{group}/{p}{name}": w for p in prefix}


def face_details():
    d = {}

    def add(stem, w):
        d[stem] = d.get(stem, 0.0) + w

    def both(group, name, w):
        for p in ("l-", "r-"):
            add(f"{group}/{p}{name}", w)

    # head / skull
    add("head/head-oval", 0.35)
    add("head/head-triangular", 0.25)
    add("head/head-age-incr", 0.35)
    add("head/head-fat-decr", 0.45)
    add("head/head-scale-vert-incr", 0.05)

    # forehead / brow
    add("eyebrows/eyebrows-angle-down", 0.30)
    add("eyebrows/eyebrows-trans-down", 0.15)
    add("forehead/forehead-temple-decr", 0.3)

    # eyes: heavy lid, slightly deep set, tired lower lid
    for n, w in (("eye-bag-incr", 0.55), ("eye-bag-height-incr", 0.2), ("eye-height1-decr", 0.25),
                 ("eye-eyefold-down", 0.45), ("eye-eyefold-convex", 0.25), ("eye-corner2-down", 0.25),
                 ("eye-push1-in", 0.2), ("eye-scale-incr", 0.05)):
        both("eyes", n, w)

    # nose: long, straight bridge, slight hump, down-turned tip, narrow nostrils
    for n, w in (("nose-hump-incr", 0.45), ("nose-point-down", 0.45), ("nose-greek-incr", 0.30),
                 ("nose-scale-vert-incr", 0.28), ("nose-width1-decr", 0.35), ("nose-width3-decr", 0.2),
                 ("nose-nostrils-width-decr", 0.3), ("nose-flaring-decr", 0.2), ("nose-scale-depth-incr", 0.15),
                 ("nose-base-down", 0.1)):
        add(f"nose/{n}", w)

    # cheeks: high bones, hollow
    both("cheek", "cheek-bones-incr", 0.65)
    both("cheek", "cheek-volume-decr", 0.55)
    both("cheek", "cheek-inner-decr", 0.2)
    both("cheek", "cheek-trans-up", 0.1)

    # mouth: thin lips, down-turned, deep laugh lines
    for n, w in (("mouth-upperlip-volume-decr", 0.55), ("mouth-lowerlip-volume-decr", 0.5),
                 ("mouth-angles-down", 0.45), ("mouth-laugh-lines-in", 0.6), ("mouth-cupidsbow-incr", 0.2),
                 ("mouth-scale-horiz-incr", 0.1), ("mouth-trans-down", 0.05), ("mouth-philtrum-volume-incr", 0.2)):
        add(f"mouth/{n}", w)

    # chin / jaw
    add("chin/chin-prominent-incr", 0.3)
    add("chin/chin-width-decr", 0.3)
    add("chin/chin-triangle", 0.25)
    add("chin/chin-bones-incr", 0.25)
    add("chin/chin-jaw-drop-incr", 0.1)

    # neck
    add("neck/neck-scale-vert-incr", 0.15)
    add("neck/neck-scale-horiz-decr", 0.15)

    # ears
    both("ears", "ear-scale-decr", 0.1)
    both("ears", "ear-lobe-incr", 0.2)
    return d
