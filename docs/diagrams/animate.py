#!/usr/bin/env python3
"""Renders the animated overview of the path to production.

    pip install cairosvg pillow            # plus ffmpeg on the PATH
    python3 docs/diagrams/animate.py       # writes 00-path-to-production.gif and .mp4 here

The story follows one release: push, check, release, synthesize, sign in,
promote. The first and last frames show the complete picture, so the GIF
loops seamlessly and its first frame works as a still image.
"""

from __future__ import annotations

import math
import subprocess
import sys
import tempfile
from html import escape
from multiprocessing import Pool
from pathlib import Path

import cairosvg
from PIL import Image

W, H, FPS = 1200, 760, 20
FONT = "Inter, 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

INK, SLATE, MUTED, HAIR = "#0F172A", "#334155", "#64748B", "#CBD5E1"
GHOST_FILL, GHOST_STROKE, GHOST_TEXT, GHOST_SUB = "#FFFFFF", "#DCE2EA", "#AEB8C6", "#C6CED9"
GREEN, GREEN_DARK, BLUE = "#2E8B57", "#14532D", "#4A6FA5"
KINDS = {  # fill, stroke, title colour
    "code": ("#F8FAFC", "#334155", INK),
    "ci": ("#EEF3FB", "#4A6FA5", "#1E3A66"),
    "aws": ("#FFF4E8", "#D9822B", "#7A3E06"),
    "ok": ("#ECF7F0", "#2E8B57", "#14532D"),
    "support": ("#F3F4F6", "#9CA3AF", SLATE),
}
TINTS = {"ci": "#F4F7FC", "support": "#F6F7F9", "aws": "#FFF8F0"}

# ── story clock (seconds) ──────────────────────────────────────────────────
SCENES = [  # key, start, headline, sentence
    ("intro", 0.0, "One release, start to finish",
     "Watch a Hello World Java Lambda travel from a commit to production."),
    ("push", 1.2, "Push",
     "A developer pushes the Java app and its Java CDK infrastructure to GitHub."),
    ("check", 4.2, "Check",
     "App CI and Infra CI build, test and lint every change. Neither pipeline can touch AWS."),
    ("release", 8.0, "Release",
     "A version tag publishes the tested JAR once. A released version never changes."),
    ("synth", 11.5, "Synthesize",
     "A pull request pins that version. AWS CDK turns the Java stack into CloudFormation, once."),
    ("signin", 15.5, "Sign in",
     "The release job signs in to AWS with OIDC. Credentials expire within an hour; no keys are stored."),
    ("promote", 19.3, "Promote",
     "The same files climb from Dev to QA to Prod. Each gate must pass, and Prod waits for a person."),
    ("final", 28.1, "Build once, deploy many",
     "The app is Hello World. The value is the path that delivers it."),
]
STORY_END = 31.1          # final state held until here
LEAD_HOLD, LEAD_FADE = 1.6, 0.6   # the GIF opens on the finished picture, then resets
STEPS = ["Push", "Check", "Release", "Synthesize", "Sign in", "Promote"]

# geometry ─────────────────────────────────────────────────────────────────
R1, R2, R3, NH = 156, 296, 436, 84            # row tops, node height
Z1, Z2, Z3 = (24, 392), (424, 736), (848, 1176)
GH = (44, R1, 328, NH)
INFRA = (44, R2, 156, NH)
APP = (216, R2, 156, NH)
ART = (444, R1, 272, NH)
CDK = (444, R2, 272, NH)
TPL = (444, R3, 272, NH)
PROD = (868, R1, 288, NH)
QA = (868, R2, 288, NH)
DEV = (868, R3, 288, NH)
FOUND = (868, 540, 288, 54)
LOCK = (792, R3 + NH / 2)
CX3 = 1012

P_GH_INFRA = [(122, R1 + NH), (122, R2)]
P_GH_APP = [(294, R1 + NH), (294, R2)]
P_APP_ART = [(372, R2 + NH / 2), (408, R2 + NH / 2), (408, R1 + NH / 2), (444, R1 + NH / 2)]
P_ART_CDK = [(520, R1 + NH), (520, R2)]
P_CDK_TPL = [(520, R2 + NH), (520, R3)]
P_TPL_DEV = [(716, R3 + NH / 2), (868, R3 + NH / 2)]
P_DEV_QA = [(CX3, R3), (CX3, R2 + NH)]
P_QA_PROD = [(CX3, R2), (CX3, R1 + NH)]
LOCK_FRAC = (LOCK[0] - 716) / (868 - 716)


