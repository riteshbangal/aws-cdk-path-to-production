#!/usr/bin/env python3
"""Generates the six diagrams used in the README and the article.

    pip install cairosvg
    python3 docs/diagrams/generate.py

Writes <name>.svg (editable source) and <name>.png (2x, for Medium/DEV/Hashnode)
next to this file. The PNGs are rendered with the Inter font if it is installed.
"""

from __future__ import annotations

import math
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent
W = 800
FONT = "Inter, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, 'DejaVu Sans Mono', monospace"

INK = "#0F172A"      # headings
SLATE = "#334155"    # structure, arrows
MUTED = "#64748B"    # secondary text
HAIR = "#CBD5E1"     # faint lines

# kind -> (fill, stroke, title colour)
KINDS = {
    "code": ("#F8FAFC", "#334155", INK),       # navy/slate: our source code
    "ci": ("#EEF3FB", "#4A6FA5", "#1E3A66"),    # muted blue: CI/CD
    "aws": ("#FFF4E8", "#D9822B", "#7A3E06"),   # orange: AWS
    "ok": ("#ECF7F0", "#2E8B57", "#14532D"),    # green: validation passed
    "support": ("#F3F4F6", "#9CA3AF", SLATE),   # gray: supporting infra
    "stop": ("#FCEDEB", "#B54434", "#7F1D1D"),  # red: stop paths
    "manual": ("#FFFFFF", "#334155", INK),      # dashed: a human decision
}
TINTS = {"neutral": "#F8FAFC", "ci": "#F4F7FC", "aws": "#FFF8F0", "support": "#F6F7F9"}


