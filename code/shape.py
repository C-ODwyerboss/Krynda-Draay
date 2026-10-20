"""Character shape definition (MakeHuman macro + detail targets)."""
import os

AGE = float(os.environ.get("AGE", "46"))

MACRO = dict(gender=0.0, age_years=AGE, muscle=0.36, weight=0.28, height=0.58)


def sym(group, name, w, prefix=("l-", "r-")):
    return {f"{group}/{p}{name}": w for p in prefix}


def face_details():
    d = {}

    def add(stem, w):
        d[stem] = d.get(stem, 0.0) + w

    def both(group, name, w):
        for p in ("l-", "r-"):
            add(f"{group}/{p}{name}", w)

    # head / skull -- more angular, less youthful-round
    add("head/head-oval", 0.45)
    add("head/head-triangular", 0.40)
    add("head/head-age-incr", 0.55)
    add("head/head-fat-decr", 0.60)
    add("head/head-scale-vert-incr", 0.08)

    # forehead / brow -- stronger, lower, more severe brow line
    add("eyebrows/eyebrows-angle-down", 0.42)
    add("eyebrows/eyebrows-trans-down", 0.28)
    add("forehead/forehead-temple-decr", 0.42)

    # eyes: hooded, deep-set, narrow -- sharp/striking rather than tired
    for n, w in (("eye-bag-incr", 0.40), ("eye-bag-height-incr", 0.15), ("eye-height1-decr", 0.35),
                 ("eye-eyefold-down", 0.55), ("eye-eyefold-convex", 0.30), ("eye-corner2-down", 0.30),
                 ("eye-push1-in", 0.35), ("eye-scale-incr", 0.0)):
        both("eyes", n, w)

    # nose: long, straight bridge, pronounced hump, down-turned tip, narrow nostrils
    for n, w in (("nose-hump-incr", 0.60), ("nose-point-down", 0.55), ("nose-greek-incr", 0.42),
                 ("nose-scale-vert-incr", 0.35), ("nose-width1-decr", 0.45), ("nose-width3-decr", 0.28),
                 ("nose-nostrils-width-decr", 0.38), ("nose-flaring-decr", 0.25), ("nose-scale-depth-incr", 0.20),
                 ("nose-base-down", 0.15)):
        add(f"nose/{n}", w)

    # cheeks: high, hollow bones -- gaunt, sculpted
    both("cheek", "cheek-bones-incr", 0.80)
    both("cheek", "cheek-volume-decr", 0.70)
    both("cheek", "cheek-inner-decr", 0.32)
    both("cheek", "cheek-trans-up", 0.15)

    # mouth: thin lips, down-turned, deep-set laugh lines
    for n, w in (("mouth-upperlip-volume-decr", 0.62), ("mouth-lowerlip-volume-decr", 0.58),
                 ("mouth-angles-down", 0.55), ("mouth-laugh-lines-in", 0.75), ("mouth-cupidsbow-incr", 0.25),
                 ("mouth-scale-horiz-incr", 0.12), ("mouth-trans-down", 0.06), ("mouth-philtrum-volume-incr", 0.25)):
        add(f"mouth/{n}", w)

    # chin / jaw -- prominent, narrow, defined
    add("chin/chin-prominent-incr", 0.42)
    add("chin/chin-width-decr", 0.42)
    add("chin/chin-triangle", 0.35)
    add("chin/chin-bones-incr", 0.38)
    add("chin/chin-jaw-drop-incr", 0.12)

    # neck -- longer, slender
    add("neck/neck-scale-vert-incr", 0.22)
    add("neck/neck-scale-horiz-decr", 0.22)

    # ears
    both("ears", "ear-scale-decr", 0.12)
    both("ears", "ear-lobe-incr", 0.22)
    return d