# ── helpers ────────────────────────────────────────────────────────────────
def clamp(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def prog(t, a, b):
    return clamp((t - a) / (b - a))


def ease(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def on(t, a, d=0.4):
    return ease(prog(t, a, a + d))


def window(t, a, b, d=0.3):
    return min(on(t, a, d), 1 - on(t, b, d))


def pop(t, a, d=0.3):
    x = prog(t, a, a + d)
    if x <= 0:
        return 0.0
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2


def mix(c1, c2, a):
    a = clamp(a)
    p = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    q = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * a):02X}" for x, y in zip(p, q))


def along(pts, f):
    segs = list(zip(pts, pts[1:]))
    lens = [math.dist(a, b) for a, b in segs]
    goal = clamp(f) * sum(lens)
    for (a, b), L in zip(segs, lens):
        if goal <= L or L == 0:
            k = 0 if L == 0 else goal / L
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        goal -= L
    return pts[-1]


def partial(pts, f):
    segs = list(zip(pts, pts[1:]))
    lens = [math.dist(a, b) for a, b in segs]
    goal = clamp(f) * sum(lens)
    out = [pts[0]]
    for (a, b), L in zip(segs, lens):
        if goal >= L:
            out.append(b)
            goal -= L
        else:
            k = goal / L if L else 0
            out.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
            break
    return out


class Frame:
    def __init__(self):
        self.parts: list[str] = []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, fill, stroke="none", r=12, sw=2, dash=None, op=1.0, dashoff=0):
        if op <= 0.001:
            return
        d = f' stroke-dasharray="{dash}" stroke-dashoffset="{dashoff:.1f}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op:.3f}"{d}/>')

    def text(self, x, y, s, size=16, weight=400, color=SLATE, anchor="start", font=FONT,
             op=1.0, spacing=0.0):
        if op <= 0.001:
            return
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" '
                 f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
                 f'opacity="{op:.3f}"{ls}>{escape(s)}</text>')

    def poly(self, pts, color, sw=2.2, op=1.0, dash=None):
        if len(pts) < 2 or op <= 0.001:
            return
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linejoin="round" opacity="{op:.3f}"{da}/>')

    def head(self, a, b, color, op=1.0):
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        hl, hw = 11, 6
        bx, by = b[0] - hl * math.cos(ang), b[1] - hl * math.sin(ang)
        px, py = -math.sin(ang), math.cos(ang)
        tri = [b, (bx + hw * px, by + hw * py), (bx - hw * px, by - hw * py)]
        self.add('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in tri)
                 + f'" fill="{color}" opacity="{op:.3f}"/>')

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
                f'viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#FFFFFF"/>'
                + "".join(self.parts) + "</svg>")


# ── components ─────────────────────────────────────────────────────────────
def arrow(f, pts, lit):
    """Ghost path, with the travelled part drawn in slate up to `lit`."""
    f.poly(pts, GHOST_STROKE)
    f.head(pts[-2], pts[-1], GHOST_STROKE)
    if lit > 0:
        f.poly(partial(pts, lit), SLATE)
        if lit >= 0.999:
            f.head(pts[-2], pts[-1], SLATE)


def node(f, box, kind, title, lines, a, ring=0.0, title_size=20, line_size=14):
    """lines: list of dicts {text, alpha, font, color, alt, alt_color, alt_font, swap}."""
    x, y, w, h = box
    fill, stroke, tcol = KINDS[kind]
    if ring > 0:
        f.rect(x - 6, y - 6, w + 12, h + 12, "none", stroke, r=17, sw=3, op=0.32 * ring)
    f.rect(x, y, w, h, mix(GHOST_FILL, fill, a), mix(GHOST_STROKE, stroke, a), r=12)
    entries = [dict(text=title, size=title_size, weight=600, color=mix(GHOST_TEXT, tcol, a),
                    font=FONT, alpha=1.0)]
    for ln in lines:
        e = dict(size=line_size, weight=400, font=FONT, alpha=1.0)
        e.update(ln)
        e["color"] = mix(GHOST_SUB, ln.get("color", MUTED), a)
        entries.append(e)
    heights = [e["size"] * 1.32 * e["alpha"] for e in entries]
    cy = y + (h - sum(heights)) / 2
    for e, lh in zip(entries, heights):
        base = cy + e["size"] * 1.32 * 0.76 * max(e["alpha"], 0.6)
        swap = e.get("swap", 0.0)
        f.text(x + w / 2, base, e["text"], e["size"], e["weight"], e["color"], "middle",
               e["font"], op=e["alpha"] * (1 - swap))
        if swap > 0:
            f.text(x + w / 2, base, e["alt"], e.get("alt_size", e["size"]), 600,
                   e["alt_color"], "middle", e.get("alt_font", e["font"]), op=swap)
        cy += lh