class Diagram:
    def __init__(self, name: str, height: int, title: str, subtitle: str):
        self.name, self.h = name, height
        self.parts: list[str] = []
        self.text(40, 56, title, 30, 700, INK)
        self.text(40, 88, subtitle, 18, 400, MUTED)

    # primitives ----------------------------------------------------------
    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, size=18, weight=400, color=SLATE, anchor="start",
             font=FONT, spacing=0.0, italic=False):
        style = ' font-style="italic"' if italic else ""
        ls = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" '
                 f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{ls}{style}>'
                 f'{escape(s)}</text>')

    def rect(self, x, y, w, h, fill, stroke="none", r=12, sw=2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def zone(self, x, y, w, h, tint, label=None):
        self.rect(x, y, w, h, TINTS[tint], r=16, sw=0)
        if label:
            self.text(x + 20, y + 30, label, 13, 700, MUTED, spacing=1.4)

    def box(self, x, y, w, h, kind, title, subs=(), title_size=21, sub_size=16,
            mono_sub=False, dash=None, r=12):
        fill, stroke, tcolor = KINDS[kind]
        if kind == "manual" and dash is None:
            dash = "7 6"
        self.rect(x, y, w, h, fill, stroke, r=r, dash=dash)
        lines = [(title, title_size, 600, tcolor, FONT)]
        lines += [(s, sub_size, 400, MUTED, MONO if mono_sub else FONT) for s in subs]
        heights = [sz * 1.32 for _, sz, *_ in lines]
        cy = y + (h - sum(heights)) / 2
        for (s, sz, wt, col, fam), lh in zip(lines, heights):
            self.text(x + w / 2, cy + lh * 0.76, s, sz, wt, col, "middle", font=fam)
            cy += lh

    def pill(self, cx, y, w, h, kind, label, size=17, check=False):
        fill, stroke, tcolor = KINDS[kind]
        x = cx - w / 2
        self.rect(x, y, w, h, fill, stroke, r=h / 2, dash="7 6" if kind == "manual" else None)
        if check:
            tw = len(label) * size * 0.56
            ix = cx - tw / 2 - 14
            iy = y + h / 2
            self.add(f'<path d="M{ix - 7},{iy} l5,5 l9,-10" fill="none" stroke="{stroke}" '
                     f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
            self.text(cx + 8, y + h / 2 + size * 0.36, label, size, 600, tcolor, "middle")
        else:
            self.text(cx, y + h / 2 + size * 0.36, label, size, 600, tcolor, "middle")

    def arrow(self, pts, color=SLATE, dashed=False, label=None, label_at=None,
              label_anchor="middle", label_color=None, width=2.2, head=True, label_bg=None):
        pts = [tuple(p) for p in pts]
        if head:
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            ang = math.atan2(y2 - y1, x2 - x1)
            hl, hw = 12, 6.5
            bx, by = x2 - hl * math.cos(ang), y2 - hl * math.sin(ang)
            line_pts = pts[:-1] + [(bx, by)]
        else:
            line_pts = pts
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in line_pts)
        dash = ' stroke-dasharray="7 6"' if dashed else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
                 f'stroke-linejoin="round"{dash}/>')
        if head:
            px, py = -math.sin(ang), math.cos(ang)
            tri = [(x2, y2), (bx + hw * px, by + hw * py), (bx - hw * px, by - hw * py)]
            self.add('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in tri)
                     + f'" fill="{color}"/>')
        if label:
            lx, ly = label_at
            self.label(lx, ly, label, anchor=label_anchor, color=label_color or MUTED, bg=label_bg)

    def label(self, x, y, s, size=15, anchor="middle", color=MUTED, weight=500, bg="#FFFFFF"):
        tw = len(s) * size * 0.55 + 10
        if anchor == "middle":
            rx = x - tw / 2
        elif anchor == "start":
            rx = x - 5
        else:
            rx = x - tw + 5
        if bg:
            self.rect(rx, y - size * 0.95, tw, size * 1.35, bg, r=4, sw=0)
        self.text(x, y, s, size, weight, color, anchor)

    def footer(self, y, s, size=17):
        self.text(W / 2, y, s, size, 500, SLATE, "middle", italic=True)

    # output --------------------------------------------------------------
    def svg(self) -> str:
        body = "\n  ".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" '
                f'viewBox="0 0 {W} {self.h}">\n  <rect width="100%" height="100%" fill="#FFFFFF"/>\n'
                f'  {body}\n</svg>\n')

    def save(self) -> None:
        svg = self.svg()
        (OUT / f"{self.name}.svg").write_text(svg, encoding="utf-8")
        try:
            import cairosvg
            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT / f"{self.name}.png"),
                             output_width=W * 2, output_height=self.h * 2)
        except ImportError:
            print("cairosvg not installed: wrote SVG only")
        print(f"wrote {self.name}")


