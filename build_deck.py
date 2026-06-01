"""Build LBG PCW Competitive Intelligence deck as a .pptx file."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree
import copy

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x0A, 0x16, 0x28)
BLUE   = RGBColor(0x1B, 0x3A, 0x6B)
MID    = RGBColor(0x25, 0x63, 0xAB)
ACCENT = RGBColor(0x0F, 0x7A, 0xC5)
TEAL   = RGBColor(0x0D, 0x94, 0x88)
GOLD   = RGBColor(0xC9, 0xA8, 0x4C)
LIGHT  = RGBColor(0xF4, 0xF6, 0xFA)
WARM   = RGBColor(0xE8, 0xED, 0xF5)
BORDER = RGBColor(0xCB, 0xD5, 0xE1)
TEXT   = RGBColor(0x1E, 0x29, 0x3B)
SUB    = RGBColor(0x47, 0x55, 0x69)
MUTED  = RGBColor(0x94, 0xA3, 0xB8)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
PURPLE = RGBColor(0x7C, 0x3A, 0xED)
GREEN  = RGBColor(0x05, 0x96, 0x69)
RED    = RGBColor(0xDC, 0x26, 0x26)
AMBER  = RGBColor(0xC9, 0xA8, 0x4C)

# Slide size: widescreen 13.33 × 7.5 in
W = Inches(13.33)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

blank_layout = prs.slide_layouts[6]  # completely blank

# ── Low-level helpers ─────────────────────────────────────────────────────────

def add_rect(slide, x, y, w, h, fill_rgb=None, line_rgb=None, line_pt=0.75):
    from pptx.util import Pt
    shape = slide.shapes.add_shape(1, x, y, w, h)  # MSO_SHAPE_TYPE.RECTANGLE
    shape.line.fill.background()
    if fill_rgb:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_rgb
    else:
        shape.fill.background()
    if line_rgb:
        shape.line.color.rgb = line_rgb
        shape.line.width = Pt(line_pt)
    else:
        shape.line.fill.background()
    return shape


def add_textbox(slide, x, y, w, h, text, font_size=10, bold=False, italic=False,
                color=TEXT, align=PP_ALIGN.LEFT, wrap=True, font_name="Calibri"):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font_name
    return tb


def add_para(tf, text, font_size=10, bold=False, italic=False,
             color=TEXT, align=PP_ALIGN.LEFT, space_before=0, font_name="Calibri"):
    p = tf.add_paragraph()
    p.alignment = align
    if space_before:
        p.space_before = Pt(space_before)
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font_name
    return p


def slide_header(slide, eyebrow, title, eyebrow_color=ACCENT):
    """Standard page header with eyebrow + title + gold rule."""
    # Left accent stripe
    add_rect(slide, Inches(0), Inches(0), Inches(0.07), H, fill_rgb=NAVY)
    # Footer bar
    add_rect(slide, Inches(0), H - Inches(0.07), W, Inches(0.07), fill_rgb=MID)

    add_textbox(slide, Inches(0.5), Inches(0.3), Inches(12), Inches(0.25),
                eyebrow, font_size=8, bold=True, color=eyebrow_color)
    add_textbox(slide, Inches(0.5), Inches(0.55), Inches(12), Inches(0.45),
                title, font_size=20, bold=True, color=NAVY)
    # Gold rule
    add_rect(slide, Inches(0.5), Inches(1.05), Inches(0.5), Inches(0.04), fill_rgb=GOLD)


def slide_number(slide, n, total=16):
    add_textbox(slide, W - Inches(1.1), H - Inches(0.35), Inches(1.0), Inches(0.25),
                f"{n:02d} / {total}", font_size=8, color=MUTED, align=PP_ALIGN.RIGHT)


def card(slide, x, y, w, h, top_color, bg_color=LIGHT):
    add_rect(slide, x, y, w, h, fill_rgb=bg_color, line_rgb=BORDER, line_pt=0.5)
    add_rect(slide, x, y, w, Inches(0.05), fill_rgb=top_color)


def bullet_tf(slide, x, y, w, h, items, font_size=10, color=SUB, bullet_color=ACCENT):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(2)
        run = p.add_run()
        run.text = f"–  {item}"
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        run.font.name = "Calibri"
    return tb


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Cover
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)

# Navy background (full)
add_rect(s, 0, 0, W, H, fill_rgb=NAVY)

# Gold top bar
add_rect(s, 0, 0, W, Inches(0.08), fill_rgb=GOLD)

# Left accent block (decorative)
add_rect(s, 0, 0, Inches(0.08), H, fill_rgb=GOLD)

# Subtle mid-blue panel on right
add_rect(s, Inches(9.2), Inches(0.08), Inches(4.13), H - Inches(0.08), fill_rgb=BLUE)

# Organisation label
add_textbox(s, Inches(0.5), Inches(0.55), Inches(8.5), Inches(0.3),
            "LLOYDS BANKING GROUP  ·  GENERAL INSURANCE",
            font_size=8, bold=True, color=GOLD)

# Main title
tb = s.shapes.add_textbox(Inches(0.5), Inches(1.1), Inches(8.4), Inches(1.8))
tf = tb.text_frame
tf.word_wrap = True
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.LEFT
r1 = p.add_run(); r1.text = "PCW Competitive Intelligence\n& Optimisation Platform"
r1.font.size = Pt(34); r1.font.bold = True; r1.font.color.rgb = WHITE
r1.font.name = "Calibri"

# Gold divider
add_rect(s, Inches(0.5), Inches(3.05), Inches(0.7), Inches(0.05), fill_rgb=GOLD)

# Sub-title
add_textbox(s, Inches(0.5), Inches(3.2), Inches(8.3), Inches(0.35),
            "Transforming Market Monitoring into Continuous Competitive Advantage",
            font_size=12, color=MUTED, italic=True)

# Pills row
pill_labels = ["Agentic Intelligence", "Human-Governed Decisioning", "Closed-Loop Optimisation"]
px = Inches(0.5)
for lbl in pill_labels:
    pw = Inches(2.2)
    r = add_rect(s, px, Inches(3.75), pw, Inches(0.32), fill_rgb=None)
    r.line.color.rgb = MUTED
    r.line.width = Pt(0.75)
    r.fill.background()
    add_textbox(s, px + Inches(0.1), Inches(3.79), pw - Inches(0.2), Inches(0.25),
                lbl, font_size=8.5, color=MUTED, align=PP_ALIGN.CENTER)
    px += pw + Inches(0.15)

# Executive message box
add_rect(s, Inches(0.5), Inches(4.35), Inches(8.3), Inches(0.85),
         fill_rgb=RGBColor(0x12, 0x22, 0x3F))
add_rect(s, Inches(0.5), Inches(4.35), Inches(0.06), Inches(0.85), fill_rgb=GOLD)
add_textbox(s, Inches(0.7), Inches(4.42), Inches(8.0), Inches(0.72),
            "Move from periodic competitor reviews to continuous market sensing, intelligence generation "
            "and optimisation recommendations across all Price Comparison Website channels.",
            font_size=10.5, color=RGBColor(0xCC, 0xD6, 0xE8), italic=True)

# Right panel content
add_textbox(s, Inches(9.4), Inches(1.2), Inches(3.6), Inches(0.3),
            "DELIVERY TIMELINE", font_size=8, bold=True, color=GOLD)
waves = [("Wave 1", "Market Visibility", "Months 1–3"),
         ("Wave 2", "Intelligence",       "Months 4–6"),
         ("Wave 3", "Decision Support",   "Months 7–9"),
         ("Wave 4", "Optimisation",       "Months 10–12")]
wy = Inches(1.6)
for wv, wt, wm in waves:
    add_rect(s, Inches(9.4), wy, Inches(3.6), Inches(0.62),
             fill_rgb=RGBColor(0x14, 0x28, 0x4A), line_rgb=RGBColor(0x1B, 0x3A, 0x6B), line_pt=0.5)
    add_textbox(s, Inches(9.5), wy + Inches(0.06), Inches(1.0), Inches(0.22),
                wv, font_size=7.5, bold=True, color=GOLD)
    add_textbox(s, Inches(9.5), wy + Inches(0.26), Inches(2.5), Inches(0.22),
                wt, font_size=9.5, bold=True, color=WHITE)
    add_textbox(s, Inches(9.5), wy + Inches(0.44), Inches(2.5), Inches(0.18),
                wm, font_size=8, color=MUTED)
    wy += Inches(0.7)

slide_number(s, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Executive Summary
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "EXECUTIVE SUMMARY", "Strategic Context & Recommendation")

cols = [
    (ACCENT, LIGHT, "THE OPPORTUNITY",
     "PCWs remain a primary acquisition channel",
     "Price Comparison Websites continue to shape customer acquisition at scale, creating significant leverage for firms that can optimise positioning effectively."),
    (MID, LIGHT, "THE CHALLENGE",
     "Responses are fragmented and reactive",
     "Manual, periodic reviews are unable to keep pace with the velocity and complexity of market movements across all PCW channels simultaneously."),
    (NAVY, NAVY, "THE RECOMMENDATION",
     "Establish an Agentic AI-powered Platform",
     "Continuously monitor, analyse and recommend actions across pricing, product and proposition — governed by human oversight at every decision point."),
]
cx = Inches(0.5)
cw = Inches(4.1)
for top_c, bg, lbl, title, body in cols:
    card(s, cx, Inches(1.25), cw, Inches(3.6), top_c, bg)
    lbl_c = ACCENT if bg == LIGHT else GOLD
    title_c = NAVY if bg == LIGHT else WHITE
    body_c = SUB if bg == LIGHT else RGBColor(0xCC, 0xD6, 0xE8)
    add_textbox(s, cx + Inches(0.18), Inches(1.38), cw - Inches(0.3), Inches(0.25),
                lbl, font_size=7.5, bold=True, color=lbl_c)
    add_textbox(s, cx + Inches(0.18), Inches(1.65), cw - Inches(0.3), Inches(0.55),
                title, font_size=13, bold=True, color=title_c)
    add_textbox(s, cx + Inches(0.18), Inches(2.3), cw - Inches(0.3), Inches(1.8),
                body, font_size=10.5, color=body_c)
    cx += cw + Inches(0.15)

# Outcomes row
add_textbox(s, Inches(0.5), Inches(5.0), Inches(3.0), Inches(0.25),
            "EXPECTED OUTCOMES", font_size=7.5, bold=True, color=MUTED)
outcomes = ["Improved PCW ranking visibility", "Faster competitor response",
            "Better-informed pricing decisions", "Reduced manual effort", "Reusable strategic capability"]
ox = Inches(0.5)
ow = Inches(2.45)
for oc in outcomes:
    add_rect(s, ox, Inches(5.3), ow, Inches(0.5),
             fill_rgb=WARM, line_rgb=TEAL, line_pt=0.5)
    add_rect(s, ox, Inches(5.3), Inches(0.05), Inches(0.5), fill_rgb=TEAL)
    add_textbox(s, ox + Inches(0.12), Inches(5.37), ow - Inches(0.18), Inches(0.38),
                oc, font_size=9, color=TEXT)
    ox += ow + Inches(0.1)

slide_number(s, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — Why This Matters
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "MARKET CONTEXT", "Why This Matters")

cards = [
    (ACCENT, "PCWs Drive Customer Acquisition",
     ["Price, excess and product features compared", "Optional add-ons influence decisions", "Brand perception shapes customer choice"]),
    (TEAL, "Ranking Position Drives Outcomes",
     ["Quote volumes sensitive to rank position", "Conversion rates materially affected", "New business growth directly at stake"]),
    (GOLD, "Market Dynamics Change Daily",
     ["Competitor pricing adjustments are frequent", "Offer and promotion changes are ongoing", "Product enhancements occur continuously"]),
    (RED, "Current Monitoring Cannot Scale",
     ["Manual processes lag market movement", "Analysis siloed across teams", "Response latency creates competitive risk"]),
]
positions = [(Inches(0.5), Inches(1.25)), (Inches(6.9), Inches(1.25)),
             (Inches(0.5),  Inches(4.1)),  (Inches(6.9), Inches(4.1))]
cw, ch = Inches(6.1), Inches(2.6)
for (cx, cy), (top_c, title, bullets) in zip(positions, cards):
    card(s, cx, cy, cw, ch, top_c)
    add_textbox(s, cx + Inches(0.2), cy + Inches(0.15), cw - Inches(0.3), Inches(0.35),
                title, font_size=12, bold=True, color=NAVY)
    bullet_tf(s, cx + Inches(0.2), cy + Inches(0.6), cw - Inches(0.3), Inches(1.7),
              bullets, font_size=10.5, color=SUB, bullet_color=top_c)

slide_number(s, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — Current State
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "CURRENT STATE ASSESSMENT", "How We Operate Today")

steps = [
    ("01", "Monitoring",   "Market reviews performed periodically across multiple PCWs"),
    ("02", "Analysis",     "Information collected manually, interpreted separately by teams"),
    ("03", "Decisions",    "Pricing changes initiated after trends become visible — often delayed"),
    ("04", "Execution",    "Multiple handoffs across pricing, product and operations"),
    ("05", "Outcome",      "Reactive response — unable to anticipate market shifts"),
]
sw = Inches(2.4)
sx = Inches(0.5)
for num, title, desc in steps:
    add_rect(s, sx, Inches(1.3), sw, Inches(3.2), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.5)
    add_textbox(s, sx + Inches(0.15), Inches(1.4), sw - Inches(0.25), Inches(0.5),
                num, font_size=28, bold=True, color=RGBColor(0xD1, 0xD9, 0xE8))
    add_textbox(s, sx + Inches(0.15), Inches(1.95), sw - Inches(0.25), Inches(0.35),
                title.upper(), font_size=9, bold=True, color=NAVY)
    add_rect(s, sx + Inches(0.15), Inches(2.32), Inches(0.35), Inches(0.03), fill_rgb=ACCENT)
    add_textbox(s, sx + Inches(0.15), Inches(2.4), sw - Inches(0.25), Inches(1.6),
                desc, font_size=10, color=SUB)
    # Arrow (except last)
    if num != "05":
        add_textbox(s, sx + sw - Inches(0.05), Inches(2.6), Inches(0.3), Inches(0.3),
                    "›", font_size=18, color=MUTED)
    sx += sw + Inches(0.15)

# Result box
add_rect(s, Inches(0.5), Inches(4.75), Inches(12.33), Inches(0.75),
         fill_rgb=RGBColor(0xFE, 0xF3, 0xC7), line_rgb=GOLD, line_pt=0.75)
add_rect(s, Inches(0.5), Inches(4.75), Inches(0.06), Inches(0.75), fill_rgb=GOLD)
add_textbox(s, Inches(0.7), Inches(4.83), Inches(2.0), Inches(0.3),
            "⚠  CURRENT RESULT", font_size=8.5, bold=True, color=RGBColor(0x92, 0x40, 0x0E))
add_textbox(s, Inches(2.9), Inches(4.85), Inches(9.8), Inches(0.5),
            "Reactive rather than proactive market response — competitive advantage ceded during monitoring gaps",
            font_size=11, color=RGBColor(0x78, 0x35, 0x0F), bold=True)

slide_number(s, 4)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — Strategic Hypothesis
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=LIGHT)
slide_header(s, "STRATEGIC RATIONALE", "The Strategic Hypothesis")

blocks = [
    (ACCENT, "IF",   "LBG continuously captures competitor market signals across all active PCW channels in real time"),
    (MID,    "AND",  "Automatically analyses ranking movement, pricing shifts and proposition changes using Agentic AI"),
    (TEAL,   "THEN", "Decision-makers can identify opportunities faster, with greater confidence and evidence"),
]
by = Inches(1.3)
for bc, label, text in blocks:
    add_rect(s, Inches(0.5), by, Inches(0.55), Inches(0.72), fill_rgb=bc)
    add_textbox(s, Inches(0.5), by + Inches(0.2), Inches(0.55), Inches(0.35),
                label, font_size=9, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(s, Inches(1.05), by, Inches(11.28), Inches(0.72),
             fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    add_textbox(s, Inches(1.2), by + Inches(0.16), Inches(11.0), Inches(0.45),
                text, font_size=12, color=TEXT)
    by += Inches(0.9)
    if label != "THEN":
        add_rect(s, Inches(0.66), by - Inches(0.18), Inches(0.22), Inches(0.18), fill_rgb=LIGHT)
        add_textbox(s, Inches(1.1), by - Inches(0.2), Inches(2.0), Inches(0.2),
                    "→", font_size=10, color=MUTED)

# Result box
add_rect(s, Inches(0.5), Inches(4.15), Inches(12.33), Inches(0.9), fill_rgb=NAVY)
add_rect(s, Inches(0.5), Inches(4.15), Inches(0.06), Inches(0.9), fill_rgb=GOLD)
add_textbox(s, Inches(0.7), Inches(4.22), Inches(2.5), Inches(0.28),
            "RESULTING IN", font_size=8, bold=True, color=GOLD)
add_textbox(s, Inches(0.7), Inches(4.5), Inches(11.8), Inches(0.45),
            "Improved competitiveness, better conversion performance and enhanced operational efficiency across PCW channels",
            font_size=12, color=WHITE)

slide_number(s, 5)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — Target Operating Model
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "OPERATING MODEL", "Target Operating Model — Seven-Stage Cycle")

tom = [
    (ACCENT, "1", "SENSE",     "Capture market movements continuously"),
    (MID,    "2", "ANALYSE",   "Identify patterns, ranking changes & competitor behaviour"),
    (TEAL,   "3", "SIMULATE",  "Evaluate potential interventions before implementation"),
    (PURPLE, "4", "RECOMMEND", "Generate pricing, offer and proposition recommendations"),
    (GOLD,   "5", "GOVERN",    "Apply human approval and oversight controls"),
    (GREEN,  "6", "EXECUTE",   "Implement approved changes across systems"),
    (RED,    "7", "LEARN",     "Measure outcomes and continuously improve"),
]
tw = Inches(1.73)
tx = Inches(0.35)
for tc, tn, tt, td in tom:
    add_rect(s, tx, Inches(1.3), tw, Inches(3.8), fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    add_rect(s, tx, Inches(1.3), tw, Inches(0.05), fill_rgb=tc)
    # Number circle
    circ = s.shapes.add_shape(9, tx + Inches(0.6), Inches(1.55), Inches(0.52), Inches(0.52))
    circ.fill.solid(); circ.fill.fore_color.rgb = tc
    circ.line.fill.background()
    add_textbox(s, tx + Inches(0.6), Inches(1.57), Inches(0.52), Inches(0.48),
                tn, font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(s, tx + Inches(0.1), Inches(2.2), tw - Inches(0.2), Inches(0.28),
                tt, font_size=9.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_rect(s, tx + tw/2 - Inches(0.2), Inches(2.52), Inches(0.4), Inches(0.03), fill_rgb=tc)
    add_textbox(s, tx + Inches(0.1), Inches(2.65), tw - Inches(0.2), Inches(2.2),
                td, font_size=9.5, color=SUB, align=PP_ALIGN.CENTER)
    # Arrow
    if tn != "7":
        add_textbox(s, tx + tw - Inches(0.05), Inches(2.85), Inches(0.22), Inches(0.3),
                    "›", font_size=16, color=MUTED)
    tx += tw + Inches(0.08)

slide_number(s, 6)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — Value Creation
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "VALUE FRAMEWORK", "Value Creation — Four Dimensions")

value_cards = [
    (ACCENT, "Increase New Business Growth",
     ["Improved PCW ranking position", "Enhanced pricing competitiveness", "Stronger product competitiveness", "Better offer competitiveness"]),
    (TEAL, "Improve Decision Quality",
     ["Better, evidence-based insights", "Faster, more reliable recommendations", "Evidence-based interventions", "Reduced subjectivity in decisions"]),
    (GOLD, "Improve Market Responsiveness",
     ["Continuous, real-time monitoring", "Significantly reduced response latency", "Earlier competitor movement detection", "Proactive rather than reactive posture"]),
    (PURPLE, "Reduce Operational Effort",
     ["Automated intelligence gathering", "Significantly reduced manual analysis", "Scalable market coverage", "Reusable platform capability"]),
]
vw = Inches(6.1)
positions = [(Inches(0.5), Inches(1.25)), (Inches(6.9), Inches(1.25)),
             (Inches(0.5),  Inches(4.1)),  (Inches(6.9), Inches(4.1))]
for (vx, vy), (tc, vt, vb) in zip(positions, value_cards):
    card(s, vx, vy, vw, Inches(2.6), tc)
    add_textbox(s, vx + Inches(0.2), vy + Inches(0.15), vw - Inches(0.3), Inches(0.32),
                vt, font_size=12, bold=True, color=NAVY)
    bullet_tf(s, vx + Inches(0.2), vy + Inches(0.55), vw - Inches(0.3), Inches(1.7),
              vb, font_size=10.5, color=SUB)

slide_number(s, 7)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — Architecture
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "CAPABILITY ARCHITECTURE", "Competitive Intelligence — Five-Layer Architecture")

layers = [
    (ACCENT, "Market Intelligence", ["Ranking monitoring", "Competitor monitoring", "Product monitoring", "Offer monitoring"]),
    (MID,    "Insight Layer",       ["Trend detection", "Competitive analysis", "Gap analysis", "Opportunity identification"]),
    (TEAL,   "Recommendation",      ["Pricing recommendations", "Offer recommendations", "Product recommendations", "Simulation outputs"]),
    (PURPLE, "Governance",          ["Human approval workflows", "Audit controls", "Compliance controls", "Explainability layer"]),
    (GREEN,  "Execution",           ["AGGS", "Duck Creek", "Pricing Services", "Product Services"]),
]
lw = Inches(2.45)
lx = Inches(0.35)
for lc, lt, li in layers:
    add_rect(s, lx, Inches(1.3), lw, Inches(0.42), fill_rgb=lc)
    add_textbox(s, lx + Inches(0.1), Inches(1.35), lw - Inches(0.2), Inches(0.35),
                lt, font_size=9.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    iy = Inches(1.82)
    for item in li:
        add_rect(s, lx, iy, lw, Inches(0.52), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
        add_textbox(s, lx + Inches(0.1), iy + Inches(0.12), lw - Inches(0.2), Inches(0.32),
                    item, font_size=10, color=TEXT, align=PP_ALIGN.CENTER)
        iy += Inches(0.6)
    lx += lw + Inches(0.15)

slide_number(s, 8)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — Agentic Architecture
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "AGENTIC AI DESIGN", "Multi-Agent Intelligence Architecture")

# Orchestrator bar
add_rect(s, Inches(0.5), Inches(1.3), Inches(12.33), Inches(0.6), fill_rgb=NAVY)
add_rect(s, Inches(0.5), Inches(1.3), Inches(0.06), Inches(0.6), fill_rgb=GOLD)
add_textbox(s, Inches(0.7), Inches(1.38), Inches(2.5), Inches(0.28),
            "ORCHESTRATOR AGENT", font_size=8.5, bold=True, color=GOLD)
add_textbox(s, Inches(3.3), Inches(1.4), Inches(9.3), Inches(0.35),
            "Coordinates end-to-end workflow — routes tasks, aggregates outputs, manages state and escalates to human governance tiers as required",
            font_size=10, color=RGBColor(0xCC, 0xD6, 0xE8))

agents = [
    (ACCENT, "01", "Market Collection",       "Captures competitor data continuously across all active PCW channels"),
    (MID,    "02", "Position Intelligence",    "Determines ranking movement, velocity and emerging trends"),
    (TEAL,   "03", "Competitor Analysis",      "Identifies market changes, drivers and competitor strategies"),
    (PURPLE, "04", "Pricing Intelligence",     "Assesses pricing competitiveness and gaps versus market"),
    (GOLD,   "05", "Proposition Intelligence", "Evaluates product and offer positioning versus competitors"),
    (RED,    "06", "Simulation",               "Models likely outcomes of proposed pricing or proposition actions"),
    (GREEN,  "07", "Recommendation",           "Produces actionable, evidence-based recommendations"),
    (RGBColor(0x08, 0x91, 0xB2), "08", "Learning", "Measures effectiveness and improves future recommendations"),
]
aw = Inches(1.53)
ax = Inches(0.5)
for ac, an, at, ad in agents:
    add_rect(s, ax, Inches(2.1), aw, Inches(3.4), fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    add_rect(s, ax, Inches(2.1), aw, Inches(0.04), fill_rgb=ac)
    add_textbox(s, ax + Inches(0.1), Inches(2.16), aw - Inches(0.2), Inches(0.22),
                f"Agent {an}", font_size=7.5, bold=True, color=MUTED)
    add_textbox(s, ax + Inches(0.1), Inches(2.4), aw - Inches(0.2), Inches(0.45),
                at, font_size=10, bold=True, color=NAVY)
    add_textbox(s, ax + Inches(0.1), Inches(2.9), aw - Inches(0.2), Inches(2.3),
                ad, font_size=9.5, color=SUB)
    ax += aw + Inches(0.1)

slide_number(s, 9)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — Integration
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "SYSTEMS INTEGRATION", "Integration with Existing LBG Architecture")

# Left: investments
add_textbox(s, Inches(0.5), Inches(1.3), Inches(5.5), Inches(0.3),
            "Existing Strategic Investments Reused", font_size=12, bold=True, color=NAVY)
investments = [("AGGS", "Aggregation Gateway"), ("Apigee", "API Management"),
               ("Pega", "Governance & Workflow"), ("Duck Creek", "Policy & Rating"),
               ("Pricing Services", "Rate Calculation"), ("Product Services", "Product Config")]
iy = Inches(1.75)
for nm, desc in investments:
    add_rect(s, Inches(0.5), iy, Inches(5.5), Inches(0.45),
             fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, Inches(0.5), iy, Inches(0.05), Inches(0.45), fill_rgb=MID)
    add_textbox(s, Inches(0.65), iy + Inches(0.08), Inches(2.5), Inches(0.3),
                nm, font_size=11, bold=True, color=TEXT)
    add_textbox(s, Inches(3.2), iy + Inches(0.1), Inches(2.7), Inches(0.28),
                desc, font_size=9.5, color=MUTED)
    iy += Inches(0.52)

# Principle box
add_rect(s, Inches(0.5), Inches(5.1), Inches(5.5), Inches(0.72), fill_rgb=NAVY)
add_rect(s, Inches(0.5), Inches(5.1), Inches(0.06), Inches(0.72), fill_rgb=GOLD)
add_textbox(s, Inches(0.7), Inches(5.2), Inches(5.2), Inches(0.5),
            "Enhance existing capabilities rather than create parallel operating models",
            font_size=10, color=RGBColor(0xCC, 0xD6, 0xE8), italic=True)

# Right: flow
add_textbox(s, Inches(7.0), Inches(1.3), Inches(5.8), Inches(0.3),
            "Data & Decision Flow", font_size=12, bold=True, color=NAVY)
flow_nodes = [
    (RGBColor(0x0F, 0x7A, 0xC5), "PCWs — Market Data Source"),
    (MID,    "Competitive Intelligence Platform"),
    (SUB,    "Apigee — API Management Layer"),
    (TEAL,   "AGGS · Duck Creek · Pricing Services"),
    (PURPLE, "Pega — Governance & Approval"),
    (GREEN,  "Business Users — Decision & Oversight"),
]
fy = Inches(1.72)
for fc, ft in flow_nodes:
    add_rect(s, Inches(7.0), fy, Inches(5.8), Inches(0.44), fill_rgb=fc)
    add_textbox(s, Inches(7.1), fy + Inches(0.1), Inches(5.6), Inches(0.28),
                ft, font_size=10.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    fy += Inches(0.44)
    if ft != flow_nodes[-1][1]:
        add_textbox(s, Inches(9.6), fy, Inches(0.6), Inches(0.22),
                    "↓", font_size=12, color=MUTED, align=PP_ALIGN.CENTER)
        fy += Inches(0.22)

slide_number(s, 10)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 11 — Human in the Loop
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "GOVERNANCE DESIGN", "Human-in-the-Loop Decision Model")

tiers = [
    (RGBColor(0x16, 0x65, 0x34), RGBColor(0xDC, 0xFC, 0xE7), "1", "AUTO",
     "Market monitoring and analysis", "Continuous, fully automated data collection and pattern detection", "Fully Automated"),
    (RGBColor(0x1E, 0x40, 0xAF), RGBColor(0xDB, 0xEA, 0xFE), "2", "ANALYSE",
     "Recommendation generation", "AI surfaces intelligence, quantifies opportunity and drafts recommended actions", "AI-Driven"),
    (RGBColor(0x92, 0x40, 0x0E), RGBColor(0xFE, 0xF3, 0xC7), "3", "APPROVE",
     "Pricing teams review", "Human judgement applied before any action is approved for execution", "Human Required"),
    (RGBColor(0x6B, 0x21, 0xA8), RGBColor(0xF3, 0xE8, 0xFF), "4", "EXECUTE",
     "Approved actions implemented", "Governed, auditable execution through existing system integrations", "Governed"),
    (RGBColor(0x99, 0x1B, 0x1B), RGBColor(0xFE, 0xE2, 0xE2), "5", "LEARN",
     "Outcomes measured", "Outcomes fed back into models for continuous improvement of recommendation quality", "Closed-Loop"),
]
ty = Inches(1.25)
for tc, bg, tn, badge, title, desc, note in tiers:
    add_rect(s, Inches(0.5), ty, Inches(12.33), Inches(0.8), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    # Tier number
    add_textbox(s, Inches(0.6), ty + Inches(0.18), Inches(0.55), Inches(0.5),
                tn, font_size=24, bold=True, color=RGBColor(0xD1, 0xD9, 0xE8))
    # Badge
    add_rect(s, Inches(1.3), ty + Inches(0.22), Inches(1.0), Inches(0.34), fill_rgb=bg)
    add_textbox(s, Inches(1.3), ty + Inches(0.25), Inches(1.0), Inches(0.28),
                badge, font_size=8.5, bold=True, color=tc, align=PP_ALIGN.CENTER)
    # Title
    add_textbox(s, Inches(2.5), ty + Inches(0.08), Inches(5.0), Inches(0.3),
                title, font_size=11, bold=True, color=NAVY)
    # Desc
    add_textbox(s, Inches(2.5), ty + Inches(0.42), Inches(8.0), Inches(0.32),
                desc, font_size=10, color=SUB)
    # Note
    add_textbox(s, Inches(10.8), ty + Inches(0.25), Inches(2.0), Inches(0.3),
                note, font_size=9, bold=True, color=tc, align=PP_ALIGN.RIGHT)
    ty += Inches(0.88)

# Principle bar
add_rect(s, Inches(0.5), Inches(5.68), Inches(12.33), Inches(0.45), fill_rgb=NAVY)
add_textbox(s, Inches(0.5), Inches(5.74), Inches(12.33), Inches(0.32),
            "The platform RECOMMENDS.   People DECIDE.   Systems EXECUTE.   Always.",
            font_size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

slide_number(s, 11)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 12 — Governance & Risk
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "RISK & COMPLIANCE", "Governance & Risk Framework")

gov = [
    (RGBColor(0x1E, 0x40, 0xAF), RGBColor(0xDB, 0xEA, 0xFE), "FCA Alignment",
     "Supports Consumer Duty and governed decision-making. Recommendations traceable to clear business rationale."),
    (GREEN, RGBColor(0xDC, 0xFC, 0xE7), "Auditability",
     "Full lineage of all recommendations maintained. Every decision point captured with timestamp, actor and rationale."),
    (GOLD, RGBColor(0xFE, 0xF3, 0xC7), "Explainability",
     "Transparent rationale for every recommendation. Pricing teams can interrogate AI outputs before approving."),
    (PURPLE, RGBColor(0xF3, 0xE8, 0xFF), "Data Protection",
     "PII protection enforced throughout. Access controls and data minimisation aligned to GDPR obligations."),
    (RGBColor(0x08, 0x91, 0xB2), RGBColor(0xCC, 0xF6, 0xFE), "Model Governance",
     "Continuous evaluation and performance monitoring of AI models. Drift detection and retraining protocols."),
    (RED, RGBColor(0xFE, 0xE2, 0xE2), "Operational Resilience",
     "Fallback mechanisms and recovery procedures defined. Platform degradation does not disrupt core pricing operations."),
]
positions = [(Inches(0.5), Inches(1.25)), (Inches(4.6), Inches(1.25)), (Inches(8.7), Inches(1.25)),
             (Inches(0.5), Inches(4.0)),  (Inches(4.6), Inches(4.0)),  (Inches(8.7), Inches(4.0))]
gw, gh = Inches(3.8), Inches(2.5)
for (gx, gy), (tc, bg, gt, gd) in zip(positions, gov):
    add_rect(s, gx, gy, gw, gh, fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    add_rect(s, gx, gy, gw, Inches(0.04), fill_rgb=tc)
    add_rect(s, gx + Inches(0.18), gy + Inches(0.18), Inches(0.38), Inches(0.38), fill_rgb=bg)
    add_textbox(s, gx + Inches(0.18), Inches(1.9) if gy < Inches(3) else Inches(4.65),
                gw - Inches(0.3), Inches(0.3),
                gt, font_size=12, bold=True, color=NAVY)
    add_textbox(s, gx + Inches(0.18), Inches(2.24) if gy < Inches(3) else Inches(4.98),
                gw - Inches(0.3), Inches(1.4),
                gd, font_size=10.5, color=SUB)

slide_number(s, 12)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 13 — KPI Framework
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "PERFORMANCE MANAGEMENT", "KPI & Measurement Framework")

kpis = [
    (ACCENT, "Commercial",   ["PCW ranking position", "Quote conversion rate", "New business growth", "Revenue per quote"]),
    (MID,    "Operational",  ["Monitoring effort (FTE hrs)", "Time to insight", "Time to decision", "Recommendation latency"]),
    (TEAL,   "Strategic",    ["Market responsiveness index", "Competitor coverage breadth", "Recommendation adoption rate", "Platform reuse score"]),
    (RED,    "Risk & Control",["Audit compliance rate", "Control effectiveness", "Model performance (accuracy)", "Governance approval rate"]),
]
kw = Inches(3.0)
kx = Inches(0.5)
for kc, kt, ki in kpis:
    add_rect(s, kx, Inches(1.3), kw, Inches(0.42), fill_rgb=kc)
    add_textbox(s, kx + Inches(0.1), Inches(1.35), kw - Inches(0.2), Inches(0.32),
                kt.upper(), font_size=9.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    iy = Inches(1.82)
    for item in ki:
        add_rect(s, kx, iy, kw, Inches(0.56), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
        add_rect(s, kx, iy, Inches(0.05), Inches(0.56), fill_rgb=kc)
        add_textbox(s, kx + Inches(0.12), iy + Inches(0.14), kw - Inches(0.2), Inches(0.3),
                    item, font_size=11, color=TEXT)
        iy += Inches(0.64)
    kx += kw + Inches(0.44)

slide_number(s, 13)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 14 — Roadmap
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "PHASED DELIVERY", "12-Month Delivery Roadmap")

waves = [
    (ACCENT, "Wave 1", "Market Visibility", "Months 1–3",
     ["PCW ranking data capture", "Competitor baseline monitoring", "Executive dashboards", "Data quality validation"]),
    (MID, "Wave 2", "Intelligence", "Months 4–6",
     ["Analysis agents deployed", "Trend detection active", "Opportunity identification", "Competitor profiling"]),
    (TEAL, "Wave 3", "Decision Support", "Months 7–9",
     ["Recommendation engine live", "Pega governance integration", "Approval workflow active", "AGGS / Duck Creek integration"]),
    (PURPLE, "Wave 4", "Optimisation", "Months 10–12",
     ["Simulation capability active", "Closed-loop learning", "Continuous optimisation", "Full PCW channel coverage"]),
]
ww = Inches(3.0)
wx = Inches(0.5)
for wc, wv, wt, wm, wi in waves:
    # Header
    add_rect(s, wx, Inches(1.3), ww, Inches(1.05), fill_rgb=wc)
    add_textbox(s, wx + Inches(0.15), Inches(1.35), ww - Inches(0.25), Inches(0.24),
                wv.upper(), font_size=7.5, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF, ))
    add_textbox(s, wx + Inches(0.15), Inches(1.58), ww - Inches(0.25), Inches(0.35),
                wt, font_size=14, bold=True, color=WHITE)
    add_textbox(s, wx + Inches(0.15), Inches(1.9), ww - Inches(0.25), Inches(0.24),
                wm, font_size=9, color=RGBColor(0xCC, 0xD6, 0xE8))
    # Items
    add_rect(s, wx, Inches(2.45), ww, Inches(4.05), fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    iy = Inches(2.6)
    for item in wi:
        add_textbox(s, wx + Inches(0.15), iy, ww - Inches(0.25), Inches(0.35),
                    f"✓  {item}", font_size=10.5, color=TEXT)
        iy += Inches(0.45)
    wx += ww + Inches(0.44)

# Timeline bar
add_rect(s, Inches(0.5), Inches(6.55), Inches(12.33), Inches(0.14),
         fill_rgb=RGBColor(0xE2, 0xE8, 0xF0))
for i, (wc, _, _, _, _) in enumerate(waves):
    bw = Inches(3.0)
    bx = Inches(0.5) + i * (bw + Inches(0.44))
    add_rect(s, bx, Inches(6.55), bw, Inches(0.14), fill_rgb=wc)

slide_number(s, 14)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 15 — Business Value
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=WHITE)
slide_header(s, "BUSINESS CASE", "Business Value Summary")

bv = [
    (ACCENT, "⚡", "Faster Market Response",
     "Reduce time from competitor movement to business action from days to hours. Continuous sensing eliminates monitoring blindspots and manual lag across all active PCW channels."),
    (TEAL, "📈", "Better Commercial Outcomes",
     "Improve PCW ranking visibility and pricing competitiveness. Evidence-based recommendations enable more targeted interventions with measurable conversion and revenue impact."),
    (GOLD, "🔧", "Operational Efficiency",
     "Significantly reduce manual monitoring and analysis effort. Free pricing and proposition teams to focus on judgement-intensive decisions rather than data collection and synthesis."),
    (PURPLE, "🏗", "Reusable Strategic Capability",
     "Establish a Competitive Intelligence platform extensible across broader General Insurance use cases — a durable, scalable strategic asset, not a one-off solution."),
]
positions = [(Inches(0.5), Inches(1.25)), (Inches(6.9), Inches(1.25)),
             (Inches(0.5),  Inches(4.1)),  (Inches(6.9), Inches(4.1))]
bw, bh = Inches(6.1), Inches(2.6)
for (bx, by), (bc, icon, bt, bd) in zip(positions, bv):
    card(s, bx, by, bw, bh, bc)
    add_textbox(s, bx + Inches(0.2), by + Inches(0.12), Inches(0.45), Inches(0.38),
                icon, font_size=20, color=bc)
    add_textbox(s, bx + Inches(0.75), by + Inches(0.15), bw - Inches(0.9), Inches(0.35),
                bt, font_size=13, bold=True, color=NAVY)
    add_textbox(s, bx + Inches(0.2), by + Inches(0.6), bw - Inches(0.35), Inches(1.75),
                bd, font_size=10.5, color=SUB)

slide_number(s, 15)


# ═══════════════════════════════════════════════════════════════════════════════
# SLIDE 16 — Recommendation & Close
# ═══════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
add_rect(s, 0, 0, W, H, fill_rgb=NAVY)
add_rect(s, 0, 0, W, Inches(0.08), fill_rgb=GOLD)
add_rect(s, 0, 0, Inches(0.08), H, fill_rgb=GOLD)

add_textbox(s, Inches(0.5), Inches(0.4), Inches(10), Inches(0.28),
            "RECOMMENDATION & DECISION REQUIRED",
            font_size=8, bold=True, color=GOLD)

# Recommendation box
add_rect(s, Inches(0.5), Inches(0.85), Inches(12.33), Inches(1.0),
         fill_rgb=RGBColor(0x12, 0x22, 0x3F))
add_rect(s, Inches(0.5), Inches(0.85), Inches(0.06), Inches(1.0), fill_rgb=GOLD)
add_textbox(s, Inches(0.7), Inches(0.92), Inches(12.0), Inches(0.75),
            "Proceed with a focused MVP targeting a single PCW channel and a limited set of pricing "
            "and proposition use cases — validating the core capability before scaling to full channel coverage.",
            font_size=12, color=WHITE)

add_textbox(s, Inches(0.5), Inches(2.1), Inches(6.0), Inches(0.28),
            "IMMEDIATE NEXT STEPS", font_size=8, bold=True, color=RGBColor(0x94, 0xA3, 0xB8))

next_steps = [
    ("1", "Confirm business sponsorship and executive ownership"),
    ("2", "Validate commercial value drivers and target KPIs"),
    ("3", "Define MVP scope and success criteria"),
    ("4", "Build and validate pilot platform (Wave 1)"),
    ("5", "Measure outcomes against baseline KPIs"),
    ("6", "Scale across all PCW channels — Waves 2–4"),
]
nsx, nsy = Inches(0.5), Inches(2.5)
for i, (ns_n, ns_t) in enumerate(next_steps):
    nx = nsx + (Inches(6.25) if i >= 3 else 0)
    ny = nsy + (i % 3) * Inches(0.68)
    add_rect(s, nx, ny, Inches(0.36), Inches(0.36), fill_rgb=GOLD)
    add_textbox(s, nx, ny + Inches(0.04), Inches(0.36), Inches(0.28),
                ns_n, font_size=10, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_textbox(s, nx + Inches(0.44), ny + Inches(0.04), Inches(5.6), Inches(0.3),
                ns_t, font_size=10.5, color=RGBColor(0xCC, 0xD6, 0xE8))

# Closing line
add_rect(s, Inches(0.5), Inches(6.2), Inches(12.33), Inches(0.01),
         fill_rgb=RGBColor(0x2D, 0x3F, 0x5E))
add_textbox(s, Inches(0.5), Inches(6.35), Inches(12.33), Inches(0.45),
            '"Transforming competitor monitoring into continuous competitive intelligence and optimisation."',
            font_size=12.5, italic=True, color=RGBColor(0xCC, 0xD6, 0xE8), align=PP_ALIGN.CENTER)

slide_number(s, 16)


# ── Save ──────────────────────────────────────────────────────────────────────
out = "/home/user/rag/LBG_PCW_Competitive_Intelligence_Deck.pptx"
prs.save(out)
print(f"Saved: {out}")
