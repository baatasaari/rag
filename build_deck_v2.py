"""
build_deck_v2.py — LBG PCW Competitive Intelligence Platform v2
Builds a comprehensive, professional consulting-style PowerPoint presentation.
Run: python3 build_deck_v2.py
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree
import copy

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
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

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)

# ---------------------------------------------------------------------------
# Helper: set shape fill
# ---------------------------------------------------------------------------
def _set_fill(shape, rgb):
    fill = shape.fill
    fill.solid()
    fill.fore_color.rgb = rgb


def _set_line(shape, rgb, pt=0.75):
    line = shape.line
    line.color.rgb = rgb
    line.width = Pt(pt)


def _no_line(shape):
    shape.line.fill.background()


# ---------------------------------------------------------------------------
# add_rect
# ---------------------------------------------------------------------------
def add_rect(slide, x, y, w, h, fill_rgb=None, line_rgb=None, line_pt=0.75):
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        x, y, w, h
    )
    if fill_rgb:
        _set_fill(shape, fill_rgb)
    else:
        shape.fill.background()
    if line_rgb:
        _set_line(shape, line_rgb, line_pt)
    else:
        _no_line(shape)
    return shape


# ---------------------------------------------------------------------------
# add_textbox
# ---------------------------------------------------------------------------
def add_textbox(slide, x, y, w, h, text, font_size=10, bold=False, italic=False,
                color=TEXT, align=PP_ALIGN.LEFT, wrap=True, font_name="Calibri"):
    txBox = slide.shapes.add_textbox(x, y, w, h)
    txBox.word_wrap = wrap
    tf = txBox.text_frame
    tf.word_wrap = wrap
    tf.auto_size = None
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return txBox


# ---------------------------------------------------------------------------
# add_textbox_multiline — adds a textbox with multiple paragraphs
# ---------------------------------------------------------------------------
def add_textbox_multiline(slide, x, y, w, h, lines, font_size=10, bold=False,
                          italic=False, color=TEXT, align=PP_ALIGN.LEFT,
                          font_name="Calibri", space_before=0):
    txBox = slide.shapes.add_textbox(x, y, w, h)
    txBox.word_wrap = True
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.alignment = align
        if space_before:
            p.space_before = Pt(space_before)
        run = p.add_run()
        run.text = line
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
    return txBox


# ---------------------------------------------------------------------------
# slide_chrome
# ---------------------------------------------------------------------------
def slide_chrome(slide, eyebrow, title, n, total):
    # Left navy stripe
    add_rect(slide, Inches(0), Inches(0), Inches(0.07), SLIDE_H, fill_rgb=NAVY)
    # Gold footer bar
    add_rect(slide, Inches(0), SLIDE_H - Inches(0.07), SLIDE_W, Inches(0.07), fill_rgb=GOLD)
    # Eyebrow
    add_textbox(slide, Inches(0.18), Inches(0.13), Inches(10), Inches(0.22),
                eyebrow, font_size=7, bold=True, color=MID, align=PP_ALIGN.LEFT)
    # Title
    add_textbox(slide, Inches(0.18), Inches(0.33), Inches(11.5), Inches(0.42),
                title, font_size=16, bold=True, color=NAVY, align=PP_ALIGN.LEFT)
    # Gold rule under title
    add_rect(slide, Inches(0.18), Inches(0.76), Inches(12.8), Inches(0.035), fill_rgb=GOLD)
    # Slide number bottom right
    add_textbox(slide, Inches(12.3), SLIDE_H - Inches(0.32), Inches(0.9), Inches(0.25),
                f"{n} / {total}", font_size=7.5, bold=False, color=MUTED, align=PP_ALIGN.RIGHT)


# ---------------------------------------------------------------------------
# card_box
# ---------------------------------------------------------------------------
def card_box(slide, x, y, w, h, top_color, bg=LIGHT):
    add_rect(slide, x, y, w, h, fill_rgb=bg)
    add_rect(slide, x, y, w, Inches(0.05), fill_rgb=top_color)


# ---------------------------------------------------------------------------
# Bullet list helper
# ---------------------------------------------------------------------------
def add_bullet_list(slide, x, y, w, h, items, font_size=9, color=TEXT,
                    bullet_color=ACCENT, font_name="Calibri", line_spacing=1.0):
    txBox = slide.shapes.add_textbox(x, y, w, h)
    txBox.word_wrap = True
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        run.text = "- " + item
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
    return txBox


# ---------------------------------------------------------------------------
# Presentation setup
# ---------------------------------------------------------------------------
prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
blank_layout = prs.slide_layouts[6]

TOTAL = 18

# ===========================================================================
# SLIDE 1 — Cover
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)

# Full navy background
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=NAVY)
# Gold top bar
add_rect(slide, 0, 0, SLIDE_W, Inches(0.08), fill_rgb=GOLD)
# Gold left bar
add_rect(slide, 0, 0, Inches(0.08), SLIDE_H, fill_rgb=GOLD)
# Right panel (lighter navy)
add_rect(slide, Inches(9.0), 0, SLIDE_W - Inches(9.0), SLIDE_H,
         fill_rgb=RGBColor(0x14, 0x24, 0x42))

# Left side content
# Small label
add_textbox(slide, Inches(0.3), Inches(0.25), Inches(7.5), Inches(0.3),
            "LLOYDS BANKING GROUP  |  GENERAL INSURANCE",
            font_size=8, bold=True, color=GOLD)

# Main title — line 1
add_textbox(slide, Inches(0.3), Inches(0.72), Inches(8.3), Inches(0.55),
            "PCW Competitive Intelligence",
            font_size=34, bold=True, color=WHITE)
# Main title — line 2
add_textbox(slide, Inches(0.3), Inches(1.22), Inches(8.3), Inches(0.55),
            "& Optimisation Platform",
            font_size=34, bold=True, color=WHITE)

# Gold divider rect
add_rect(slide, Inches(0.3), Inches(1.85), Inches(0.6), Inches(0.05), fill_rgb=GOLD)

# Subtitle
add_textbox(slide, Inches(0.3), Inches(2.0), Inches(8.3), Inches(0.4),
            "Transforming Market Monitoring into Continuous Competitive Advantage",
            font_size=12, italic=True, color=MUTED)

# Pills
pill_labels = ["Machine Learning", "Generative AI", "Agentic Automation"]
for i, label in enumerate(pill_labels):
    px = Inches(0.3 + i * 2.2)
    py = Inches(2.55)
    pw = Inches(2.0)
    ph = Inches(0.32)
    pr = add_rect(slide, px, py, pw, ph, fill_rgb=None, line_rgb=GOLD, line_pt=1.0)
    add_textbox(slide, px + Inches(0.05), py + Inches(0.05), pw - Inches(0.1), ph - Inches(0.05),
                label, font_size=9, bold=True, color=GOLD, align=PP_ALIGN.CENTER)

# Executive message box
add_rect(slide, Inches(0.3), Inches(3.1), Inches(8.5), Inches(1.2),
         fill_rgb=RGBColor(0x12, 0x22, 0x3F))
add_rect(slide, Inches(0.3), Inches(3.1), Inches(0.06), Inches(1.2), fill_rgb=GOLD)
add_textbox(slide, Inches(0.5), Inches(3.18), Inches(8.2), Inches(1.05),
            "This platform harnesses the full spectrum of AI capability — from ML-driven pricing models "
            "to GenAI-powered analysis and Agentic automation — to deliver continuous, governed competitive "
            "intelligence across all PCW channels.",
            font_size=10, italic=True, color=RGBColor(0xC8, 0xD6, 0xE8), wrap=True)

# Right panel — DELIVERY PHASES label
add_textbox(slide, Inches(9.15), Inches(0.45), Inches(3.8), Inches(0.28),
            "DELIVERY PHASES", font_size=8, bold=True, color=GOLD)

# Four wave boxes
waves = [
    ("Wave 1", "Market Visibility", "Months 1-3"),
    ("Wave 2", "Intelligence", "Months 4-6"),
    ("Wave 3", "Decision Support", "Months 7-9"),
    ("Wave 4", "Optimisation", "Months 10-12"),
]
wave_colors = [ACCENT, MID, TEAL, PURPLE]
for i, (wname, wtitle, wmonths) in enumerate(waves):
    wy = Inches(0.85 + i * 1.52)
    add_rect(slide, Inches(9.15), wy, Inches(3.9), Inches(1.35),
             fill_rgb=RGBColor(0x0C, 0x1C, 0x34))
    add_rect(slide, Inches(9.15), wy, Inches(0.06), Inches(1.35), fill_rgb=wave_colors[i])
    add_textbox(slide, Inches(9.3), wy + Inches(0.1), Inches(3.6), Inches(0.25),
                wname, font_size=8, bold=True, color=wave_colors[i])
    add_textbox(slide, Inches(9.3), wy + Inches(0.35), Inches(3.6), Inches(0.3),
                wtitle, font_size=12, bold=True, color=WHITE)
    add_textbox(slide, Inches(9.3), wy + Inches(0.72), Inches(3.6), Inches(0.25),
                wmonths, font_size=9, color=MUTED)

# ===========================================================================
# SLIDE 2 — Executive Summary
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "EXECUTIVE SUMMARY", "Platform Overview — The Case for Change", 2, TOTAL)

col_w = Inches(4.1)
col_gap = Inches(0.12)
col_y = Inches(0.9)
col_h = Inches(4.7)

# Card 1 — Opportunity (ACCENT)
cx = Inches(0.18)
card_box(slide, cx, col_y, col_w, col_h, ACCENT, LIGHT)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.12), col_w - Inches(0.2), Inches(0.22),
            "THE OPPORTUNITY", font_size=7.5, bold=True, color=ACCENT)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.35), col_w - Inches(0.2), Inches(0.55),
            "PCWs are a primary acquisition channel under continuous competitive pressure",
            font_size=10.5, bold=True, color=NAVY, wrap=True)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.97), col_w - Inches(0.2), Inches(3.55),
            "Price Comparison Websites influence the majority of UK General Insurance new business. "
            "Customers compare price, excess, features, add-ons and brand across multiple providers simultaneously. "
            "Small changes in market position can drive material volume impact. "
            "Competitors adjust their positioning daily — creating both risk and opportunity.",
            font_size=9.5, color=SUB, wrap=True)

# Card 2 — Challenge (MID)
cx = Inches(0.18) + col_w + col_gap
card_box(slide, cx, col_y, col_w, col_h, MID, LIGHT)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.12), col_w - Inches(0.2), Inches(0.22),
            "THE CHALLENGE", font_size=7.5, bold=True, color=MID)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.35), col_w - Inches(0.2), Inches(0.55),
            "Current monitoring is periodic, manual and unable to match market velocity",
            font_size=10.5, bold=True, color=NAVY, wrap=True)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.97), col_w - Inches(0.2), Inches(3.55),
            "LBG's current approach relies on scheduled, manual market reviews. By the time trends are identified, "
            "analysed and actioned, the market has often moved on. Teams work in silos, data is inconsistent, "
            "and there is no mechanism for continuous, cross-channel competitive tracking or rapid response.",
            font_size=9.5, color=SUB, wrap=True)

# Card 3 — Recommendation (NAVY)
cx = Inches(0.18) + 2 * (col_w + col_gap)
add_rect(slide, cx, col_y, col_w, col_h, fill_rgb=NAVY)
add_rect(slide, cx, col_y, col_w, Inches(0.05), fill_rgb=GOLD)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.12), col_w - Inches(0.2), Inches(0.22),
            "THE RECOMMENDATION", font_size=7.5, bold=True, color=GOLD)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(0.35), col_w - Inches(0.2), Inches(0.6),
            "Build an AI-powered Competitive Intelligence & Optimisation Platform",
            font_size=10.5, bold=True, color=WHITE, wrap=True)
add_textbox(slide, cx + Inches(0.12), col_y + Inches(1.02), col_w - Inches(0.2), Inches(3.5),
            "Deploy a multi-capability AI platform combining traditional ML models, Generative AI and Agentic "
            "automation — continuously monitoring market signals, generating intelligence and recommending actions, "
            "governed by human oversight at every decision point.",
            font_size=9.5, color=RGBColor(0xB8, 0xCC, 0xE4), wrap=True)

# Outcomes row
outcomes = [
    "Improved PCW ranking position",
    "Faster competitor response",
    "Better pricing decisions",
    "Reduced manual effort",
    "Reusable AI platform capability",
]
oy = Inches(5.75)
ow = Inches(2.47)
oh = Inches(0.65)
for i, out in enumerate(outcomes):
    ox = Inches(0.18 + i * 2.59)
    add_rect(slide, ox, oy, ow, oh, fill_rgb=WARM)
    add_rect(slide, ox, oy, Inches(0.05), oh, fill_rgb=TEAL)
    add_textbox(slide, ox + Inches(0.1), oy + Inches(0.1), ow - Inches(0.15), oh - Inches(0.12),
                out, font_size=9, bold=True, color=NAVY, wrap=True)

# ===========================================================================
# SLIDE 3 — Market Context
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "MARKET CONTEXT", "Why PCWs Matter — The Strategic Imperative", 3, TOTAL)

# Left column
lx = Inches(0.18)
lw = Inches(6.0)
ly = Inches(0.88)
add_textbox(slide, lx, ly, lw, Inches(0.28), "The PCW Landscape",
            font_size=13, bold=True, color=NAVY)

stat_boxes = [
    ("Customer Behaviour",
     "Over 80% of UK motor insurance customers use a PCW at some stage of their purchase journey. "
     "Home insurance PCW penetration continues to grow year-on-year as price sensitivity increases "
     "post-cost-of-living pressures."),
    ("Ranking Economics",
     "Position 1-3 on a PCW results list captures a disproportionate share of clicks and quote completions. "
     "Moving from position 5 to position 2 can increase quote volume by 30-50% depending on the PCW "
     "and product line."),
    ("Competitor Velocity",
     "Analysis of PCW markets shows competitors make pricing or proposition adjustments multiple times per week. "
     "Seasonal peaks, regulatory changes and claims events all trigger rapid market responses "
     "that LBG must be able to match."),
]
for i, (title, body) in enumerate(stat_boxes):
    sy = Inches(1.22 + i * 1.95)
    sh = Inches(1.8)
    add_rect(slide, lx, sy, lw, sh, fill_rgb=LIGHT)
    add_rect(slide, lx, sy, Inches(0.05), sh, fill_rgb=ACCENT)
    add_textbox(slide, lx + Inches(0.12), sy + Inches(0.1), lw - Inches(0.2), Inches(0.28),
                title, font_size=10.5, bold=True, color=NAVY)
    add_textbox(slide, lx + Inches(0.12), sy + Inches(0.42), lw - Inches(0.2), Inches(1.3),
                body, font_size=9, color=SUB, wrap=True)

# Right column
rx = Inches(6.45)
rw = Inches(6.65)
add_textbox(slide, rx, ly, rw, Inches(0.28), "Strategic Implications",
            font_size=13, bold=True, color=NAVY)

insight_boxes = [
    ("Real-Time Insight is a Competitive Necessity",
     "Firms that can sense and respond to market movements within hours — rather than days or weeks — "
     "consistently outperform on PCW conversion metrics. Intelligence latency is directly correlated "
     "with lost volume.", MID, WARM),
    ("Proposition is as Important as Price",
     "PCW algorithms increasingly weight excess levels, optional cover inclusions, claim processes and "
     "customer review scores alongside raw premium. Competitive intelligence must span the full product "
     "proposition, not just price.", MID, WARM),
]
for i, (title, body, strip, bg) in enumerate(insight_boxes):
    sy = Inches(1.22 + i * 2.0)
    sh = Inches(1.75)
    add_rect(slide, rx, sy, rw, sh, fill_rgb=bg)
    add_rect(slide, rx, sy, Inches(0.05), sh, fill_rgb=strip)
    add_textbox(slide, rx + Inches(0.12), sy + Inches(0.1), rw - Inches(0.2), Inches(0.28),
                title, font_size=10.5, bold=True, color=NAVY)
    add_textbox(slide, rx + Inches(0.12), sy + Inches(0.42), rw - Inches(0.2), Inches(1.25),
                body, font_size=9, color=SUB, wrap=True)

# Risk box
ry = Inches(5.3)
rh = Inches(1.05)
add_rect(slide, rx, ry, rw, rh, fill_rgb=WARM)
add_rect(slide, rx, ry, Inches(0.05), rh, fill_rgb=RED)
add_textbox(slide, rx + Inches(0.12), ry + Inches(0.08), rw - Inches(0.2), Inches(0.9),
            "Current State Risk: Without continuous monitoring, LBG risks sustained periods of sub-optimal "
            "PCW positioning — particularly during competitor promotional campaigns, regulatory-driven repricing "
            "events or claims inflation cycles.",
            font_size=9, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 4 — Current State Assessment
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "CURRENT STATE", "Current State Assessment — Process & Pain Points", 4, TOTAL)

flow_steps = [
    ("01 MONITORING",
     "Periodic manual market reviews conducted at irregular intervals. No continuous tracking. Coverage varies "
     "by team and channel. PCW data captured inconsistently across Motor, Home and other lines."),
    ("02 ANALYSIS",
     "Data collected in spreadsheets and shared drives. No common taxonomy or data model. Analysis duplicated "
     "across pricing, product and proposition teams. Findings not systematically stored or compared over time."),
    ("03 DECISION MAKING",
     "Decisions rely on analyst judgement without systematic competitive context. Lead times from insight to "
     "decision typically span days to weeks. No simulation capability to assess likely impact before acting."),
    ("04 EXECUTION",
     "Changes routed through multiple approval layers with no automated handoffs. Pricing, product and operations "
     "teams coordinated manually. No closed loop to measure the outcome of interventions."),
    ("05 OUTCOME",
     "Reactive posture. LBG responds to competitor actions rather than anticipating them. Opportunity windows "
     "are missed. Manual effort is high and difficult to scale as PCW channel complexity increases."),
]
step_colors = [ACCENT, MID, TEAL, PURPLE, RED]
sw = Inches(2.4)
sh = Inches(2.85)
for i, (title, body) in enumerate(flow_steps):
    sx = Inches(0.18 + i * 2.63)
    sy = Inches(0.9)
    add_rect(slide, sx, sy, sw, sh, fill_rgb=LIGHT)
    add_rect(slide, sx, sy, sw, Inches(0.07), fill_rgb=step_colors[i])
    add_textbox(slide, sx + Inches(0.1), sy + Inches(0.12), sw - Inches(0.15), Inches(0.28),
                title, font_size=9, bold=True, color=step_colors[i])
    add_textbox(slide, sx + Inches(0.1), sy + Inches(0.45), sw - Inches(0.15), Inches(2.25),
                body, font_size=8.5, color=SUB, wrap=True)

# Pain points section
pain_y = Inches(3.95)
lx = Inches(0.18)
lw = Inches(6.0)
add_textbox(slide, lx, pain_y, lw, Inches(0.28), "Key Friction Points",
            font_size=11, bold=True, color=NAVY)
left_bullets = [
    "No single source of truth for competitor positioning data",
    "Analysis capability does not scale with market complexity",
    "Decision latency creates exploitable competitive windows",
    "No measurement framework linking interventions to outcomes",
]
add_bullet_list(slide, lx, pain_y + Inches(0.32), lw, Inches(1.8), left_bullets,
                font_size=9, color=SUB)

rx = Inches(6.6)
rw = Inches(6.5)
add_textbox(slide, rx, pain_y, rw, Inches(0.28), "Organisational Consequences",
            font_size=11, bold=True, color=NAVY)
right_bullets = [
    "Sub-optimal PCW rankings during competitor campaign periods",
    "Pricing teams operating without full market context",
    "Product proposition gaps not identified until customer feedback",
    "Significant FTE effort on low-value data collection and formatting",
]
add_bullet_list(slide, rx, pain_y + Inches(0.32), rw, Inches(1.8), right_bullets,
                font_size=9, color=SUB)

# Result bar
rb_y = Inches(6.75)
add_rect(slide, Inches(0.18), rb_y, SLIDE_W - Inches(0.36), Inches(0.55),
         fill_rgb=RGBColor(0xFB, 0xF3, 0xE0))
add_rect(slide, Inches(0.18), rb_y, Inches(0.06), Inches(0.55), fill_rgb=GOLD)
add_textbox(slide, Inches(0.35), rb_y + Inches(0.1), SLIDE_W - Inches(0.6), Inches(0.35),
            "Net result: Reactive rather than proactive market response — competitive advantage consistently "
            "ceded during monitoring gaps",
            font_size=9.5, bold=True, color=RGBColor(0x7A, 0x5C, 0x10), wrap=True)

# ===========================================================================
# SLIDE 5 — Strategic Hypothesis
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "STRATEGIC HYPOTHESIS", "Strategic Hypothesis — The Logical Construct", 5, TOTAL)

hyp_blocks = [
    ("IF", ACCENT,
     "LBG establishes continuous, automated capture of competitor pricing, product and proposition data across "
     "all active PCW channels — creating a real-time market intelligence feed that does not depend on manual "
     "collection or scheduled reviews"),
    ("AND", MID,
     "This data is processed by a layered AI capability — combining ML models for pattern detection and anomaly "
     "identification, Generative AI for contextual analysis and narrative synthesis, and Agentic automation for "
     "orchestrated, multi-step investigation and recommendation generation"),
    ("THEN", TEAL,
     "Pricing, product and proposition decision-makers receive timely, evidence-based, explainable recommendations "
     "— enabling faster, better-informed interventions with the confidence to act on AI-generated intelligence "
     "within a clear human governance framework"),
]
for i, (label, color, body) in enumerate(hyp_blocks):
    by = Inches(0.92 + i * 1.55)
    bh = Inches(1.4)
    add_rect(slide, Inches(0.18), by, SLIDE_W - Inches(0.36), bh, fill_rgb=LIGHT)
    add_rect(slide, Inches(0.18), by, Inches(0.9), bh, fill_rgb=color)
    add_textbox(slide, Inches(0.3), by + Inches(0.52), Inches(0.7), Inches(0.4),
                label, font_size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(slide, Inches(1.2), by + Inches(0.2), SLIDE_W - Inches(1.55), Inches(1.05),
                body, font_size=10.5, color=SUB, wrap=True)

# RESULTING IN bar
ri_y = Inches(5.6)
add_rect(slide, Inches(0.18), ri_y, SLIDE_W - Inches(0.36), Inches(1.1), fill_rgb=NAVY)
add_rect(slide, Inches(0.18), ri_y, Inches(0.08), Inches(1.1), fill_rgb=GOLD)
add_textbox(slide, Inches(0.38), ri_y + Inches(0.08), Inches(3.0), Inches(0.25),
            "RESULTING IN", font_size=9, bold=True, color=GOLD)
add_textbox(slide, Inches(0.38), ri_y + Inches(0.35), SLIDE_W - Inches(0.7), Inches(0.7),
            "Improved PCW ranking position and conversion performance  |  Reduced time from market signal to "
            "business action  |  Lower FTE effort on monitoring and analysis  |  A reusable, extensible AI "
            "platform capability that strengthens LBG's competitive position across General Insurance",
            font_size=10, color=WHITE, wrap=True)

# ===========================================================================
# SLIDE 6 — AI Capability Spectrum
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "AI TECHNOLOGY STRATEGY", "AI Capability Spectrum — Right Tool, Right Problem", 6, TOTAL)

ai_cols = [
    {
        "header": "Machine Learning",
        "sub": "Pattern Detection & Prediction",
        "color": ACCENT,
        "uses": [
            "PCW ranking trend prediction",
            "Price elasticity modelling",
            "Competitor behaviour clustering",
            "Anomaly detection in market data",
            "Quote conversion propensity scoring",
            "Demand forecasting by channel",
        ],
        "chars": "High accuracy on structured data. Explainable outputs. Production-proven at LBG scale. Low inference latency.",
    },
    {
        "header": "Generative AI",
        "sub": "Analysis & Synthesis",
        "color": TEAL,
        "uses": [
            "Competitor proposition narrative summarisation",
            "Executive briefing generation",
            "Recommendation rationale drafting",
            "Market commentary synthesis",
            "Regulatory change impact assessment",
            "Customer review sentiment analysis",
        ],
        "chars": "Transforms unstructured data into actionable insight. Reduces analyst effort. Generates explainable, readable outputs.",
    },
    {
        "header": "Agentic Automation",
        "sub": "Orchestration & Decision Support",
        "color": PURPLE,
        "uses": [
            "Multi-step competitor investigation workflows",
            "Autonomous PCW data collection and validation",
            "Triggered analysis on market movement events",
            "Cross-agent intelligence aggregation",
            "Simulation scenario orchestration",
            "Governance escalation routing",
        ],
        "chars": "Combines ML and GenAI capabilities. Executes complex, multi-step workflows. Human oversight at defined decision gates.",
    },
]
col_w = Inches(3.9)
col_h = Inches(6.2)
for i, col in enumerate(ai_cols):
    cx = Inches(0.18 + i * 3.1)  # tighter spacing to leave room for right col
    cy = Inches(0.88)
    # Adjust widths to fit: 3 cols of 3.1 = 9.3, leaving 4.03 for right panel
    actual_w = Inches(2.9)
    add_rect(slide, cx, cy, actual_w, col_h, fill_rgb=LIGHT)
    add_rect(slide, cx, cy, actual_w, Inches(0.05), fill_rgb=col["color"])
    add_textbox(slide, cx + Inches(0.1), cy + Inches(0.1), actual_w - Inches(0.15), Inches(0.3),
                col["header"], font_size=12, bold=True, color=NAVY)
    add_textbox(slide, cx + Inches(0.1), cy + Inches(0.42), actual_w - Inches(0.15), Inches(0.25),
                col["sub"], font_size=9, italic=True, color=col["color"])
    # Use cases
    add_bullet_list(slide, cx + Inches(0.1), cy + Inches(0.75), actual_w - Inches(0.15),
                    Inches(3.6), col["uses"], font_size=9, color=SUB)
    # Characteristics box
    char_y = cy + Inches(4.5)
    add_rect(slide, cx, char_y, actual_w, Inches(1.5), fill_rgb=WARM)
    add_textbox(slide, cx + Inches(0.08), char_y + Inches(0.05), actual_w - Inches(0.15), Inches(0.2),
                "Characteristics", font_size=8, bold=True, color=col["color"])
    add_textbox(slide, cx + Inches(0.08), char_y + Inches(0.28), actual_w - Inches(0.15), Inches(1.15),
                col["chars"], font_size=8.5, italic=True, color=SUB, wrap=True)

# Right column — LBG Platform Foundation
rx = Inches(9.18)
rw = Inches(3.95)
add_rect(slide, rx, Inches(0.88), rw, col_h, fill_rgb=NAVY)
add_textbox(slide, rx + Inches(0.12), Inches(0.98), rw - Inches(0.2), Inches(0.3),
            "LBG Platform", font_size=12, bold=True, color=GOLD)
add_textbox(slide, rx + Inches(0.12), Inches(1.3), rw - Inches(0.2), Inches(0.22),
            "Foundation Capabilities", font_size=8.5, italic=True, color=MUTED)

platform_items = [
    "Cloud Infrastructure (Azure)",
    "Data Platform & Feature Store",
    "MLOps & Model Registry",
    "LLM Gateway & Prompt Layer",
    "API Management (Apigee)",
    "Governance & Audit Framework",
    "Pega Workflow Engine",
]
for j, item in enumerate(platform_items):
    iy = Inches(1.6 + j * 0.72)
    add_rect(slide, rx + Inches(0.1), iy, rw - Inches(0.2), Inches(0.6),
             fill_rgb=RGBColor(0x14, 0x24, 0x42))
    add_textbox(slide, rx + Inches(0.22), iy + Inches(0.15), rw - Inches(0.4), Inches(0.32),
                item, font_size=9, bold=True, color=WHITE)

# ===========================================================================
# SLIDE 7 — Target Operating Model
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "TARGET OPERATING MODEL", "Target Operating Model — AI-Powered Continuous Intelligence Cycle", 7, TOTAL)

tom_steps = [
    ("SENSE", ACCENT, "Automated collection of PCW market data across all monitored competitors, channels and product lines. Triggered by schedule and event.", "[ML + Agentic]"),
    ("ANALYSE", MID, "ML models detect ranking shifts, pricing anomalies and proposition changes. Patterns classified by significance, velocity and likely cause.", "[ML + GenAI]"),
    ("SIMULATE", TEAL, "Simulation models evaluate the likely commercial impact of potential interventions — pricing changes, excess adjustments, offer additions — before recommendation.", "[ML]"),
    ("RECOMMEND", PURPLE, "GenAI synthesises analysis into clear, structured, explainable recommendations — pricing actions, product changes, offer adjustments — with supporting evidence.", "[GenAI + Agentic]"),
    ("GOVERN", GOLD, "Recommendations routed to appropriate human approvers via Pega workflow. Full context, rationale and risk assessment provided. Approval, rejection or modification recorded.", "[Human + Pega]"),
    ("EXECUTE", GREEN, "Approved changes implemented through AGGS, Duck Creek and Pricing Services APIs. Execution confirmed and logged. Change impact tracking initiated.", "[Agentic + Integration]"),
    ("LEARN", RED, "Outcome measurement compares pre- and post-intervention PCW performance. Model performance evaluated. Recommendation quality scores updated. Models retrained as required.", "[ML + GenAI]"),
]
n_steps = len(tom_steps)
step_w = Inches(1.75)
step_h = Inches(5.7)
step_gap = Inches(0.07)
start_x = Inches(0.18)
for i, (label, color, desc, ai_tag) in enumerate(tom_steps):
    sx = start_x + i * (step_w + step_gap)
    sy = Inches(0.9)
    add_rect(slide, sx, sy, step_w, step_h, fill_rgb=LIGHT)
    add_rect(slide, sx, sy, step_w, Inches(0.4), fill_rgb=color)
    add_textbox(slide, sx + Inches(0.05), sy + Inches(0.1), step_w - Inches(0.08), Inches(0.25),
                label, font_size=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(slide, sx + Inches(0.08), sy + Inches(0.5), step_w - Inches(0.12), Inches(4.6),
                desc, font_size=8.5, color=SUB, wrap=True)
    add_textbox(slide, sx + Inches(0.08), sy + Inches(5.2), step_w - Inches(0.12), Inches(0.3),
                ai_tag, font_size=8, bold=True, color=color)

# ===========================================================================
# SLIDE 8 — LBG AI Platform Capabilities
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "PLATFORM CAPABILITIES", "LBG AI Platform — Existing Capabilities Leveraged", 8, TOTAL)

# Left grid — 3x3
grid_cards = [
    # Row 1
    ("Data Ingestion & Enrichment", ACCENT,
     "Real-time and batch data pipelines. PCW data normalisation, validation and enrichment. Feature engineering for ML models. Data lineage and quality monitoring."),
    ("ML Model Platform", MID,
     "Centrally managed model registry. A/B testing and champion/challenger framework. Automated retraining pipelines. Model performance dashboards. Explainability layer (SHAP/LIME)."),
    ("LLM & GenAI Gateway", TEAL,
     "Managed access to foundation models (Azure OpenAI). Prompt versioning and management. Response caching and cost governance. Hallucination detection and output validation."),
    # Row 2
    ("Agentic Orchestration Layer", PURPLE,
     "Multi-agent workflow coordination. Tool use and API integration framework. State management and context persistence. Human-in-the-loop escalation triggers."),
    ("API & Integration Layer", GOLD,
     "Apigee-managed API gateway. Pre-built connectors: AGGS, Duck Creek, Pega. Event-driven integration patterns. Rate limiting, security and audit logging."),
    ("Observability & Monitoring", GREEN,
     "End-to-end pipeline monitoring. Model drift detection and alerting. Data quality scoring. Recommendation acceptance rate tracking. Business KPI dashboards."),
    # Row 3
    ("Governance & Audit", NAVY,
     "FCA-aligned model governance framework. Full decision lineage and audit trail. Role-based access controls. Approved model change process."),
    ("Pega Workflow Engine", MID,
     "Configurable approval workflows. SLA management and escalation rules. Decision record management. Integration with pricing and product teams."),
    ("Security & Compliance", RED,
     "PII detection and masking. Data residency controls (UK). Penetration-tested API layer. GDPR-aligned data retention policies."),
]
card_w = Inches(2.45)
card_h = Inches(1.9)
card_gap = Inches(0.1)
for i, (title, color, body) in enumerate(grid_cards):
    row = i // 3
    col = i % 3
    cx = Inches(0.18) + col * (card_w + card_gap)
    cy = Inches(0.9) + row * (card_h + card_gap)
    add_rect(slide, cx, cy, card_w, card_h, fill_rgb=LIGHT)
    add_rect(slide, cx, cy, card_w, Inches(0.05), fill_rgb=color)
    add_textbox(slide, cx + Inches(0.08), cy + Inches(0.1), card_w - Inches(0.12), Inches(0.28),
                title, font_size=9.5, bold=True, color=NAVY)
    add_textbox(slide, cx + Inches(0.08), cy + Inches(0.42), card_w - Inches(0.12), Inches(1.4),
                body, font_size=8.5, color=SUB, wrap=True)

# Right section — Build vs Reuse
rx = Inches(7.75)
rw = Inches(5.3)
add_textbox(slide, rx, Inches(0.9), rw, Inches(0.28), "Build vs Reuse Principle",
            font_size=13, bold=True, color=NAVY)

reuse_items = [
    (GREEN, "REUSE",
     "Apigee, AGGS, Duck Creek, Pega and the existing data platform are reused. No parallel infrastructure created."),
    (MID, "EXTEND",
     "ML model platform and MLOps tooling extended with new PCW-specific features, models and pipelines."),
    (TEAL, "CONFIGURE",
     "LLM Gateway configured with PCW domain prompts, guardrails and output schemas."),
    (ACCENT, "BUILD",
     "Agentic orchestration layer and PCW-specific agent logic are net-new capabilities built on the existing platform."),
]
for j, (strip, label, body) in enumerate(reuse_items):
    iy = Inches(1.27 + j * 1.45)
    ih = Inches(1.3)
    add_rect(slide, rx, iy, rw, ih, fill_rgb=WARM)
    add_rect(slide, rx, iy, Inches(0.05), ih, fill_rgb=strip)
    add_textbox(slide, rx + Inches(0.12), iy + Inches(0.1), Inches(1.2), Inches(0.28),
                label, font_size=9, bold=True, color=strip)
    add_textbox(slide, rx + Inches(0.12), iy + Inches(0.38), rw - Inches(0.2), Inches(0.85),
                body, font_size=9, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 9 — Capability Architecture (5-layer)
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "CAPABILITY ARCHITECTURE", "Platform Architecture — Five-Layer Capability Model", 9, TOTAL)

layers = [
    ("Market Intelligence", ACCENT, [
        "PCW ranking capture (all channels)",
        "Competitor price monitoring",
        "Product & excess tracking",
        "Offer & promotion detection",
        "Frequency: near real-time",
        "Coverage: all active PCWs",
    ]),
    ("Insight Layer", MID, [
        "ML trend detection models",
        "Ranking movement classification",
        "Competitor strategy inference",
        "Gap & opportunity scoring",
        "Anomaly flagging (price/product)",
        "Insight confidence scoring",
    ]),
    ("Recommendation", TEAL, [
        "Pricing action recommendations",
        "Excess adjustment proposals",
        "Offer optimisation suggestions",
        "Product feature gap alerts",
        "Simulation-backed evidence",
        "Priority and urgency scoring",
    ]),
    ("Governance", PURPLE, [
        "Human approval via Pega",
        "Tiered authorisation controls",
        "Audit trail & decision log",
        "FCA explainability outputs",
        "Rejection feedback loop",
        "Compliance change records",
    ]),
    ("Execution", GREEN, [
        "AGGS rate submissions",
        "Duck Creek policy updates",
        "Pricing Services API calls",
        "Product config updates",
        "Execution confirmation logging",
        "Post-change monitoring trigger",
    ]),
]
lyr_w = Inches(2.45)
lyr_h = Inches(5.85)
lyr_gap = Inches(0.12)
for i, (title, color, items) in enumerate(layers):
    lx = Inches(0.18) + i * (lyr_w + lyr_gap)
    ly = Inches(0.88)
    add_rect(slide, lx, ly, lyr_w, lyr_h, fill_rgb=LIGHT)
    add_rect(slide, lx, ly, lyr_w, Inches(0.45), fill_rgb=color)
    add_textbox(slide, lx + Inches(0.08), ly + Inches(0.1), lyr_w - Inches(0.12), Inches(0.28),
                title, font_size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for j, item in enumerate(items):
        iy = ly + Inches(0.6 + j * 0.83)
        add_rect(slide, lx + Inches(0.1), iy, lyr_w - Inches(0.2), Inches(0.72),
                 fill_rgb=WHITE)
        add_rect(slide, lx + Inches(0.1), iy, Inches(0.04), Inches(0.72), fill_rgb=color)
        add_textbox(slide, lx + Inches(0.2), iy + Inches(0.1), lyr_w - Inches(0.35), Inches(0.55),
                    item, font_size=8.5, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 10 — Intelligence Architecture (Multi-Agent)
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "INTELLIGENCE ARCHITECTURE", "Multi-Agent Intelligence Architecture", 10, TOTAL)

# Orchestrator bar
orch_y = Inches(0.9)
add_rect(slide, Inches(0.18), orch_y, SLIDE_W - Inches(0.36), Inches(0.85), fill_rgb=NAVY)
add_rect(slide, Inches(0.18), orch_y, Inches(0.08), Inches(0.85), fill_rgb=GOLD)
add_textbox(slide, Inches(0.35), orch_y + Inches(0.08), Inches(5.0), Inches(0.22),
            "ORCHESTRATOR AGENT", font_size=9, bold=True, color=GOLD)
add_textbox(slide, Inches(0.35), orch_y + Inches(0.32), SLIDE_W - Inches(0.65), Inches(0.45),
            "Coordinates end-to-end workflow. Routes tasks between specialist agents. Manages execution state, "
            "handles failures, aggregates outputs and escalates to human governance tiers. "
            "Implemented as an Agentic AI controller with tool-use capability.",
            font_size=8.5, color=MUTED, wrap=True)

# 8 agent cards 4x2
agents = [
    (ACCENT, "Market Collection Agent",
     "Autonomously navigates PCW data sources. Collects pricing, product, excess and offer data across all monitored competitors. Validates data integrity and enriches with metadata.",
     "Technology: Agentic + ML validation"),
    (MID, "Position Intelligence Agent",
     "Analyses ranking movement across PCW channels. Detects velocity and direction of rank changes. Classifies movements by significance and likely driver.",
     "Technology: ML (time-series, classification)"),
    (TEAL, "Competitor Analysis Agent",
     "Investigates identified market changes to determine root cause. Cross-references pricing, product and offer data. Produces structured competitive assessments.",
     "Technology: GenAI + ML"),
    (PURPLE, "Pricing Intelligence Agent",
     "Evaluates LBG pricing competitiveness at segment and risk-group level. Identifies pricing gaps and over-competitiveness. Feeds pricing team recommendations.",
     "Technology: ML (regression, optimisation)"),
    (GOLD, "Proposition Intelligence Agent",
     "Monitors competitor product features, excess structures and optional covers. Identifies proposition gaps and differentiators. Tracks cover innovation across the market.",
     "Technology: GenAI + ML"),
    (RED, "Simulation Agent",
     "Models the likely commercial outcomes of proposed interventions. Runs pricing elasticity simulations. Quantifies expected ranking, volume and margin impact.",
     "Technology: ML (simulation, elasticity)"),
    (GREEN, "Recommendation Agent",
     "Synthesises all agent outputs into prioritised, structured recommendations. Generates human-readable rationale. Assigns confidence and urgency scores.",
     "Technology: GenAI (structured output)"),
    (RGBColor(0x08, 0x91, 0xB2), "Learning Agent",
     "Tracks recommendation acceptance and outcome performance. Updates model feature stores with intervention outcomes. Identifies systematic recommendation errors.",
     "Technology: ML + GenAI"),
]
ag_w = Inches(3.0)
ag_h = Inches(2.55)
ag_gap_x = Inches(0.2)
ag_gap_y = Inches(0.15)
ag_start_y = Inches(1.9)
for i, (color, title, desc, tech) in enumerate(agents):
    row = i // 4
    col = i % 4
    ax = Inches(0.18) + col * (ag_w + ag_gap_x)
    ay = ag_start_y + row * (ag_h + ag_gap_y)
    add_rect(slide, ax, ay, ag_w, ag_h, fill_rgb=LIGHT)
    add_rect(slide, ax, ay, ag_w, Inches(0.05), fill_rgb=color)
    add_textbox(slide, ax + Inches(0.1), ay + Inches(0.1), ag_w - Inches(0.15), Inches(0.28),
                title, font_size=9.5, bold=True, color=NAVY)
    add_textbox(slide, ax + Inches(0.1), ay + Inches(0.42), ag_w - Inches(0.15), Inches(1.6),
                desc, font_size=8.5, color=SUB, wrap=True)
    add_textbox(slide, ax + Inches(0.1), ay + Inches(2.18), ag_w - Inches(0.15), Inches(0.3),
                tech, font_size=8, bold=True, color=color)

# ===========================================================================
# SLIDE 11 — Integration with LBG Architecture
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "INTEGRATION ARCHITECTURE", "Integration with LBG Technology Estate", 11, TOTAL)

# Left column
lx = Inches(0.18)
lw = Inches(7.6)
ly = Inches(0.88)
add_textbox(slide, lx, ly, lw, Inches(0.28), "Existing Strategic Investments",
            font_size=13, bold=True, color=NAVY)

systems = [
    ("AGGS", "Quote aggregation & PCW submission", ACCENT),
    ("Apigee", "API gateway & security", MID),
    ("Pega", "Governance workflow & approvals", PURPLE),
    ("Duck Creek", "Policy administration & rating", TEAL),
    ("Pricing Services", "Rate engine & band management", GREEN),
    ("Product Services", "Cover configuration & rules", GOLD),
    ("Data Platform", "Feature store & ML pipelines", NAVY),
]
for i, (sys_name, sys_note, color) in enumerate(systems):
    sy = Inches(1.22 + i * 0.6)
    add_rect(slide, lx, sy, lw, Inches(0.52), fill_rgb=LIGHT)
    add_rect(slide, lx, sy, Inches(0.05), Inches(0.52), fill_rgb=color)
    add_textbox(slide, lx + Inches(0.12), sy + Inches(0.06), Inches(1.8), Inches(0.35),
                sys_name, font_size=10, bold=True, color=NAVY)
    add_textbox(slide, lx + Inches(2.0), sy + Inches(0.06), lw - Inches(2.2), Inches(0.35),
                sys_note, font_size=9, color=SUB)

# Principle box
pb_y = Inches(5.5)
add_rect(slide, lx, pb_y, lw, Inches(1.15), fill_rgb=WARM)
add_rect(slide, lx, pb_y, Inches(0.05), Inches(1.15), fill_rgb=NAVY)
add_textbox(slide, lx + Inches(0.12), pb_y + Inches(0.1), lw - Inches(0.2), Inches(0.25),
            "Architecture Principle", font_size=9, bold=True, color=NAVY)
add_textbox(slide, lx + Inches(0.12), pb_y + Inches(0.38), lw - Inches(0.2), Inches(0.7),
            "The platform is designed as a capability layer on top of LBG's existing technology estate. "
            "No duplication of core systems. All changes flow through established integration patterns "
            "with full audit and governance.",
            font_size=9, italic=True, color=SUB, wrap=True)

# Right flow diagram
rx = Inches(8.05)
rw = Inches(5.1)
flow_nodes = [
    ("PCWs -- Real-Time Market Data", ACCENT),
    ("Competitive Intelligence Platform -- AI Agents & Models", MID),
    ("LBG Data Platform -- Feature Store & ML Registry", TEAL),
    ("Apigee -- API Management & Security", SUB),
    ("AGGS / Duck Creek / Pricing Services", GREEN),
    ("Pega -- Governance Workflow & Approval", PURPLE),
    ("Business Users -- Review, Approve & Monitor", NAVY),
]
fn_h = Inches(0.65)
fn_gap = Inches(0.13)
for i, (label, color) in enumerate(flow_nodes):
    fy = Inches(0.88) + i * (fn_h + fn_gap)
    add_rect(slide, rx, fy, rw, fn_h, fill_rgb=color)
    txt_color = WHITE if color not in [LIGHT, WARM] else TEXT
    add_textbox(slide, rx + Inches(0.12), fy + Inches(0.18), rw - Inches(0.2), Inches(0.35),
                label, font_size=9, bold=True, color=WHITE)
    # Arrow
    if i < len(flow_nodes) - 1:
        arr_y = fy + fn_h + Inches(0.02)
        add_textbox(slide, rx + rw / 2 - Inches(0.15), arr_y, Inches(0.3), Inches(0.1),
                    "v", font_size=7, color=MUTED, align=PP_ALIGN.CENTER)

# ===========================================================================
# SLIDE 12 — Human-in-the-Loop Governance
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "GOVERNANCE MODEL", "Human-in-the-Loop Governance Framework", 12, TOTAL)

tiers = [
    ("Tier 1", "AUTO", GREEN, "Market Monitoring & Data Collection",
     "Fully automated. ML and Agentic agents continuously collect, validate and process PCW market data. "
     "No human intervention required in steady-state operation. Exceptions escalated automatically. "
     "SLA: continuous, <15 min data freshness."),
    ("Tier 2", "ANALYSE", MID, "Intelligence Generation & Analysis",
     "AI-driven. ML models and GenAI analyse collected data, detect patterns, assess significance and generate "
     "contextual intelligence. Outputs reviewed by automated quality checks before escalation. "
     "SLA: <30 minutes from data collection to insight."),
    ("Tier 3", "RECOMMEND", GOLD, "Recommendation Review & Refinement",
     "Human review required. Pricing and proposition teams receive AI-generated recommendations with full evidence, "
     "rationale and simulated impact. Teams can approve, modify or reject. All decisions recorded in audit log. "
     "SLA: same-day review for urgent signals."),
    ("Tier 4", "APPROVE", PURPLE, "Governance Approval & Sign-Off",
     "Senior approval required for material changes. Delegated authority framework applied. Pega workflow manages "
     "routing, escalation and SLA compliance. Full decision record created. Compliance team notified for "
     "significant pricing movements."),
    ("Tier 5", "EXECUTE & LEARN", RED, "Execution & Outcome Measurement",
     "Approved changes implemented through API integrations. Change confirmation logged. Post-implementation "
     "monitoring initiated automatically. Outcome data fed back to Learning Agent within defined measurement window."),
]
tier_h = Inches(1.08)
tier_gap = Inches(0.08)
for i, (tier_n, badge, color, title, desc) in enumerate(tiers):
    ty = Inches(0.9) + i * (tier_h + tier_gap)
    add_rect(slide, Inches(0.18), ty, SLIDE_W - Inches(0.36), tier_h, fill_rgb=LIGHT)
    # Badge
    add_rect(slide, Inches(0.18), ty, Inches(1.5), tier_h, fill_rgb=color)
    add_textbox(slide, Inches(0.22), ty + Inches(0.1), Inches(1.4), Inches(0.25),
                tier_n, font_size=8, bold=True, color=WHITE)
    add_textbox(slide, Inches(0.22), ty + Inches(0.36), Inches(1.4), Inches(0.35),
                badge, font_size=10, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    # Title & desc
    add_textbox(slide, Inches(1.82), ty + Inches(0.08), Inches(10.5), Inches(0.3),
                title, font_size=10.5, bold=True, color=NAVY)
    add_textbox(slide, Inches(1.82), ty + Inches(0.42), Inches(10.5), Inches(0.6),
                desc, font_size=9, color=SUB, wrap=True)

# Principle bar
pb_y = Inches(6.5)
add_rect(slide, Inches(0.18), pb_y, SLIDE_W - Inches(0.36), Inches(0.65), fill_rgb=NAVY)
add_textbox(slide, Inches(0.35), pb_y + Inches(0.15), SLIDE_W - Inches(0.65), Inches(0.4),
            "The platform recommends. People decide. Systems execute. Outcomes measured. Always.",
            font_size=11, bold=True, italic=True, color=WHITE, align=PP_ALIGN.CENTER)

# ===========================================================================
# SLIDE 13 — Governance & Risk Framework
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "GOVERNANCE & RISK", "Governance & Risk Framework", 13, TOTAL)

gov_cards = [
    ("FCA Alignment", ACCENT,
     "Consumer Duty obligations met through explainable AI outputs and human decision accountability. "
     "Pricing decisions remain with authorised individuals. AI provides decision support, not autonomous pricing. "
     "Regular review of AI outputs against FCA fair value requirements."),
    ("Auditability", MID,
     "Complete decision lineage from market data collection through to executed change. Every recommendation, "
     "approval, modification and rejection recorded with timestamp, user identity and rationale. "
     "Audit trail accessible for regulatory review within defined SLAs."),
    ("Explainability", TEAL,
     "All AI recommendations accompanied by human-readable rationale. ML model outputs include feature importance "
     "and confidence scores. GenAI outputs include source data references. Pricing teams able to interrogate "
     "and challenge recommendations before approving."),
    ("Data Protection & Privacy", PURPLE,
     "No customer PII used in competitive intelligence workflows. Competitor market data treated as commercially "
     "sensitive. Role-based access controls applied. Data minimisation principles applied throughout. "
     "UK data residency maintained."),
    ("Model Governance", GOLD,
     "All ML models subject to LBG model governance policy. Pre-deployment validation, champion/challenger testing "
     "and post-deployment monitoring mandatory. Model performance reviewed quarterly. Retraining triggered "
     "automatically on drift detection."),
    ("Operational Resilience", GREEN,
     "Platform designed for graceful degradation — core pricing operations continue if intelligence platform is "
     "unavailable. Recovery time objectives defined per component. Manual fallback procedures documented and tested. "
     "Third-party dependency risk assessed and mitigated."),
]
gc_w = Inches(4.1)
gc_h = Inches(2.55)
gc_gap = Inches(0.12)
for i, (title, color, body) in enumerate(gov_cards):
    row = i // 3
    col = i % 3
    cx = Inches(0.18) + col * (gc_w + gc_gap)
    cy = Inches(0.9) + row * (gc_h + gc_gap)
    add_rect(slide, cx, cy, gc_w, gc_h, fill_rgb=LIGHT)
    add_rect(slide, cx, cy, gc_w, Inches(0.05), fill_rgb=color)
    add_textbox(slide, cx + Inches(0.12), cy + Inches(0.1), gc_w - Inches(0.2), Inches(0.3),
                title, font_size=11, bold=True, color=NAVY)
    add_textbox(slide, cx + Inches(0.12), cy + Inches(0.48), gc_w - Inches(0.2), Inches(2.0),
                body, font_size=8.5, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 14 — KPI & Measurement Framework
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "MEASUREMENT FRAMEWORK", "KPI & Measurement Framework", 14, TOTAL)

kpi_cols = [
    ("COMMERCIAL", ACCENT, [
        "PCW ranking position (by channel, brand, product)",
        "Quote conversion rate (PCW-sourced)",
        "New business volume (PCW channel)",
        "Revenue per PCW quote",
        "Market share by PCW (where measurable)",
        "Competitive win/loss rate",
    ]),
    ("OPERATIONAL", MID, [
        "Market data freshness (minutes)",
        "Time: signal to insight (target <30 min)",
        "Time: insight to recommendation (target <2 hrs)",
        "Time: recommendation to decision (target same day)",
        "FTE hours saved (monitoring & analysis)",
        "Recommendation throughput (per week)",
    ]),
    ("STRATEGIC", TEAL, [
        "Competitor coverage breadth (% of market monitored)",
        "Recommendation adoption rate (%)",
        "Recommendation accuracy (post-outcome)",
        "Intelligence latency vs competitors (estimated)",
        "Platform reuse across GI product lines",
        "Stakeholder satisfaction score (NPS)",
    ]),
    ("RISK & MODEL", RED, [
        "Audit compliance rate (100% target)",
        "Model performance vs baseline (monthly)",
        "Data quality score (% clean records)",
        "Governance SLA compliance (%)",
        "Model drift incidents (target zero)",
        "FCA review findings (target zero)",
    ]),
]
kc_w = Inches(3.1)
kc_h = Inches(6.0)
kc_gap = Inches(0.1)
for i, (label, color, kpis) in enumerate(kpi_cols):
    kx = Inches(0.18) + i * (kc_w + kc_gap)
    ky = Inches(0.88)
    add_rect(slide, kx, ky, kc_w, kc_h, fill_rgb=LIGHT)
    add_rect(slide, kx, ky, kc_w, Inches(0.45), fill_rgb=color)
    add_textbox(slide, kx + Inches(0.08), ky + Inches(0.1), kc_w - Inches(0.12), Inches(0.28),
                label, font_size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for j, kpi in enumerate(kpis):
        iy = ky + Inches(0.55 + j * 0.88)
        add_rect(slide, kx + Inches(0.08), iy, kc_w - Inches(0.16), Inches(0.78),
                 fill_rgb=WHITE)
        add_rect(slide, kx + Inches(0.08), iy, Inches(0.04), Inches(0.78), fill_rgb=color)
        add_textbox(slide, kx + Inches(0.18), iy + Inches(0.12), kc_w - Inches(0.3), Inches(0.58),
                    kpi, font_size=8.5, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 15 — Phased Delivery Roadmap
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "DELIVERY ROADMAP", "Phased Delivery Roadmap — Four Waves to Full Capability", 15, TOTAL)

waves_data = [
    ("Wave 1", "Market Visibility", "Months 1-3", ACCENT, [
        "PCW data collection pipeline",
        "Competitor baseline dataset",
        "Ranking capture (2 PCWs)",
        "Data quality framework",
        "Executive monitoring dashboard",
        "Initial ML anomaly detection",
        "Platform infrastructure setup",
        "Team onboarding & training",
    ]),
    ("Wave 2", "Intelligence", "Months 4-6", MID, [
        "ML trend detection models",
        "Competitor profiling capability",
        "GenAI analysis summaries",
        "Opportunity identification engine",
        "Expanded PCW coverage (all channels)",
        "Intelligence distribution workflow",
        "Model performance monitoring",
        "Stakeholder feedback loop",
    ]),
    ("Wave 3", "Decision Support", "Months 7-9", TEAL, [
        "Recommendation engine (ML+GenAI)",
        "Pega governance integration",
        "Tiered approval workflows",
        "Simulation capability (pricing)",
        "AGGS & Duck Creek integration",
        "Pricing team change management",
        "Delegated authority framework",
        "Audit & compliance tooling",
    ]),
    ("Wave 4", "Optimisation", "Months 10-12", PURPLE, [
        "Closed-loop Learning Agent",
        "Continuous optimisation models",
        "Advanced simulation (full proposition)",
        "Full agentic orchestration",
        "Platform extensibility (other GI lines)",
        "Performance benchmarking",
        "Retraining automation",
        "Scale & operate model",
    ]),
]
wv_w = Inches(3.1)
wv_h = Inches(6.1)
wv_gap = Inches(0.12)
for i, (wname, wtitle, wmonths, color, items) in enumerate(waves_data):
    wx = Inches(0.18) + i * (wv_w + wv_gap)
    wy = Inches(0.88)
    add_rect(slide, wx, wy, wv_w, wv_h, fill_rgb=LIGHT)
    add_rect(slide, wx, wy, wv_w, Inches(0.6), fill_rgb=color)
    add_textbox(slide, wx + Inches(0.1), wy + Inches(0.05), wv_w - Inches(0.15), Inches(0.22),
                wname, font_size=8.5, bold=True, color=WHITE)
    add_textbox(slide, wx + Inches(0.1), wy + Inches(0.28), wv_w - Inches(0.15), Inches(0.25),
                wtitle, font_size=10, bold=True, color=WHITE)
    add_textbox(slide, wx + Inches(0.1), wy + Inches(0.52), wv_w - Inches(0.15), Inches(0.2),  # months
                wmonths, font_size=8, color=RGBColor(0xE8, 0xE8, 0xE8))
    for j, item in enumerate(items):
        iy = wy + Inches(0.72 + j * 0.65)
        add_rect(slide, wx + Inches(0.1), iy, wv_w - Inches(0.2), Inches(0.58),
                 fill_rgb=WHITE)
        add_rect(slide, wx + Inches(0.1), iy, Inches(0.04), Inches(0.58), fill_rgb=color)
        add_textbox(slide, wx + Inches(0.2), iy + Inches(0.1), wv_w - Inches(0.35), Inches(0.42),
                    item, font_size=8.5, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 16 — Business Value Summary
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "BUSINESS VALUE", "Business Value Summary — The Case for Investment", 16, TOTAL)

value_cards = [
    ("Faster Market Response", ACCENT,
     "Reduce competitor response time from days to hours. Continuous sensing eliminates blindspots across all "
     "PCW channels simultaneously. Event-triggered alerts ensure material market movements are surfaced "
     "immediately to decision-makers — not discovered in the next scheduled review."),
    ("Better Commercial Outcomes", TEAL,
     "Data-driven recommendations improve PCW ranking position and conversion performance. Simulation capability "
     "ensures interventions are targeted and evidence-based. Closed-loop learning means recommendation quality "
     "improves continuously — compounding commercial benefit over time."),
    ("Operational Efficiency", GOLD,
     "Automated data collection and analysis significantly reduces FTE effort on low-value monitoring tasks. "
     "Pricing and proposition teams redirected to higher-value judgement work. Scalable architecture means "
     "broader market coverage without proportional headcount growth."),
    ("Reusable Strategic Platform", PURPLE,
     "Architecture is designed for extensibility beyond PCW competitive intelligence. ML models, GenAI "
     "capabilities and Agentic orchestration patterns are reusable across other LBG General Insurance use "
     "cases — broker channel monitoring, claims analytics, product performance intelligence."),
]
vc_w = Inches(6.3)
vc_h = Inches(2.85)
vc_gap = Inches(0.15)
positions = [
    (Inches(0.18), Inches(0.88)),
    (Inches(0.18) + vc_w + vc_gap, Inches(0.88)),
    (Inches(0.18), Inches(0.88) + vc_h + vc_gap),
    (Inches(0.18) + vc_w + vc_gap, Inches(0.88) + vc_h + vc_gap),
]
for i, (title, color, body) in enumerate(value_cards):
    vx, vy = positions[i]
    add_rect(slide, vx, vy, vc_w, vc_h, fill_rgb=LIGHT)
    add_rect(slide, vx, vy, vc_w, Inches(0.07), fill_rgb=color)
    add_rect(slide, vx, vy, Inches(0.07), vc_h, fill_rgb=color)
    add_textbox(slide, vx + Inches(0.18), vy + Inches(0.15), vc_w - Inches(0.25), Inches(0.32),
                title, font_size=13, bold=True, color=NAVY)
    add_textbox(slide, vx + Inches(0.18), vy + Inches(0.55), vc_w - Inches(0.25), Inches(2.15),
                body, font_size=10, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 17 — Risk & Assumptions
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=WHITE)
slide_chrome(slide, "RISK MANAGEMENT", "Key Risks, Assumptions & Mitigations", 17, TOTAL)

# Left — risk register
lx = Inches(0.18)
lw = Inches(7.8)
add_textbox(slide, lx, Inches(0.9), lw, Inches(0.28), "Risk Register",
            font_size=12, bold=True, color=NAVY)

# Table header
hx = lx
hy = Inches(1.22)
hh = Inches(0.32)
add_rect(slide, hx, hy, lw, hh, fill_rgb=NAVY)
headers = ["Risk", "Likelihood", "Impact", "Mitigation"]
widths = [Inches(3.0), Inches(0.9), Inches(0.7), Inches(3.2)]
xpos = hx
for h, w in zip(headers, widths):
    add_textbox(slide, xpos + Inches(0.05), hy + Inches(0.05), w - Inches(0.08), Inches(0.22),
                h, font_size=8.5, bold=True, color=WHITE)
    xpos += w

risks = [
    (RED, "Data quality and availability from PCW channels", "Medium", "High",
     "Data validation layer with quality scoring. Manual fallback procedures. Vendor relationships for data access."),
    (RED, "AI model accuracy below required threshold", "Medium", "High",
     "Champion/challenger framework. Phased rollout with human validation. Clear accuracy acceptance criteria before production."),
    (GOLD, "Business adoption and change management", "Medium", "Medium",
     "Pricing team co-design from Wave 1. Change management programme. Recommendation transparency builds trust incrementally."),
    (GOLD, "FCA scrutiny of AI-driven pricing inputs", "Low", "High",
     "Human decision accountability maintained throughout. Full explainability and audit trail. Legal & Compliance review at each wave gate."),
    (GREEN, "Integration complexity with core systems", "Low", "Medium",
     "Existing API patterns reused. Integration spikes in Wave 1. Apigee abstraction layer reduces coupling."),
]
row_h = Inches(0.88)
for i, (strip_color, risk, like, impact, mit) in enumerate(risks):
    ry = Inches(1.54) + i * (row_h + Inches(0.05))
    add_rect(slide, hx, ry, lw, row_h, fill_rgb=LIGHT)
    add_rect(slide, hx, ry, Inches(0.05), row_h, fill_rgb=strip_color)
    cells = [risk, like, impact, mit]
    xpos = hx
    for ci, (cell, cw) in enumerate(zip(cells, widths)):
        add_textbox(slide, xpos + Inches(0.08), ry + Inches(0.1), cw - Inches(0.12), row_h - Inches(0.15),
                    cell, font_size=8.5, color=SUB, wrap=True)
        xpos += cw

# Right — Key Assumptions
rx = Inches(8.1)
rw = Inches(5.0)
add_textbox(slide, rx, Inches(0.9), rw, Inches(0.28), "Key Assumptions",
            font_size=12, bold=True, color=NAVY)
assumptions = [
    "PCW data is available and accessible at sufficient frequency and quality to support near-real-time monitoring",
    "LBG's existing cloud and data platform can support the additional workloads introduced by the CI platform",
    "Pricing and proposition teams have capacity to engage in co-design and adopt AI-assisted workflows",
    "Regulatory environment does not materially change the framework for AI-assisted pricing decisions during delivery",
    "Business sponsorship and funding are confirmed prior to Wave 1 commencement",
]
for i, assumption in enumerate(assumptions):
    ay = Inches(1.22 + i * 1.05)
    ah = Inches(0.95)
    add_rect(slide, rx, ay, rw, ah, fill_rgb=WARM)
    add_rect(slide, rx, ay, Inches(0.05), ah, fill_rgb=MID)
    add_textbox(slide, rx + Inches(0.12), ay + Inches(0.1), rw - Inches(0.2), ah - Inches(0.12),
                assumption, font_size=8.5, color=SUB, wrap=True)

# ===========================================================================
# SLIDE 18 — Recommendation & Next Steps
# ===========================================================================
slide = prs.slides.add_slide(blank_layout)

# Dark navy background
add_rect(slide, 0, 0, SLIDE_W, SLIDE_H, fill_rgb=NAVY)
# Gold top bar
add_rect(slide, 0, 0, SLIDE_W, Inches(0.08), fill_rgb=GOLD)
# Gold left bar
add_rect(slide, 0, 0, Inches(0.08), SLIDE_H, fill_rgb=GOLD)

# Label
add_textbox(slide, Inches(0.25), Inches(0.2), Inches(9.0), Inches(0.3),
            "RECOMMENDATION & DECISION REQUIRED", font_size=9, bold=True, color=GOLD)

# Recommendation box
add_rect(slide, Inches(0.25), Inches(0.6), SLIDE_W - Inches(0.5), Inches(1.35),
         fill_rgb=RGBColor(0x12, 0x22, 0x3F))
add_rect(slide, Inches(0.25), Inches(0.6), Inches(0.07), Inches(1.35), fill_rgb=GOLD)
add_textbox(slide, Inches(0.42), Inches(0.68), SLIDE_W - Inches(0.75), Inches(1.15),
            "Proceed with a focused MVP targeting a single PCW channel and a defined set of pricing and "
            "proposition use cases. The MVP should validate the end-to-end workflow from data collection through "
            "to governed recommendation delivery — establishing confidence in the AI capability, governance model "
            "and commercial impact before scaling.",
            font_size=12, color=WHITE, wrap=True)

# Immediate next steps label
add_textbox(slide, Inches(0.25), Inches(2.1), Inches(5.0), Inches(0.28),
            "IMMEDIATE NEXT STEPS", font_size=9, bold=True, color=RGBColor(0xB0, 0xBB, 0xCC))

# 6 next steps in 2x3 grid
next_steps = [
    "Confirm executive sponsorship and investment approval for Wave 1",
    "Establish cross-functional delivery team (Pricing, Product, Technology, Risk)",
    "Select pilot PCW channel and define MVP scope with pricing team",
    "Conduct data availability assessment and PCW integration spike",
    "Define success criteria, baseline KPIs and measurement framework",
    "Commence Wave 1 delivery: platform infrastructure and data pipeline",
]
ns_w = Inches(6.2)
ns_h = Inches(1.0)
ns_gap_x = Inches(0.2)
ns_gap_y = Inches(0.12)
for i, step in enumerate(next_steps):
    row = i // 2
    col = i % 2
    nx = Inches(0.25) + col * (ns_w + ns_gap_x)
    ny = Inches(2.45) + row * (ns_h + ns_gap_y)
    add_rect(slide, nx, ny, ns_w, ns_h, fill_rgb=RGBColor(0x0C, 0x1C, 0x34))
    # Number square
    add_rect(slide, nx, ny, Inches(0.6), ns_h, fill_rgb=GOLD)
    add_textbox(slide, nx + Inches(0.05), ny + Inches(0.3), Inches(0.52), Inches(0.42),
                str(i + 1), font_size=16, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_textbox(slide, nx + Inches(0.7), ny + Inches(0.15), ns_w - Inches(0.85), ns_h - Inches(0.25),
                step, font_size=9.5, color=WHITE, wrap=True)

# Slide number
add_textbox(slide, Inches(12.3), SLIDE_H - Inches(0.32), Inches(0.9), Inches(0.25),
            f"18 / {TOTAL}", font_size=7.5, bold=False, color=MUTED, align=PP_ALIGN.RIGHT)

# Final quote bar
qb_y = SLIDE_H - Inches(0.65)
add_rect(slide, Inches(0.25), qb_y, SLIDE_W - Inches(0.5), Inches(0.45),
         fill_rgb=RGBColor(0x0C, 0x1C, 0x34))
add_textbox(slide, Inches(0.4), qb_y + Inches(0.08), SLIDE_W - Inches(0.8), Inches(0.32),
            "Transforming competitor monitoring into continuous competitive intelligence and optimisation "
            "-- powered by ML, GenAI and Agentic AI, governed by human oversight.",
            font_size=9, italic=True, color=MUTED, align=PP_ALIGN.CENTER)

# ===========================================================================
# Save
# ===========================================================================
prs.save("/home/user/rag/LBG_PCW_CI_Platform_v2.pptx")
print("Done")