# 1 ─ hero ----------------------------------------------------------------
def d1_journey():
    d = Diagram("01-the-path-to-production", 1140, "The path to production",
                "One commit, one released artifact, three environments")
    A, B, CW = 40, 440, 320          # two-column grid
    ca, cb = A + CW / 2, B + CW / 2

    d.zone(20, 112, 760, 136, "neutral", "DEVELOP")
    d.box(A, 156, CW, 72, "code", "Developer", ["Java app + Java CDK code"])
    d.box(B, 156, CW, 72, "code", "GitHub", ["pull request · merge · tag"])
    d.arrow([(A + CW, 192), (B, 192)], label="push", label_at=(400, 182))

    d.zone(20, 266, 760, 170, "ci", "CI")
    d.arrow([(cb, 228), (cb, 312)])
    d.add(f'<circle cx="{cb}" cy="257" r="4" fill="{SLATE}"/>')
    d.arrow([(cb, 257), (ca, 257), (ca, 312)])
    d.box(A, 312, CW, 80, "ci", "App CI", ["build · test · package JAR"])
    d.box(B, 312, CW, 80, "ci", "Infra CI", ["test · synth · lint templates"])
    d.text(cb, 420, "checks only · nothing reaches AWS", 15, 600, KINDS["ok"][1], "middle")

    d.zone(20, 454, 760, 156, "support", "ARTIFACTS")
    d.arrow([(ca, 392), (ca, 494)], label="on tag v1.2.3", label_at=(ca + 12, 424),
            label_anchor="start")
    d.box(A, 494, CW, 96, "support", "Artifactory",
          ["hello-world-lambda 1.2.3", "immutable · SHA-256"])
    d.text(cb, 532, "Build once.", 18, 600, SLATE, "middle")
    d.text(cb, 558, "Every environment deploys", 17, 400, MUTED, "middle")
    d.text(cb, 581, "these exact bytes.", 17, 400, MUTED, "middle")

    d.zone(20, 628, 760, 152, "neutral", "IaC")
    d.arrow([(ca, 590), (ca, 668)], label="pinned JAR", label_at=(ca + 12, 642),
            label_anchor="start")
    d.box(A, 668, CW, 80, "code", "AWS CDK (Java)", ["GreetingApiStack"])
    d.box(B, 668, CW, 80, "code", "CloudFormation", ["templates for dev · qa · prod"])
    d.arrow([(A + CW, 708), (B, 708)], label="cdk synth", label_at=(400, 698))

    d.zone(20, 798, 760, 290, "aws", "DEPLOY & PROMOTE")
    xs = [40, 300, 560]
    envs = [("Dev", "automatic"), ("QA", "automatic"), ("Prod", "after approval")]
    d.arrow([(cb, 748), (cb, 832)], head=False)
    d.arrow([(xs[0] + 100, 832), (xs[2] + 100, 832)], head=False)
    for x in xs:
        d.arrow([(x + 100, 832), (x + 100, 872)])
    d.label(cb - 14, 818, "cdk deploy · same templates", anchor="end", color=MUTED, bg=None)
    for x, (env, when) in zip(xs, envs):
        d.box(x, 872, 200, 96, "aws", env, ["API Gateway → Lambda", when], sub_size=15)
    d.arrow([(240, 920), (300, 920)])
    d.arrow([(500, 920), (560, 920)])
    d.pill(270, 990, 140, 38, "ok", "smoke", size=15, check=True)
    d.pill(530, 990, 140, 38, "ok", "tests", size=15, check=True)
    d.pill(530, 1036, 140, 38, "manual", "approval", size=15)
    d.add(f'<path d="M270,940 L270,990" stroke="{HAIR}" stroke-width="2"/>')
    d.add(f'<path d="M530,940 L530,990" stroke="{HAIR}" stroke-width="2"/>')
    d.footer(1118, "The app is Hello World. The value is the path that delivers it.")
    d.save()


# 2 ─ app vs infra --------------------------------------------------------
def d2_two_kinds_of_code():
    d = Diagram("02-two-kinds-of-code", 830, "Two kinds of code, one application",
                "They change for different reasons, so they build separately")
    d.zone(20, 116, 370, 448, "ci")
    d.zone(410, 116, 370, 448, "neutral")
    d.text(40, 148, "APPLICATION", 13, 700, MUTED, spacing=1.4)
    d.text(40, 172, "app/", 16, 500, SLATE, font=MONO)
    d.text(430, 148, "INFRASTRUCTURE", 13, 700, MUTED, spacing=1.4)
    d.text(430, 172, "infrastructure/", 16, 500, SLATE, font=MONO)

    AX, BX, BW = 55, 445, 300
    rows = [196, 322, 448]
    d.box(AX, rows[0], BW, 84, "code", "HelloHandler.java", ["returns \"Hello, World!\""])
    d.box(AX, rows[1], BW, 84, "ci", "Gradle", ["compile · unit tests · package"])
    d.box(AX, rows[2], BW, 84, "ci", "Lambda JAR", ["versioned, built once"])
    d.box(BX, rows[0], BW, 84, "code", "GreetingApiStack.java", ["Lambda · API Gateway · logs"])
    d.box(BX, rows[1], BW, 84, "code", "cdk synth", ["runs the Java, writes files"])
    d.box(BX, rows[2], BW, 84, "code", "CloudFormation", ["template + packaged assets"])
    for x in (AX + BW / 2, BX + BW / 2):
        d.arrow([(x, rows[0] + 84), (x, rows[1])])
        d.arrow([(x, rows[1] + 84), (x, rows[2])])

    d.arrow([(AX + BW / 2, 532), (AX + BW / 2, 640)], label="the JAR",
            label_at=(AX + BW / 2 + 12, 600), label_anchor="start")
    d.arrow([(BX + BW / 2, 532), (BX + BW / 2, 640)], label="the template",
            label_at=(BX + BW / 2 + 12, 600), label_anchor="start")
    d.box(100, 640, 600, 104, "aws", "cdk deploy → AWS",
          ["CloudFormation creates API Gateway + Lambda,", "and the Lambda runs the JAR"])
    d.footer(800, "They meet only at deployment, through a pinned, versioned JAR.")
    d.save()