def badge(f, cx, cy, s):
    if s <= 0.001:
        return
    f.add(f'<g transform="translate({cx:.1f},{cy:.1f}) scale({s:.3f})">'
          f'<circle r="12" fill="{GREEN}" stroke="#FFFFFF" stroke-width="3"/>'
          f'<path d="M-5.2,0.2 l3.6,3.6 l6.8,-7.2" fill="none" stroke="#FFFFFF" '
          f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></g>')


def bar(f, box, p, kind, op):
    if op <= 0.001:
        return
    x, y, w, h = box
    f.rect(x + 16, y + h - 11, w - 32, 4, "#E2E8F0", r=2, sw=0, op=op)
    if p > 0:
        f.rect(x + 16, y + h - 11, (w - 32) * p, 4, KINDS[kind][1], r=2, sw=0, op=op)


def chip(f, cx, cy, s, style="navy", op=1.0, scale=1.0, size=13):
    if op <= 0.001 or scale <= 0.001:
        return
    styles = {
        "navy": ("#1E3A66", "#1E3A66", "#FFFFFF"),
        "blue": (BLUE, BLUE, "#FFFFFF"),
        "slate": (SLATE, SLATE, "#FFFFFF"),
        "outline": ("#FFFFFF", BLUE, "#1E3A66"),
        "pin": ("#FFFFFF", SLATE, SLATE),
    }
    fill, stroke, tc = styles[style]
    w = len(s) * size * 0.61 + 20
    h = size + 13
    f.add(f'<g transform="translate({cx:.1f},{cy:.1f}) scale({scale:.3f})" opacity="{op:.3f}">'
          f'<rect x="{-w / 2:.1f}" y="{-h / 2:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
          f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>'
          f'<text x="0" y="{size * 0.36:.1f}" font-family="{MONO}" font-size="{size}" '
          f'font-weight="600" fill="{tc}" text-anchor="middle">{escape(s)}</text></g>')


def sheet(f, x, y, label, a, s):
    """A small CloudFormation template sheet; a = colour, s = pop scale."""
    w, h = 52, 32
    stroke = mix(GHOST_STROKE, SLATE, a)
    col = mix(GHOST_SUB, SLATE, a)
    sc = 1.0 if a <= 0 else max(s, 0.001)
    f.add(f'<g transform="translate({x + w / 2:.1f},{y + h / 2:.1f}) scale({sc:.3f}) '
          f'translate({-w / 2},{-h / 2})">'
          f'<path d="M0,0 H{w - 10} L{w},10 V{h} H0 Z" fill="#FFFFFF" stroke="{stroke}" '
          f'stroke-width="1.6" stroke-linejoin="round"/>'
          f'<path d="M{w - 10},0 V10 H{w}" fill="none" stroke="{stroke}" stroke-width="1.6"/>'
          f'<text x="{w / 2 - 3}" y="{h / 2 + 5}" font-family="{MONO}" font-size="12" '
          f'font-weight="600" fill="{col}" text-anchor="middle">{label}</text></g>')


def pill(f, cx, cy, w, label, state, op=1.0, h=30):
    """state: 0 ghost → 1 green. Check mark appears with the green state."""
    x, y = cx - w / 2, cy - h / 2
    f.rect(x, y, w, h, mix(GHOST_FILL, KINDS["ok"][0], state),
           mix(GHOST_STROKE, GREEN, state), r=h / 2, sw=2, op=op)
    tc = mix(GHOST_TEXT, GREEN_DARK, state)
    shift = 9 * state
    f.text(cx + shift, cy + 5, label, 14, 600, tc, "middle", op=op)
    if state > 0.05:
        tw = len(label) * 14 * 0.53
        ix = cx + shift - tw / 2 - 13
        f.add(f'<path d="M{ix - 5:.1f},{cy:.1f} l3.6,3.6 l6.8,-7.2" fill="none" stroke="{GREEN}" '
              f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" '
              f'opacity="{state * op:.3f}"/>')


def split_pill(f, cx, cy, halves, h=30, dashoff=0.0):
    """halves: [(label, state, waiting)], drawn as one gate with two posts."""
    w = 120
    x0, xm, x1, y0, r = cx - w, cx, cx + w, cy - h / 2, h / 2
    paths = [f"M{x0 + r},{y0} H{xm} V{y0 + h} H{x0 + r} A{r},{r} 0 0 1 {x0 + r},{y0} Z",
             f"M{xm},{y0} H{x1 - r} A{r},{r} 0 0 1 {x1 - r},{y0 + h} H{xm} Z"]
    centers = [cx - w / 2 + 6, cx + w / 2 - 6]
    for path, c, (label, st, wait) in zip(paths, centers, halves):
        fill = mix(GHOST_FILL, KINDS["ok"][0], st)
        stroke = mix(GHOST_STROKE, GREEN, st)
        dash = ""
        if wait > 0 and st < 0.5:
            stroke = mix(GHOST_STROKE, SLATE, wait)
            dash = f' stroke-dasharray="6 5" stroke-dashoffset="{dashoff:.1f}"'
        f.add(f'<path d="{path}" fill="{fill}" stroke="{stroke}" stroke-width="2"{dash}/>')
        tc = mix(GHOST_TEXT, GREEN_DARK, st) if st > 0 or wait <= 0 else mix(GHOST_TEXT, INK, wait)
        shift = 9 * max(st, wait)
        f.text(c + shift, cy + 5, label, 14, 600, tc, "middle")
        ix = c + shift - len(label) * 14 * 0.265 - 13
        if st > 0.05:
            f.add(f'<path d="M{ix - 5:.1f},{cy:.1f} l3.6,3.6 l6.8,-7.2" fill="none" '
                  f'stroke="{GREEN}" stroke-width="2.6" stroke-linecap="round" '
                  f'stroke-linejoin="round" opacity="{st:.3f}"/>')
        elif wait > 0.05:  # a person waiting to approve
            f.add(f'<g opacity="{wait:.3f}" fill="{SLATE}"><circle cx="{ix:.1f}" cy="{cy - 4:.1f}" r="3.6"/>'
                  f'<path d="M{ix - 6:.1f},{cy + 7:.1f} a6,6 0 0 1 12,0 Z"/></g>')


def lock(f, cx, cy, a, open_s, green):
    col = mix(mix(GHOST_STROKE, SLATE, a), GREEN, green)
    body = mix("#FFFFFF", KINDS["ok"][0], green)
    lift = 6 * open_s
    if a > 0:
        f.add(f'<circle cx="{cx}" cy="{cy}" r="26" fill="{mix("#FFFFFF", "#EEF3FB", a)}" '
              f'opacity="{0.9 * a * (1 - green) + 0.0:.3f}"/>')
    f.add(f'<path d="M{cx - 6.5},{cy - 6 - lift:.1f} V{cy - 11 - lift:.1f} '
          f'A6.5,6.5 0 0 1 {cx + 6.5},{cy - 11 - lift:.1f} V{cy - 6 - lift * 0.2:.1f}" '
          f'fill="none" stroke="{col}" stroke-width="2.6" stroke-linecap="round"/>')
    f.add(f'<rect x="{cx - 11}" y="{cy - 6}" width="22" height="17" rx="4" fill="{body}" '
          f'stroke="{col}" stroke-width="2.4"/>')
    f.add(f'<circle cx="{cx}" cy="{cy + 2.5}" r="2.2" fill="{col}"/>')


# ── one frame of the story ─────────────────────────────────────────────────
def scene_index(t):
    idx = 0
    for i, (_, start, *_rest) in enumerate(SCENES):
        if t >= start:
            idx = i
    return idx


def draw(t: float) -> str:
    f = Frame()

    # header
    f.text(40, 54, "The path to production", 28, 700, INK)
    f.text(40, 84, "One release of a Hello World Java Lambda, from commit to production",
           16, 400, MUTED)
    f.text(1160, 54, "github.com/riteshbangal/aws-cdk-path-to-production", 13, 500, MUTED,
           "end", MONO)

    # zones
    for (x0, x1), tint, label in ((Z1, "ci", "GITHUB"), (Z2, "support", "RELEASE"),
                                  (Z3, "aws", "AWS")):
        f.rect(x0, 112, x1 - x0, 500, TINTS[tint], r=16, sw=0)
        f.text(x0 + 20, 141, label, 13, 700, MUTED, spacing=1.4)

    # ── arrows (behind everything that moves) ──
    arrow(f, P_GH_INFRA, ease(prog(t, 4.2, 5.0)))
    arrow(f, P_GH_APP, ease(prog(t, 4.2, 5.0)))
    arrow(f, P_APP_ART, ease(prog(t, 8.4, 9.6)))
    arrow(f, P_ART_CDK, ease(prog(t, 11.9, 12.7)))
    arrow(f, P_CDK_TPL, ease(prog(t, 12.9, 13.3)))
    arrow(f, P_TPL_DEV, max(LOCK_FRAC * ease(prog(t, 16.0, 17.0)), ease(prog(t, 19.3, 20.2))))
    arrow(f, P_DEV_QA, ease(prog(t, 21.4, 22.1)))
    arrow(f, P_QA_PROD, ease(prog(t, 24.6, 25.3)))

    # ── GitHub zone ──
    node(f, GH, "code", "GitHub", [dict(text="Java app + Java CDK code")],
         on(t, 1.4), window(t, 1.4, 4.2))
    node(f, INFRA, "ci", "Infra CI", [dict(text="test · synth · lint", size=13)],
         on(t, 4.8), window(t, 4.8, 8.0), line_size=13)
    node(f, APP, "ci", "App CI", [dict(text="build · test · JAR", size=13)],
         on(t, 4.8), window(t, 4.8, 8.6), line_size=13)
    for box in (INFRA, APP):
        bar(f, box, ease(prog(t, 5.0, 6.2)), "ci", window(t, 5.0, 6.3, 0.2))
    badge(f, INFRA[0] + INFRA[2] - 4, R2 + 4, pop(t, 6.2))
    badge(f, APP[0] + APP[2] - 4, R2 + 4, pop(t, 6.3))
    chip(f, 294, R2 + NH, "tag v1.2.3", "outline", op=on(t, 8.0, 0.2), scale=pop(t, 8.0), size=12)
    a = on(t, 6.5)
    pill(f, 208, 462, 196, "checks passed", a, op=a, h=34)
    f.text(208, 506, "no AWS access in CI", 14, 500, MUTED, "middle", op=a)

    # ── Release zone ──
    node(f, ART, "support", "Artifactory",
         [dict(text="hello-world-lambda 1.2.3", font=MONO, size=13, color=SLATE),
          dict(text="immutable · SHA-256", alpha=on(t, 9.8))],
         on(t, 9.4), window(t, 9.4, 11.9))
    chip(f, 647, (R1 + NH + R2) / 2, "pin 1.2.3 + sha256", "pin",
         op=on(t, 11.5, 0.25), scale=pop(t, 11.5), size=11)
    node(f, CDK, "code", "AWS CDK (Java)",
         [dict(text="GreetingApiStack", font=MONO, size=13, color=SLATE),
          dict(text="cdk synth · once", alpha=on(t, 12.7))],
         on(t, 12.5), window(t, 12.5, 15.5))
    a_tpl = on(t, 13.2)
    x, y, w, h = TPL
    ring = window(t, 13.2, 17.0)
    if ring > 0:
        f.rect(x - 6, y - 6, w + 12, h + 12, "none", SLATE, r=17, sw=3, op=0.32 * ring)
    f.rect(x, y, w, h, mix(GHOST_FILL, KINDS["code"][0], a_tpl), mix(GHOST_STROKE, SLATE, a_tpl))
    f.text(x + w / 2, y + 29, "CloudFormation", 20, 600, mix(GHOST_TEXT, INK, a_tpl), "middle")
    for i, (lbl, at) in enumerate((("dev", 13.4), ("qa", 13.7), ("prod", 14.0))):
        sheet(f, 488 + i * 66, y + 42, lbl, on(t, at, 0.2), pop(t, at))

    # ── the AWS boundary: OIDC sign-in ──
    a_lock = on(t, 15.9)
    open_s = ease(prog(t, 17.0, 17.4))
    lock(f, LOCK[0], LOCK[1], a_lock, open_s, open_s)
    f.text(LOCK[0], LOCK[1] - 26, "OIDC", 13, 700, mix(GHOST_TEXT, SLATE, a_lock), "middle",
           spacing=0.6)
    c = on(t, 17.4)
    f.text(LOCK[0], LOCK[1] + 36, "1-hour", 12, 600, GREEN_DARK, "middle", op=c)
    f.text(LOCK[0], LOCK[1] + 51, "credentials", 12, 600, GREEN_DARK, "middle", op=c)

    # ── AWS zone ──
    node(f, FOUND, "support", "Foundation · set up once",
         [dict(text="CDK bootstrap + OIDC deploy role", size=13)],
         on(t, 15.5), window(t, 15.5, 19.3), title_size=15, line_size=13)
    node(f, DEV, "aws", "Dev", [dict(text="API Gateway → Lambda")],
         on(t, 20.1), window(t, 20.1, 21.4))
    bar(f, DEV, ease(prog(t, 20.3, 21.1)), "aws", window(t, 20.3, 21.2, 0.2))
    node(f, QA, "aws", "QA", [dict(text="API Gateway → Lambda")],
         on(t, 22.0), window(t, 22.0, 24.6))
    bar(f, QA, ease(prog(t, 22.2, 23.0)), "aws", window(t, 22.2, 23.1, 0.2))
    node(f, PROD, "aws", "Prod",
         [dict(text="API Gateway → Lambda", swap=on(t, 26.2),
               alt="GET /hello → Hello, World!", alt_color=GREEN_DARK, alt_font=MONO,
               alt_size=13)],
         on(t, 25.2), window(t, 25.2, 28.1))
    bar(f, PROD, ease(prog(t, 25.4, 26.2)), "aws", window(t, 25.4, 26.3, 0.2))
    badge(f, PROD[0] + PROD[2] - 4, R1 + 4, pop(t, 26.2))

    pill(f, CX3, (R2 + NH + R3) / 2, 156, "smoke test", on(t, 21.1, 0.3))
    # Prod's gate has two posts: QA's tests, then a person's approval.
    # While the reviewer decides, the dashed outline marches.
    split_pill(f, CX3, (R1 + NH + R2) / 2,
               [("tests", on(t, 23.0, 0.3), 0.0),
                ("approval", on(t, 24.4, 0.3), on(t, 23.2, 0.2) * (1 - on(t, 24.4, 0.3)))],
               dashoff=-30 * t)

    # ── moving tokens (on top) ──
    k = prog(t, 1.4, 2.2)
    if 0 < k < 1:
        chip(f, 208, 100 + 58 * ease(k), "git push", "slate", op=min(k / 0.25, (1 - k) / 0.35, 1))
    k = prog(t, 4.2, 5.0)
    if 0 < k < 1:
        for pts in (P_GH_INFRA, P_GH_APP):
            px, py = along(pts, ease(k))
            f.add(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="{BLUE}" stroke="#FFFFFF" '
                  f'stroke-width="2.5" opacity="{min(k / 0.15, (1 - k) / 0.15, 1):.3f}"/>')
    for pts, a0, a1, label in ((P_APP_ART, 8.4, 9.6, "JAR 1.2.3"),
                               (P_ART_CDK, 11.9, 12.7, "JAR 1.2.3")):
        k = prog(t, a0, a1)
        if 0 < k < 1:
            px, py = along(pts, ease(k))
            chip(f, px, py, label, "navy", op=min(k / 0.2, (1 - k) / 0.2, 1))
    k = prog(t, 16.0, 17.0)
    if 0 < k < 1:
        px, py = along(P_TPL_DEV, LOCK_FRAC * 0.92 * ease(k))
        chip(f, px, py, "OIDC token", "blue", op=min(k / 0.25, (1 - k) / 0.15, 1), size=11)
    for pts, a0, a1 in ((P_TPL_DEV, 19.3, 20.2), (P_DEV_QA, 21.4, 22.1), (P_QA_PROD, 24.6, 25.3)):
        k = prog(t, a0, a1)
        if 0 < k < 1:
            px, py = along(pts, ease(k))
            chip(f, px, py, "1.2.3", "navy", op=min(k / 0.2, (1 - k) / 0.2, 1))

    # ── caption ──
    idx = scene_index(t)
    start = SCENES[idx][1]
    for i, alpha in ((idx, on(t, start + 0.05, 0.3)),
                     (idx - 1, 1 - on(t, start - 0.05, 0.15)) if idx > 0 else (None, 0)):
        if i is None or alpha <= 0.001:
            continue
        key, _, head, sentence = SCENES[i]
        numbered = 1 <= i <= 6
        tx = 98 if numbered else 40
        if numbered:
            f.add(f'<circle cx="60" cy="660" r="20" fill="{SLATE}" opacity="{alpha:.3f}"/>')
            f.text(60, 667, str(i), 19, 700, "#FFFFFF", "middle", op=alpha)
        f.text(tx, 656, head, 22, 700, INK, op=alpha)
        f.text(tx, 684, sentence, 17, 400, MUTED, op=alpha)

    # progress through the six steps
    seg_w, gap, x = (1120 - 5 * 10) / 6, 10, 40
    for i, name in enumerate(STEPS, start=1):
        s0, s1 = SCENES[i][1], SCENES[i + 1][1]
        fill = prog(t, s0, s1)
        f.rect(x, 710, seg_w, 5, "#E2E8F0", r=2.5, sw=0)
        if fill > 0:
            f.rect(x, 710, seg_w * fill, 5, BLUE if fill < 1 else SLATE, r=2.5, sw=0)
        current = s0 <= t < s1
        col = INK if current else (SLATE if t >= s1 else "#94A3B8")
        f.text(x + seg_w / 2, 738, name, 13, 700 if current else 500, col, "middle")
        x += seg_w + gap

    return f.svg()


def render(job):
    i, t, out = job
    cairosvg.svg2png(bytestring=draw(t).encode(), write_to=str(out / f"s{i:04d}.png"),
                     output_width=W, output_height=H)


def main():
    out_dir = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        encode(out_dir, Path(tmp))


def encode(out_dir: Path, frames: Path):

    # story frames
    n_story = int(round(STORY_END * FPS))
    with Pool() as pool:
        pool.map(render, [(i, i / FPS, frames) for i in range(n_story + 1)])

    # sequence: finished picture → fade to blank map → the story
    final = Image.open(frames / f"s{n_story:04d}.png").convert("RGB")
    start = Image.open(frames / "s0000.png").convert("RGB")
    seq = [final] * int(LEAD_HOLD * FPS)
    n_fade = int(LEAD_FADE * FPS)
    seq += [Image.blend(final, start, ease((k + 1) / n_fade)) for k in range(n_fade)]
    seq += [Image.open(frames / f"s{i:04d}.png").convert("RGB") for i in range(n_story + 1)]
    for i, im in enumerate(seq):
        im.save(frames / f"f{i:04d}.png")
    print(f"{len(seq)} frames, {len(seq) / FPS:.1f}s")

    gif = out_dir / "00-path-to-production.gif"
    mp4 = out_dir / "00-path-to-production.mp4"
    pattern = str(frames / "f%04d.png")
    palette = frames / "palette.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", pattern,
                    "-vf", "palettegen=max_colors=256:stats_mode=full", str(palette)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", pattern,
                    "-i", str(palette), "-lavfi", "paletteuse=dither=none:diff_mode=rectangle",
                    "-loop", "0", str(gif)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", pattern,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "slow",
                    "-movflags", "+faststart", str(mp4)], check=True)
    print(f"wrote {gif.name} ({gif.stat().st_size / 1e6:.2f} MB), "
          f"{mp4.name} ({mp4.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--still":
        # python3 animate.py --still 12.0 out.png   (one story moment, for checking)
        cairosvg.svg2png(bytestring=draw(float(sys.argv[2])).encode(),
                         write_to=sys.argv[3], output_width=W, output_height=H)
    else:
        main()