# 3 ─ three pipelines -----------------------------------------------------
def d3_three_pipelines():
    d = Diagram("03-three-pipelines", 820, "Three pipelines, three jobs",
                "Two pipelines check. Only one changes AWS.")
    d.zone(20, 112, 496, 616, "ci", "CHECKS · NO AWS ACCESS")
    d.zone(532, 112, 248, 616, "aws", "CHANGES AWS")
    cols = [
        (36, "App CI", "app-ci.yml", "ci",
         ["Commit or tag", "Build + unit tests", "Package JAR", "Publish (tags only)"],
         ("support", "Artifactory", False)),
        (280, "Infra CI", "infra-ci.yml", "ci",
         ["Infra change", "Test CDK code", "Get pinned JAR", "Synth all envs", "cfn-lint"],
         ("ok", "Valid templates", True)),
        (546, "Release", "release.yml", "aws",
         ["Get pinned JAR", "Synthesize once", "Sign in (OIDC)", "cdk deploy", "Smoke test"],
         ("ok", "Running API", True)),
    ]
    for x, title, file, kind, steps, (okind, out, chk) in cols:
        cx = x + 110
        d.text(cx, 176, title, 21, 700, INK, "middle")
        d.text(cx, 200, file, 14, 500, MUTED, "middle", font=MONO)
        y = 222
        for i, s in enumerate(steps):
            d.box(x, y, 220, 56, kind, s, title_size=18)
            y += 56
            d.arrow([(cx, y), (cx, y + 26)])
            y += 26
        d.pill(cx, y, 200, 48, okind, out, size=17, check=chk)
        if out == "Artifactory":
            d.text(cx, y + 74, "read by Infra CI", 14, 500, MUTED, "middle")
            d.text(cx, y + 94, "and Release", 14, 500, MUTED, "middle")
    d.footer(776, "A green check proves the templates are valid, not that a deploy will work.", 16)
    d.save()


# 4 ─ bootstrap -----------------------------------------------------------
def d4_bootstrap():
    d = Diagram("04-cdk-bootstrap", 880, "CDK bootstrap: the foundation",
                "Prepared once per account and region. Every deploy stands on it.")
    d.zone(20, 112, 760, 312, "support", "FOUNDATION · ONCE PER ACCOUNT + REGION")
    d.box(40, 160, 260, 70, "support", "cdk bootstrap", ["run by a platform admin"], sub_size=15)
    d.box(440, 160, 320, 70, "support", "CDKToolkit stack", ["a CloudFormation stack"], sub_size=15)
    d.arrow([(300, 195), (440, 195)], label="creates", label_at=(370, 185))
    tiles = [("S3 bucket", ["JAR + templates"]), ("IAM roles", ["deploy · publish", "execute"]),
             ("ECR repo", ["images (unused here)"]), ("SSM param", ["bootstrap version"])]
    tx = [40, 225, 410, 595]
    d.arrow([(600, 230), (600, 262)], head=False)
    d.arrow([(tx[0] + 82.5, 262), (tx[3] + 82.5, 262)], head=False)
    for x, (t, subs) in zip(tx, tiles):
        d.arrow([(x + 82.5, 262), (x + 82.5, 294)])
        d.box(x, 294, 165, 100, "support", t, subs, title_size=19, sub_size=14)

    d.zone(20, 470, 760, 300, "aws", "APPLICATION · EVERY RELEASE")
    d.arrow([(tx[0] + 82.5, 394), (tx[0] + 82.5, 448)], color=MUTED, dashed=True, head=False)
    d.arrow([(tx[1] + 82.5, 394), (tx[1] + 82.5, 448)], color=MUTED, dashed=True, head=False)
    d.arrow([(tx[0] + 82.5, 448), (415, 448), (415, 520)], color=MUTED, dashed=True)
    d.label(tx[1] + 82.5 + 16, 441, "uses the bucket + roles", anchor="start", size=14)
    d.box(40, 520, 250, 70, "code", "GreetingApiStack", ["our Java CDK code"], sub_size=15)
    d.box(330, 520, 170, 70, "aws", "cdk deploy")
    d.box(560, 520, 200, 70, "aws", "CloudFormation")
    d.arrow([(290, 555), (330, 555)])
    d.arrow([(500, 555), (560, 555)])
    d.box(560, 660, 200, 80, "aws", "Your API", ["API Gateway → Lambda"], title_size=20, sub_size=15)
    d.arrow([(660, 590), (660, 660)], label="creates", label_at=(672, 632),
            label_anchor="start", )
    d.footer(822, "Bootstrap prepares the machinery. cdk deploy builds the application.")
    d.save()


# 5 ─ OIDC ----------------------------------------------------------------
def d5_oidc():
    d = Diagram("05-github-to-aws-oidc", 930, "Signing in to AWS without stored keys",
                "GitHub vouches for the job. AWS hands out a one-hour pass.")
    JX, JW = 40, 240
    RX, RW = 480, 280
    d.box(JX, 128, JW, 272, "ci", "GitHub Actions job", ["environment: dev"],
          title_size=19, sub_size=16)
    d.box(RX, 128, RW, 96, "support", "GitHub OIDC issuer", ["signs an identity token"])
    d.box(RX, 304, RW, 96, "aws", "AWS STS", ["security token service"])
    d.box(RX, 452, RW, 96, "aws", "IAM deploy role", ["one per environment"])

    def num(cx, cy, n):
        d.add(f'<circle cx="{cx}" cy="{cy}" r="13" fill="{SLATE}"/>')
        d.text(cx, cy + 5.5, str(n), 15, 700, "#FFFFFF", "middle")

    L, R, NX, TX = JX + JW, RX, 306, 326
    d.arrow([(L, 156), (R, 156)]); num(NX, 156, 1)
    d.text(TX, 146, "request a token", 15, 500, MUTED)
    d.arrow([(R, 196), (L, 196)]); num(NX, 196, 2)
    d.text(TX, 220, "signed token (JWT)", 15, 500, MUTED)
    d.arrow([(L, 332), (R, 332)]); num(NX, 332, 3)
    d.text(TX, 322, "exchange token", 15, 500, MUTED)
    d.arrow([(R, 372), (L, 372)], color=KINDS["ok"][1]); num(NX, 372, 5)
    d.text(TX, 396, "1-hour credentials", 15, 600, KINDS["ok"][1])
    d.arrow([(RX + RW / 2, 400), (RX + RW / 2, 452)])
    num(RX + RW / 2 - 24, 426, 4)
    d.text(RX + RW / 2 + 14, 431, "check trust policy", 15, 500, MUTED)
    d.arrow([(JX + JW / 2, 400), (JX + JW / 2, 484)])
    d.box(JX, 484, JW, 64, "aws", "cdk deploy", title_size=20)

    d.rect(40, 584, 720, 140, "#FFFFFF", HAIR, r=12)
    d.text(64, 618, "The role's trust policy accepts only this token:", 16, 600, INK)
    rows = [("iss", "token.actions.githubusercontent.com"), ("aud", "sts.amazonaws.com"),
            ("sub", "repo:owner@id/repo@id:environment:dev")]
    for i, (k, v) in enumerate(rows):
        y = 652 + i * 26
        d.text(64, y, k, 15, 700, MUTED, font=MONO)
        d.text(112, y, v, 15, 500, SLATE, font=MONO)

    d.pill(400, 752, 720, 46, "ok", "No long-lived AWS keys stored in GitHub", size=17, check=True)
    d.rect(40, 820, 720, 70, "#FFFFFF", HAIR, r=12, dash="5 5")
    d.text(400, 849, "Separate decision: where the job runs.", 16, 600, SLATE, "middle")
    d.text(400, 874, "GitHub-hosted or self-hosted runners can both sign in this way.",
           15, 400, MUTED, "middle")
    d.save()


# 6 ─ promotion -----------------------------------------------------------
def d6_promotion():
    d = Diagram("06-promotion-gates", 1220, "Promotion: each environment earns the next",
                "Same JAR, same templates. Gates decide how far a release goes.")
    CX, MW = 400, 360
    MX = CX - MW / 2
    SX, SW = 628, 140

    def down(y1, y2, label=None):
        d.arrow([(CX, y1), (CX, y2)], label=label, label_at=(CX + 12, (y1 + y2) / 2 + 6),
                label_anchor="start", label_color=KINDS["ok"][1])

    def stop(y_mid, gate_right, text, sub=None, label="fail", below=False):
        d.arrow([(gate_right, y_mid), (SX, y_mid)], color=KINDS["stop"][1],
                label=label, label_at=((gate_right + SX) / 2, y_mid + (22 if below else -9)),
                label_color=KINDS["stop"][1])
        d.box(SX, y_mid - 30, SW, 60, "stop", text, [sub] if sub else (), title_size=17,
              sub_size=13)

    def side(y, s):
        d.text(MX - 16, y, s, 14, 600, MUTED, "end")

    d.box(MX, 120, MW, 96, "code", "Release 1.2.3",
          ["pinned JAR + SHA-256", "templates synthesized once"])
    down(216, 256)
    d.box(MX, 256, MW, 64, "aws", "Deploy Dev", title_size=20); side(294, "automatic")
    down(320, 356)
    d.pill(CX, 356, 260, 52, "ok", "Smoke test", check=True)
    stop(382, CX + 130, "Stop", "investigate")
    down(408, 456, "pass")
    d.box(MX, 456, MW, 64, "aws", "Deploy QA", title_size=20); side(494, "automatic")
    down(520, 556)
    d.pill(CX, 556, 300, 52, "ok", "Smoke + integration", check=True)
    stop(582, CX + 150, "Stop", "investigate")
    down(608, 656, "pass")
    d.box(MX, 656, MW, 64, "manual", "Production approval", title_size=20)
    side(694, "a person")
    stop(688, MX + MW, "Stop", label="reject", below=True)
    down(720, 768, "approve")
    d.box(MX, 768, MW, 64, "aws", "Deploy Prod", title_size=20); side(806, "after approval")
    down(832, 868)
    d.pill(CX, 868, 300, 52, "ok", "Smoke test + alarms", check=True)
    stop(894, CX + 150, "Incident", "rollback runbook")
    down(920, 968, "pass")
    d.pill(CX, 968, MW, 56, "ok", "Release complete", size=19)

    ly = 1072
    items = [("aws", "automated deploy"), ("ok", "gate"), ("manual", "human decision"),
             ("stop", "stop")]
    lx = 70
    for kind, s in items:
        fill, stroke, _ = KINDS[kind]
        d.rect(lx, ly - 16, 28, 20, fill, stroke, r=5, dash="5 4" if kind == "manual" else None)
        d.text(lx + 38, ly, s, 15, 500, SLATE)
        lx += 38 + len(s) * 8.6 + 34
    d.footer(1136, "A failed gate stops promotion. It doesn't roll back what's deployed.")
    d.footer(1166, "Build once, deploy many: no environment gets a rebuilt artifact.", 16)
    d.save()


if __name__ == "__main__":
    d1_journey()
    d2_two_kinds_of_code()
    d3_three_pipelines()
    d4_bootstrap()
    d5_oidc()
    d6_promotion()
