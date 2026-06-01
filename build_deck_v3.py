from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# ── Dimensions ───────────────────────────────────────────────────────────────
W = Inches(13.33)
H = Inches(7.5)

# ── Colour palette ────────────────────────────────────────────────────────────
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
DKNAVY = RGBColor(0x12, 0x22, 0x3F)
PANEL  = RGBColor(0x14, 0x24, 0x42)


# ── Core helpers ──────────────────────────────────────────────────────────────

def add_rect(slide, x, y, w, h, fill_rgb=None, line_rgb=None, line_pt=0.75):
    shape = slide.shapes.add_shape(1, x, y, w, h)
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
                color=TEXT, align=PP_ALIGN.LEFT, wrap=True):
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
    run.font.name = "Calibri"
    return tb


def slide_chrome(slide, eyebrow, title, n, total=20):
    add_rect(slide, Inches(0), Inches(0), Inches(0.07), H, fill_rgb=NAVY)
    add_rect(slide, Inches(0), H - Inches(0.07), W, Inches(0.07), fill_rgb=MID)
    add_textbox(slide, Inches(0.5), Inches(0.28), Inches(12), Inches(0.24),
                eyebrow, font_size=8, bold=True, color=ACCENT)
    add_textbox(slide, Inches(0.5), Inches(0.52), Inches(12), Inches(0.46),
                title, font_size=20, bold=True, color=NAVY)
    add_rect(slide, Inches(0.5), Inches(1.02), Inches(0.5), Inches(0.04), fill_rgb=GOLD)
    add_textbox(slide, W - Inches(1.1), H - Inches(0.35), Inches(1.0), Inches(0.25),
                f"{n:02d} / {total}", font_size=8, color=MUTED, align=PP_ALIGN.RIGHT)


def card_box(slide, x, y, w, h, top_color, bg=LIGHT):
    add_rect(slide, x, y, w, h, fill_rgb=bg, line_rgb=BORDER, line_pt=0.5)
    add_rect(slide, x, y, w, Inches(0.05), fill_rgb=top_color)


def label_text(slide, x, y, w, h, label, text, label_color=ACCENT, text_color=TEXT,
               label_size=7.5, text_size=10):
    add_textbox(slide, x, y, w, Inches(0.22), label, font_size=label_size,
                bold=True, color=label_color)
    add_textbox(slide, x, y + Inches(0.22), w, h - Inches(0.22), text,
                font_size=text_size, color=text_color)


def bullet_list(slide, x, y, w, h, items, font_size=9.5, color=SUB, indent="- "):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        if first:
            p = tf.paragraphs[0]; first = False
        else:
            p = tf.add_paragraph()
        p.space_before = Pt(1.5)
        run = p.add_run()
        run.text = f"{indent}{item}"
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        run.font.name = "Calibri"
    return tb


def mini_tag(slide, x, y, text, bg=LIGHT, fg=TEXT, size=8.5):
    w = Inches(len(text) * 0.075 + 0.25)
    add_rect(slide, x, y, w, Inches(0.24), fill_rgb=bg)
    add_textbox(slide, x + Inches(0.07), y + Inches(0.03), w - Inches(0.1), Inches(0.2),
                text, font_size=size, bold=True, color=fg, align=PP_ALIGN.CENTER)
    return w


def grid_cell(slide, x, y, w, h, items, font_size=8, bg=LIGHT):
    add_rect(slide, x, y, w, h, fill_rgb=bg, line_rgb=BORDER, line_pt=0.3)
    tb = slide.shapes.add_textbox(x + Inches(0.08), y + Inches(0.06),
                                   w - Inches(0.12), h - Inches(0.1))
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        if first:
            p = tf.paragraphs[0]; first = False
        else:
            p = tf.add_paragraph()
        p.space_before = Pt(1)
        r = p.add_run()
        r.text = item
        r.font.size = Pt(font_size)
        r.font.name = "Calibri"
        r.font.color.rgb = SUB


# ── Presentation ──────────────────────────────────────────────────────────────
prs = Presentation()
prs.slide_width = W
prs.slide_height = H
blank_layout = prs.slide_layouts[6]


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — Cover
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)

# Dark navy full background
add_rect(s, Inches(0), Inches(0), W, H, fill_rgb=NAVY)

# Gold top bar
add_rect(s, Inches(0), Inches(0), W, Inches(0.08), fill_rgb=GOLD)

# Gold left bar
add_rect(s, Inches(0), Inches(0), Inches(0.08), H, fill_rgb=GOLD)

# Right panel PANEL colour
add_rect(s, Inches(9.0), Inches(0), W - Inches(9.0), H, fill_rgb=PANEL)

# ── Left side ──
add_textbox(s, Inches(0.5), Inches(0.5), Inches(8.3), Inches(0.28),
            "LLOYDS BANKING GROUP  |  GENERAL INSURANCE  |  COMPETITIVE INTELLIGENCE",
            font_size=8, bold=True, color=GOLD)

add_textbox(s, Inches(0.5), Inches(1.1), Inches(8.3), Inches(0.55),
            "PCW Competitive Intelligence", font_size=32, bold=True, color=WHITE)
add_textbox(s, Inches(0.5), Inches(1.62), Inches(8.3), Inches(0.55),
            "& Optimisation Platform", font_size=32, bold=True, color=WHITE)

# Gold rule
add_rect(s, Inches(0.5), Inches(2.28), Inches(0.6), Inches(0.04), fill_rgb=GOLD)

add_textbox(s, Inches(0.5), Inches(2.4), Inches(8.3), Inches(0.3),
            "Transforming Market Monitoring into Continuous Competitive Advantage",
            font_size=12, italic=True, color=MUTED)

# Pill labels
add_textbox(s, Inches(0.5), Inches(2.85), Inches(8.3), Inches(0.3),
            "Machine Learning  |  Gemini / GenAI  |  ENVOY Agentic Platform",
            font_size=9.5, color=MUTED)

# Executive message box
add_rect(s, Inches(0.5), Inches(3.3), Inches(8.3), Inches(1.55), fill_rgb=DKNAVY)
add_rect(s, Inches(0.5), Inches(3.3), Inches(0.06), Inches(1.55), fill_rgb=GOLD)
add_textbox(s, Inches(0.65), Inches(3.38), Inches(8.0), Inches(1.4),
            "This platform harnesses the full AI capability of LBG's ENVOY Agentic Platform — "
            "combining ML-driven pricing models, Gemini-powered analysis and Agentic automation "
            "via the Agent Developer Kit (ADK) and Vertex AI Agent Engine — to deliver continuous, "
            "governed competitive intelligence across all Price Comparison Website channels.",
            font_size=9.5, color=WHITE)

# ── Right panel content ──
rx = Inches(9.2)
add_textbox(s, rx, Inches(0.18), Inches(3.8), Inches(0.28),
            "POWERED BY ENVOY", font_size=8, bold=True, color=GOLD)
add_textbox(s, rx, Inches(0.45), Inches(3.8), Inches(0.28),
            "Enterprise Agent Runtime & Governance Platform", font_size=9, italic=True, color=WHITE)

metrics = [
    ("30-50%", "Faster Intelligence Delivery vs Manual"),
    ("80%", "Reusable ENVOY Agent Components"),
    ("100%", "Governed Agent Calls via Cortex"),
    ("1 Platform", "Shared Across BCB General Insurance"),
    ("Full", "Observability & Traceability via ObserveAll"),
]
my = Inches(0.82)
for val, desc in metrics:
    add_rect(s, rx, my, Inches(3.9), Inches(0.42), fill_rgb=DKNAVY)
    add_rect(s, rx, my, Inches(0.06), Inches(0.42), fill_rgb=GOLD)
    add_textbox(s, rx + Inches(0.12), my + Inches(0.03), Inches(3.7), Inches(0.18),
                val, font_size=10, bold=True, color=GOLD)
    add_textbox(s, rx + Inches(0.12), my + Inches(0.21), Inches(3.7), Inches(0.18),
                desc, font_size=8, color=WHITE)
    my += Inches(0.48)

add_textbox(s, rx, my + Inches(0.05), Inches(3.8), Inches(0.22),
            "DELIVERY PHASES", font_size=8, bold=True, color=GOLD)
my += Inches(0.3)
waves = [
    ("Wave 1", "Months 1-3"),
    ("Wave 2", "Months 4-6"),
    ("Wave 3", "Months 7-9"),
    ("Wave 4", "Months 10-12"),
]
wave_colors = [ACCENT, MID, TEAL, PURPLE]
for (wn, wt), wc in zip(waves, wave_colors):
    add_rect(s, rx, my, Inches(3.9), Inches(0.38), fill_rgb=DKNAVY, line_rgb=wc, line_pt=0.75)
    add_textbox(s, rx + Inches(0.1), my + Inches(0.05), Inches(1.5), Inches(0.28),
                wn, font_size=9, bold=True, color=wc)
    add_textbox(s, rx + Inches(1.5), my + Inches(0.05), Inches(2.3), Inches(0.28),
                wt, font_size=9, color=WHITE)
    my += Inches(0.44)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Executive Summary
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "EXECUTIVE SUMMARY", "Strategic Context & Recommendation", 2)

cards = [
    (ACCENT, LIGHT, "THE OPPORTUNITY", ACCENT,
     "PCWs are a primary acquisition channel under continuous competitive pressure", NAVY,
     "Price Comparison Websites influence the majority of UK General Insurance new business. "
     "Customers simultaneously compare price, excess, features, add-ons and brand. Small rank "
     "changes drive material volume shifts. Competitors adjust positioning multiple times per week "
     "— creating both daily risk and opportunity for LBG.", SUB),
    (MID, LIGHT, "THE CHALLENGE", MID,
     "Current monitoring is periodic, manual and unable to match market velocity", NAVY,
     "LBG's current approach relies on scheduled manual market reviews conducted at irregular "
     "intervals. By the time trends are identified, analysed and escalated, the market has moved. "
     "Teams operate in silos with inconsistent data. No continuous cross-channel tracking, no "
     "simulation capability, no closed feedback loop exists.", SUB),
    (NAVY, NAVY, "THE RECOMMENDATION", GOLD,
     "Deploy an ENVOY-powered Competitive Intelligence & Optimisation Platform", WHITE,
     "Leverage LBG's ENVOY Agentic Platform — combining ML models, Gemini GenAI and ADK-"
     "orchestrated agents on Google Cloud — to continuously monitor PCW market signals, generate "
     "governed intelligence and recommend pricing and proposition actions with full human oversight "
     "via Pega workflow.", RGBColor(0xCC, 0xD6, 0xE8)),
]

cx = Inches(0.5)
for top_c, bg_c, lbl, lbl_c, ttl, ttl_c, body, body_c in cards:
    cw = Inches(4.0)
    ch = Inches(3.8)
    cy = Inches(1.2)
    add_rect(s, cx, cy, cw, ch, fill_rgb=bg_c, line_rgb=BORDER, line_pt=0.5)
    add_rect(s, cx, cy, cw, Inches(0.05), fill_rgb=top_c)
    if bg_c == NAVY:
        add_rect(s, cx, cy, Inches(0.06), ch, fill_rgb=GOLD)
    add_textbox(s, cx + Inches(0.12), cy + Inches(0.12), cw - Inches(0.2), Inches(0.22),
                lbl, font_size=7.5, bold=True, color=lbl_c)
    add_textbox(s, cx + Inches(0.12), cy + Inches(0.35), cw - Inches(0.2), Inches(0.5),
                ttl, font_size=11.5, bold=True, color=ttl_c)
    add_textbox(s, cx + Inches(0.12), cy + Inches(0.88), cw - Inches(0.2), Inches(2.75),
                body, font_size=9.5, color=body_c)
    cx += Inches(4.17)

# Outcome chips
add_textbox(s, Inches(0.5), Inches(5.15), Inches(6), Inches(0.22),
            "EXPECTED OUTCOMES", font_size=7.5, bold=True, color=MUTED)
outcomes = [
    "Improved PCW ranking position",
    "Faster competitor response",
    "Evidence-based pricing decisions",
    "Reduced analyst effort",
    "Reusable ENVOY platform capability",
]
ox = Inches(0.5)
for oc in outcomes:
    ow = Inches(2.45)
    add_rect(s, ox, Inches(5.38), ow, Inches(0.52), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, ox, Inches(5.38), Inches(0.05), Inches(0.52), fill_rgb=TEAL)
    add_textbox(s, ox + Inches(0.1), Inches(5.43), ow - Inches(0.15), Inches(0.42),
                oc, font_size=8.5, color=TEXT)
    ox += Inches(2.58)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — Why PCWs Matter
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "MARKET CONTEXT", "Why Price Comparison Websites Are Business-Critical", 3)

# Left column
lx = Inches(0.5)
add_textbox(s, lx, Inches(1.15), Inches(6.0), Inches(0.3),
            "The PCW Landscape", font_size=12, bold=True, color=NAVY)

left_cards = [
    ("Customer Behaviour & Channel Influence",
     "Over 80% of UK motor insurance customers use a PCW during their purchase journey. Home "
     "insurance PCW penetration continues to grow year-on-year as price sensitivity increases "
     "post cost-of-living pressures. Multi-quoting behaviour means customers actively compare "
     "LBG against 10+ competitors simultaneously on every PCW visit."),
    ("Ranking Economics & Volume Impact",
     "Positions 1-3 on a PCW results page capture a disproportionate share of clicks and quote "
     "completions. Analysis shows moving from position 5 to position 2 can increase quote volume "
     "by 30-50% depending on PCW, brand and product line. Rank position is determined by a "
     "combination of premium competitiveness, product features, excess levels and PCW algorithm weighting."),
    ("Competitor Velocity & Market Dynamics",
     "Competitors make pricing or proposition adjustments multiple times per week. Seasonal peaks, "
     "regulatory changes (e.g. FCA GI pricing rules), claims inflation events and competitor "
     "promotional campaigns all trigger rapid market responses. Without continuous monitoring, "
     "LBG cannot detect or respond to these movements before volume impact is felt."),
]
ly = Inches(1.5)
for ttl, body in left_cards:
    ch = Inches(1.7)
    add_rect(s, lx, ly, Inches(6.0), ch, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, lx, ly, Inches(0.05), ch, fill_rgb=ACCENT)
    add_textbox(s, lx + Inches(0.12), ly + Inches(0.08), Inches(5.8), Inches(0.26),
                ttl, font_size=10.5, bold=True, color=NAVY)
    add_textbox(s, lx + Inches(0.12), ly + Inches(0.35), Inches(5.8), Inches(1.3),
                body, font_size=9.5, color=SUB)
    ly += Inches(1.85)

# Right column
rx2 = Inches(6.8)
add_textbox(s, rx2, Inches(1.15), Inches(5.8), Inches(0.3),
            "Strategic Implications for LBG", font_size=12, bold=True, color=NAVY)

right_cards = [
    (MID, "Real-Time Intelligence is Now a Competitive Necessity",
     "Firms sensing and responding to market movements within hours — not days — consistently "
     "outperform on PCW conversion metrics. Intelligence latency is directly correlated with lost "
     "volume and missed revenue opportunity. Manual, periodic monitoring creates exploitable "
     "competitive windows.", Inches(1.5), NAVY),
    (MID, "Proposition is as Important as Price",
     "PCW ranking algorithms increasingly weight excess structures, optional cover inclusions, "
     "claims process ratings and customer review scores alongside raw premium. Competitive "
     "intelligence must span the full product proposition — not just price — requiring ML, GenAI "
     "and structured data analysis working in combination.", Inches(1.5), NAVY),
    (RED, "Current State Risk",
     "Without continuous monitoring, LBG risks sustained sub-optimal PCW positioning — "
     "particularly during competitor promotional campaigns, FCA-triggered repricing events or "
     "claims inflation cycles. Each monitoring gap represents potential lost new business volume.",
     Inches(1.35), RED),
]
ry = Inches(1.5)
for sc, ttl, body, ch, ttl_c in right_cards:
    add_rect(s, rx2, ry, Inches(5.8), ch, fill_rgb=WARM, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, rx2, ry, Inches(0.05), ch, fill_rgb=sc)
    add_textbox(s, rx2 + Inches(0.12), ry + Inches(0.08), Inches(5.6), Inches(0.26),
                ttl, font_size=10.5, bold=True, color=ttl_c)
    add_textbox(s, rx2 + Inches(0.12), ry + Inches(0.36), Inches(5.6), ch - Inches(0.42),
                body, font_size=9.5, color=SUB)
    ry += ch + Inches(0.18)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — Current State Assessment
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "CURRENT STATE", "How We Operate Today — Diagnosis", 4)

steps = [
    ("01 / MONITORING",
     "Periodic manual reviews conducted at irregular intervals. No continuous tracking. PCW "
     "coverage inconsistent across Motor, Home and other GI lines. Data captured in spreadsheets "
     "with no common format or taxonomy. Competitor changes detected days or weeks after occurrence."),
    ("02 / ANALYSIS",
     "Data consolidated manually across teams. No shared data model or single source of truth. "
     "Analysis duplicated by pricing, product and proposition teams independently. Historical data "
     "not systematically stored or compared. No automated pattern detection or anomaly alerting."),
    ("03 / DECISIONS",
     "Decisions rely on analyst judgement without systematic competitive context. Lead time from "
     "insight to decision ranges from days to weeks. No simulation capability. Commercial impact "
     "of proposed changes estimated manually with high uncertainty. Decisions made on incomplete information."),
    ("04 / EXECUTION",
     "Changes routed through multiple manual approval layers. Pricing, product and operations "
     "teams coordinated via email and meetings. No automated handoffs. Execution timelines "
     "variable. No systematic post-change impact measurement. Feedback loop to improve future decisions absent."),
    ("05 / OUTCOME",
     "Reactive posture — LBG responds to competitor actions rather than anticipating them. "
     "Opportunity windows missed during monitoring gaps. Manual effort high and not scalable. "
     "Cross-team coordination creates latency. No learning mechanism to improve process over time."),
]
step_colors = [ACCENT, MID, TEAL, PURPLE, RED]
sw = Inches(2.4)
sx = Inches(0.35)
sy = Inches(1.2)
sh = Inches(2.65)
for i, ((step_name, step_body), sc) in enumerate(zip(steps, step_colors)):
    add_rect(s, sx, sy, sw, sh, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, sx, sy, sw, Inches(0.38), fill_rgb=sc)
    add_textbox(s, sx + Inches(0.05), sy + Inches(0.07), sw - Inches(0.1), Inches(0.28),
                step_name, font_size=9, bold=True, color=WHITE)
    add_textbox(s, sx + Inches(0.08), sy + Inches(0.44), sw - Inches(0.12), sh - Inches(0.5),
                step_body, font_size=8.5, color=SUB)
    if i < 4:
        add_textbox(s, sx + sw + Inches(0.01), sy + Inches(0.1), Inches(0.06), Inches(0.28),
                    ">", font_size=11, bold=True, color=MUTED)
    sx += sw + Inches(0.07)

# Bottom two columns
by = Inches(4.1)
# Left friction card
add_rect(s, Inches(0.35), by, Inches(5.8), Inches(2.0), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
add_rect(s, Inches(0.35), by, Inches(5.8), Inches(0.05), fill_rgb=ACCENT)
add_textbox(s, Inches(0.47), by + Inches(0.1), Inches(5.6), Inches(0.3),
            "Key Friction Points", font_size=11, bold=True, color=NAVY)
bullet_list(s, Inches(0.47), by + Inches(0.45), Inches(5.6), Inches(1.45),
            ["No single source of truth for competitor positioning",
             "Analysis capability does not scale with market complexity",
             "Decision latency creates exploitable competitive windows",
             "No closed loop linking interventions to measured outcomes",
             "Siloed tooling and data across pricing, product and ops"],
            font_size=9.5)

# Right org impact card
add_rect(s, Inches(6.7), by, Inches(5.8), Inches(2.0), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
add_rect(s, Inches(6.7), by, Inches(5.8), Inches(0.05), fill_rgb=RED)
add_textbox(s, Inches(6.82), by + Inches(0.1), Inches(5.6), Inches(0.3),
            "Organisational Impact", font_size=11, bold=True, color=NAVY)
bullet_list(s, Inches(6.82), by + Inches(0.45), Inches(5.6), Inches(1.45),
            ["Sub-optimal PCW ranking during competitor campaign periods",
             "Pricing teams without full market context at point of decision",
             "Product gaps not identified until customer or broker feedback",
             "High FTE effort on low-value data collection and formatting",
             "Inconsistent competitive responses across product lines"],
            font_size=9.5)

# Result bar
add_rect(s, Inches(0.35), Inches(6.45), Inches(12.63), Inches(0.5),
         fill_rgb=RGBColor(0xFE, 0xF3, 0xC7))
add_rect(s, Inches(0.35), Inches(6.45), Inches(0.06), Inches(0.5), fill_rgb=GOLD)
add_textbox(s, Inches(0.5), Inches(6.5), Inches(12.3), Inches(0.4),
            "Net Result: Reactive rather than proactive market response — competitive advantage "
            "consistently ceded during monitoring gaps and analysis delays",
            font_size=9.5, bold=True, color=TEXT)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — Strategic Hypothesis
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "STRATEGIC RATIONALE", "The Strategic Hypothesis", 5)

blocks = [
    ("IF", ACCENT,
     "LBG establishes continuous, automated capture of competitor pricing, product, excess and "
     "proposition data across all active PCW channels — creating a real-time market intelligence "
     "feed independent of manual collection, scheduled reviews or individual analyst availability"),
    ("AND", MID,
     "This intelligence is processed by a layered AI stack on LBG's ENVOY platform — ML models "
     "(Vertex AI, Pegasus) for pattern detection and anomaly identification; Gemini for contextual "
     "analysis, narrative synthesis and recommendation rationale; and ADK-orchestrated Agentic "
     "workflows for multi-step investigation, simulation and governed recommendation delivery"),
    ("THEN", TEAL,
     "Pricing, product and proposition decision-makers receive timely, explainable, evidence-backed "
     "recommendations — enabling faster, better-informed interventions with confidence to act within "
     "a clear human governance framework, with all decisions recorded in a full FCA-compliant audit "
     "trail via Cortex and the ENVOY Audit Framework"),
]

by2 = Inches(1.2)
bh = Inches(0.9)
for lbl, lc, content in blocks:
    add_rect(s, Inches(0.5), by2, Inches(0.6), bh, fill_rgb=lc)
    add_textbox(s, Inches(0.5), by2 + Inches(0.28), Inches(0.6), Inches(0.36),
                lbl, font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(s, Inches(1.1), by2, Inches(11.73), bh, fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    add_textbox(s, Inches(1.2), by2 + Inches(0.1), Inches(11.5), bh - Inches(0.15),
                content, font_size=10.5, color=TEXT)
    by2 += Inches(1.0)

# Result bar
add_rect(s, Inches(0.5), Inches(4.3), Inches(12.33), Inches(1.0), fill_rgb=NAVY)
add_rect(s, Inches(0.5), Inches(4.3), Inches(0.06), Inches(1.0), fill_rgb=GOLD)
add_textbox(s, Inches(0.65), Inches(4.35), Inches(1.2), Inches(0.25),
            "RESULTING IN", font_size=8, bold=True, color=GOLD)
add_textbox(s, Inches(0.65), Inches(4.6), Inches(12.0), Inches(0.65),
            "Improved PCW ranking position and conversion performance  |  Reduced time from market "
            "signal to action from days to hours  |  Lower FTE effort on monitoring and analysis  |  "
            "A reusable, extensible AI platform capability across LBG General Insurance built on "
            "ENVOY's enterprise-grade governance, evaluation and observability stack",
            font_size=10, color=WHITE)

# Three metric boxes
metrics5 = [
    ("Speed", "Market signal to recommendation target < 2 hours (vs days currently)"),
    ("Coverage", "100% of active PCW channels monitored continuously (vs periodic spot checks)"),
    ("Governance", "100% of AI recommendations reviewed by human before execution"),
]
mx5 = Inches(0.5)
for mk, mv in metrics5:
    add_rect(s, mx5, Inches(5.5), Inches(3.9), Inches(0.8), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, mx5, Inches(5.5), Inches(3.9), Inches(0.05), fill_rgb=TEAL)
    add_textbox(s, mx5 + Inches(0.1), Inches(5.58), Inches(3.7), Inches(0.22),
                mk + ":", font_size=8.5, bold=True, color=TEAL)
    add_textbox(s, mx5 + Inches(0.1), Inches(5.78), Inches(3.7), Inches(0.48),
                mv, font_size=9, color=SUB)
    mx5 += Inches(4.02)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — ENVOY Platform Overview (Dense capability matrix)
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "ENVOY PLATFORM", "ENVOY — LBG's Enterprise Agentic AI Runtime", 6)

col_headers = [
    (ACCENT,   "1  AGENT RUNTIME"),
    (MID,      "2  ORCHESTRATION & COORDINATION"),
    (TEAL,     "3  KNOWLEDGE & CONTEXT"),
    (PURPLE,   "4  ENTERPRISE GOVERNANCE & GUARDRAILS"),
    (GREEN,    "5  EVALUATION & QUALITY"),
    (RGBColor(0x08, 0x91, 0xB2), "6  OBSERVABILITY & OPERATIONS"),
]
col_w = Inches(2.05)
col_gap = Inches(0.04)
grid_x0 = Inches(0.97)
row_h = Inches(1.22)

# Column headers
for ci, (hc, ht) in enumerate(col_headers):
    hx = grid_x0 + ci * (col_w + col_gap)
    add_rect(s, hx, Inches(1.15), col_w, Inches(0.4), fill_rgb=hc)
    add_textbox(s, hx + Inches(0.05), Inches(1.2), col_w - Inches(0.1), Inches(0.35),
                ht, font_size=7.5, bold=True, color=WHITE)

# Row labels
row_labels = [
    ("AGENTIC",          ACCENT, Inches(1.6)),
    ("ML MODELS",        MID,    Inches(2.82)),
    ("GEN AI",           TEAL,   Inches(4.04)),
    ("PLATFORM",         NAVY,   Inches(5.26)),
]
for rl, rc, ry in row_labels:
    add_rect(s, Inches(0.5), ry, Inches(0.42), row_h, fill_rgb=rc)
    add_textbox(s, Inches(0.5), ry + Inches(0.45), Inches(0.42), Inches(0.35),
                rl, font_size=7, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Grid data
grid_data = [
    # Row 1 AGENTIC
    [
        ["Agent execution engine", "Session & state management", "Memory & tool execution",
         "Multi-agent (A2A) execution", "MCP tool integration"],
        ["Workflow orchestration", "Agent coordination (A2A)", "Event-driven execution",
         "Long-running process mgmt", "Human-in-the-loop triggers", "Escalation & routing"],
        ["Context assembly", "RAG orchestration", "Cross-agent context sharing",
         "Knowledge retrieval", "Policy & rule retrieval", "MCP server access"],
        ["Enterprise guardrails", "PII masking & DLP", "Prompt protection",
         "Model routing (Cortex)", "Output validation", "Compliance controls"],
        ["Prompt evaluation", "Agent & workflow eval", "Hallucination detection",
         "Safety & bias checks", "Regression testing", "Golden dataset testing"],
        ["Agent traces & logs", "Tool & prompt visibility", "Cost & latency monitoring",
         "Drift & anomaly detection", "Audit trails & alerts", "SLA & reliability monitoring"],
    ],
    # Row 2 ML MODELS
    [
        ["Memory ranking", "Intent classification", "Tool recommendation", "Session summarisation"],
        ["Routing prediction", "Next best action", "SLA breach prediction", "Queue prioritisation"],
        ["Embedding generation", "Retrieval ranking", "Semantic similarity", "Context relevance scoring"],
        ["Toxicity detection", "PII detection (ML)", "Policy violation scoring", "Risk & confidence scoring"],
        ["Quality scoring", "Groundedness scoring", "Faithfulness scoring", "Model drift detection"],
        ["Anomaly detection", "Capacity prediction", "Failure prediction", "Usage forecasting"],
    ],
    # Row 3 GEN AI
    [
        ["Agent reasoning", "Tool use planning", "Memory summarisation", "Response generation"],
        ["Workflow planning", "Decision rationale", "Task decomposition", "Dynamic replanning"],
        ["RAG & retrieval", "Context synthesis", "Document summarisation", "Policy interpretation"],
        ["Guardrail reasoning", "Policy compliance check", "Output transformation", "Explanation generation"],
        ["Evaluation explanation", "Error analysis", "Test case generation", "Insight summarisation"],
        ["Anomaly explanation", "Incident summarisation", "Auto-remediation advice", "Operational insights"],
    ],
    # Row 4 PLATFORM SERVICES
    [
        ["Session Store", "Memory Store", "A2A Registry", "MCP Registry", "Tool Registry"],
        ["LangGraph", "Cloud Workflows", "Pub/Sub", "Eventarc", "Routing Rules Engine"],
        ["Vertex AI Vector Search", "BigQuery", "Cloud SQL (PostgreSQL)", "Knowledge Graph", "MCP Servers"],
        ["Cortex (Control Plane)", "Model Armor", "Policy Engine", "RBAC & ABAC", "Compliance Rules"],
        ["Pegasus (LBG)", "Vertex AI Evaluation", "ADK Evaluation", "Evaluation Framework", "Golden Test Suites"],
        ["ObserveAll", "Dynatrace", "Cloud Monitoring", "Cloud Logging", "Audit Framework"],
    ],
]

row_ys = [Inches(1.6), Inches(2.82), Inches(4.04), Inches(5.26)]
for ri, (row_items, ry) in enumerate(zip(grid_data, row_ys)):
    for ci, items in enumerate(row_items):
        cx2 = grid_x0 + ci * (col_w + col_gap)
        grid_cell(s, cx2, ry, col_w, row_h, items, font_size=7.5)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — AI Capability Spectrum Applied
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "AI TECHNOLOGY STRATEGY", "AI Capability Spectrum — Right Tool for the Right Problem", 7)

cols7 = [
    {
        "header": "Machine Learning",
        "sub": "Pattern Detection & Prediction",
        "hc": ACCENT,
        "tags": ["Vertex AI", "Pegasus (LBG)", "BigQuery ML"],
        "use_cases": ["PCW ranking trend prediction", "Price elasticity & demand modelling",
                      "Competitor behaviour clustering", "Anomaly detection in market data",
                      "Quote conversion propensity", "Market share estimation models"],
        "chars": "High accuracy on structured data. Explainable SHAP/LIME outputs. "
                 "Production-proven at LBG scale. Low inference latency. Champion/challenger tested via Pegasus.",
        "w": Inches(3.3),
    },
    {
        "header": "Generative AI (Gemini)",
        "sub": "Analysis, Synthesis & Explanation",
        "hc": TEAL,
        "tags": ["Gemini Pro", "Vertex AI", "RAG (BigQuery)"],
        "use_cases": ["Competitor proposition summarisation", "Executive intelligence briefing generation",
                      "Recommendation rationale drafting", "Market commentary synthesis",
                      "Regulatory change impact assessment", "Customer review sentiment analysis"],
        "chars": "Transforms unstructured data into actionable insight. Reduces analyst effort by "
                 "60-80% on synthesis tasks. Generates readable, explainable outputs. Governed via Model Armor and Cortex.",
        "w": Inches(3.3),
    },
    {
        "header": "Agentic AI (ENVOY / ADK)",
        "sub": "Orchestration & Multi-Step Automation",
        "hc": PURPLE,
        "tags": ["ENVOY ADK", "Vertex AI Agent Engine", "LangGraph"],
        "use_cases": ["Multi-step competitor investigation workflows",
                      "Autonomous PCW data collection & validation",
                      "Event-triggered market movement analysis",
                      "Cross-agent intelligence aggregation",
                      "Simulation scenario orchestration",
                      "Governance escalation & routing"],
        "chars": "Combines ML and GenAI in governed workflows. Executes complex multi-step tasks "
                 "autonomously. Human-in-the-loop at defined governance gates. Full observability via ObserveAll and Dynatrace.",
        "w": Inches(3.3),
    },
    {
        "header": "ENVOY Platform Foundation",
        "sub": None,
        "hc": NAVY,
        "tags": [],
        "use_cases": [],
        "chars": None,
        "w": Inches(2.85),
        "platform_items": [
            "Google Cloud (GCP)", "Vertex AI Agent Engine", "ADK (Agent Dev Kit)",
            "Gemini (LLM)", "Cortex (Control Plane)", "Pegasus (Evaluation)",
            "Model Armor (Safety)", "Apigee (API Gateway)", "Pega (Governance WF)",
            "ObserveAll / Dynatrace",
        ],
    },
]

c7x = Inches(0.5)
c7y = Inches(1.15)
c7h = Inches(6.15)
gap7 = Inches(0.12)

for col in cols7:
    cw7 = col["w"]
    add_rect(s, c7x, c7y, cw7, c7h, fill_rgb=WHITE if col["hc"] != NAVY else NAVY,
             line_rgb=BORDER, line_pt=0.4)
    add_rect(s, c7x, c7y, cw7, Inches(0.06), fill_rgb=col["hc"])

    if col["hc"] == NAVY:
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(0.12), cw7 - Inches(0.15), Inches(0.32),
                    col["header"], font_size=10, bold=True, color=GOLD)
        iy = c7y + Inches(0.52)
        for pi in col.get("platform_items", []):
            add_rect(s, c7x + Inches(0.1), iy, cw7 - Inches(0.2), Inches(0.42), fill_rgb=DKNAVY)
            add_textbox(s, c7x + Inches(0.15), iy + Inches(0.08), cw7 - Inches(0.3), Inches(0.28),
                        pi, font_size=9, color=WHITE)
            iy += Inches(0.48)
    else:
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(0.1), cw7 - Inches(0.15), Inches(0.28),
                    col["header"], font_size=11, bold=True, color=col["hc"])
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(0.38), cw7 - Inches(0.15), Inches(0.22),
                    col["sub"], font_size=9, color=col["hc"])
        # Tags
        tx7 = c7x + Inches(0.1)
        ty7 = c7y + Inches(0.65)
        for tag in col["tags"]:
            tw7 = Inches(len(tag) * 0.07 + 0.25)
            add_rect(s, tx7, ty7, tw7, Inches(0.22), fill_rgb=WARM)
            add_textbox(s, tx7 + Inches(0.05), ty7 + Inches(0.03), tw7 - Inches(0.05), Inches(0.18),
                        tag, font_size=7.5, bold=True, color=col["hc"])
            tx7 += tw7 + Inches(0.05)
        # Use cases
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(0.95), cw7 - Inches(0.15), Inches(0.22),
                    "PCW Use Cases", font_size=7.5, bold=True, color=MUTED)
        bullet_list(s, c7x + Inches(0.1), c7y + Inches(1.15), cw7 - Inches(0.15), Inches(1.5),
                    col["use_cases"], font_size=9.0, color=SUB)
        # Characteristics
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(2.75), cw7 - Inches(0.15), Inches(0.22),
                    "Characteristics", font_size=7.5, bold=True, color=MUTED)
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(2.98), cw7 - Inches(0.15), Inches(3.0),
                    col["chars"], font_size=9.0, color=SUB)

    c7x += cw7 + gap7


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — ENVOY Shared Services & Google Cloud Foundation
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "PLATFORM FOUNDATION", "ENVOY Shared Services & Google Cloud Infrastructure", 8)

add_textbox(s, Inches(0.5), Inches(1.15), Inches(5), Inches(0.28),
            "ENVOY Shared Services", font_size=10, bold=True, color=NAVY)

shared_services = ["Memory Store", "Session Store", "Tool Registry", "Agent Registry",
                   "Prompt Registry", "Policy Registry", "Evaluation Framework",
                   "MCP Registry", "A2A Registry", "Audit Framework"]
ssx = Inches(0.5)
for ss in shared_services:
    ssw = Inches(1.22)
    add_rect(s, ssx, Inches(1.45), ssw, Inches(0.42), fill_rgb=DKNAVY)
    add_textbox(s, ssx + Inches(0.05), Inches(1.5), ssw - Inches(0.08), Inches(0.32),
                ss, font_size=8, bold=True, color=WHITE)
    ssx += ssw + Inches(0.03)

add_textbox(s, Inches(0.5), Inches(2.0), Inches(6), Inches(0.28),
            "Google Cloud Platform Foundation", font_size=10, bold=True, color=NAVY)

gcp_cols = [
    (MID,    "CHANNELS",        ["APIs", "Events", "Applications", "PCW Data Feeds", "Webhook Triggers"]),
    (ACCENT, "AGENT PLATFORM",  ["Vertex AI Agent Engine", "ADK (Agent Dev Kit)", "MCP Protocol",
                                  "A2A Protocol", "Agent Registry"]),
    (TEAL,   "AI PLATFORM",     ["Gemini Pro / Flash", "Cortex Control Plane", "Pegasus (LBG Eval)",
                                  "Model Armor", "Vertex AI Studio"]),
    (PURPLE, "KNOWLEDGE",       ["Vertex AI Vector Search", "BigQuery", "Cloud SQL (PostgreSQL)",
                                  "Cloud Storage", "Knowledge Graph"]),
    (GREEN,  "INTEGRATION",     ["Apigee API Gateway", "Cloud Run", "Pub/Sub",
                                  "Cloud Workflows", "Eventarc"]),
    (RGBColor(0x08, 0x91, 0xB2), "EVALUATION", ["Pegasus (LBG)", "Vertex AI Evaluation",
                                                  "ADK Evaluation", "Golden Test Suites",
                                                  "Evaluation Pipelines"]),
    (GOLD,   "OBSERVABILITY",   ["ObserveAll (LBG)", "Dynatrace", "Cloud Monitoring",
                                  "Cloud Logging", "Audit Framework"]),
    (RED,    "SECURITY",        ["IAM & RBAC", "VPC-SC", "Encryption", "DLP",
                                  "Model Armor", "FCA Controls"]),
]
gcx = Inches(0.5)
gcw = Inches(1.55)
gcy = Inches(2.3)
gch = Inches(3.25)
for (gc, gh, gi) in gcp_cols:
    add_rect(s, gcx, gcy, gcw, gch, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, gcx, gcy, gcw, Inches(0.35), fill_rgb=gc)
    add_textbox(s, gcx + Inches(0.05), gcy + Inches(0.05), gcw - Inches(0.08), Inches(0.28),
                gh, font_size=8, bold=True, color=WHITE)
    bullet_list(s, gcx + Inches(0.07), gcy + Inches(0.4), gcw - Inches(0.1), gch - Inches(0.42),
                gi, font_size=8.5, color=SUB, indent="")
    gcx += gcw + Inches(0.04)

# Build vs Reuse
add_textbox(s, Inches(0.5), Inches(5.72), Inches(4), Inches(0.25),
            "Build vs Reuse Principle", font_size=9, bold=True, color=NAVY)
reuse_items = [
    (GREEN,  "REUSE",     "Apigee, Pega, AGGS, Duck Creek, ENVOY shared services, GCP infrastructure"),
    (MID,    "EXTEND",    "ML pipelines, Pegasus evaluation, Vertex AI features for PCW-specific models"),
    (TEAL,   "CONFIGURE", "Gemini prompts, Cortex routing rules, Model Armor policies for PCW domain"),
    (PURPLE, "BUILD",     "PCW-specific ADK agents, intelligence workflows, recommendation logic"),
]
rx8 = Inches(0.5)
for rc8, rl8, rd8 in reuse_items:
    add_rect(s, rx8, Inches(5.97), Inches(3.0), Inches(0.52), fill_rgb=rc8)
    add_textbox(s, rx8 + Inches(0.08), Inches(6.0), Inches(0.7), Inches(0.22),
                rl8, font_size=8, bold=True, color=WHITE)
    add_textbox(s, rx8 + Inches(0.08), Inches(6.21), Inches(2.85), Inches(0.25),
                rd8, font_size=7.5, color=WHITE)
    rx8 += Inches(3.12)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — Target Operating Model
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "OPERATING MODEL",
             "Target Operating Model — ENVOY-Powered Seven-Stage Intelligence Cycle", 9)

steps9 = [
    (ACCENT,  "1 / SENSE",
     "Automated collection of PCW market data. Scheduled and event-triggered. ENVOY ADK Market "
     "Collection Agent. Covers all monitored competitors, channels and product lines. Near real-time "
     "data freshness target <15 minutes.",
     "Agentic + ML Validation", ACCENT),
    (MID,     "2 / ANALYSE",
     "ML models (Vertex AI, Pegasus) detect ranking shifts, pricing anomalies and proposition "
     "changes. Patterns classified by significance, velocity and probable cause. Confidence scores "
     "assigned. Alerts generated for material movements.",
     "ML + GenAI", MID),
    (TEAL,    "3 / SIMULATE",
     "Pricing elasticity and volume simulation models evaluate likely commercial impact of potential "
     "interventions before recommendation. Quantifies expected ranking, quote volume and margin delta. "
     "Scenario comparison produced.",
     "ML Simulation", TEAL),
    (PURPLE,  "4 / RECOMMEND",
     "Gemini synthesises multi-agent analysis into structured, prioritised, explainable "
     "recommendations. Each recommendation includes rationale, supporting evidence, confidence score "
     "and simulated impact. Routed via Cortex.",
     "GenAI + Agentic", PURPLE),
    (GOLD,    "5 / GOVERN",
     "Recommendations routed to pricing and proposition teams via Pega workflow. Full context and "
     "rationale provided. Tiered authority framework applied. Approval, modification or rejection "
     "recorded in ENVOY Audit Framework.",
     "Human + Pega + Cortex", GOLD),
    (GREEN,   "6 / EXECUTE",
     "Approved changes implemented via Apigee-managed APIs to AGGS, Duck Creek and Pricing "
     "Services. Execution confirmed and logged. Post-change impact monitoring initiated automatically "
     "via ObserveAll.",
     "Agentic + Integration", GREEN),
    (RGBColor(0x08, 0x91, 0xB2), "7 / LEARN",
     "ENVOY Learning Agent tracks recommendation outcomes. Pre/post-intervention PCW performance "
     "compared. Model performance evaluated in Pegasus. Retraining triggered on drift detection. "
     "Recommendation quality scores updated.",
     "ML + GenAI", RGBColor(0x08, 0x91, 0xB2)),
]
s9w = Inches(1.8)
s9x = Inches(0.35)
s9y = Inches(1.15)
s9_body_h = Inches(4.3)
s9_hdr_h = Inches(0.42)
gap9 = Inches(0.07)

for i, (hc9, name9, body9, tag9, tc9) in enumerate(steps9):
    add_rect(s, s9x, s9y, s9w, s9_hdr_h, fill_rgb=hc9)
    add_textbox(s, s9x + Inches(0.05), s9y + Inches(0.07), s9w - Inches(0.08), Inches(0.3),
                name9, font_size=8.5, bold=True, color=WHITE)
    add_rect(s, s9x, s9y + s9_hdr_h, s9w, s9_body_h, fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.4)
    add_textbox(s, s9x + Inches(0.08), s9y + s9_hdr_h + Inches(0.1), s9w - Inches(0.12), Inches(3.7),
                body9, font_size=8.5, color=SUB)
    # Tag
    add_rect(s, s9x + Inches(0.08), s9y + s9_hdr_h + Inches(3.85),
             s9w - Inches(0.14), Inches(0.3), fill_rgb=WARM)
    add_textbox(s, s9x + Inches(0.1), s9y + s9_hdr_h + Inches(3.87),
                s9w - Inches(0.15), Inches(0.26),
                tag9, font_size=7.5, bold=True, color=tc9)
    if i < 6:
        add_textbox(s, s9x + s9w + Inches(0.01), s9y + Inches(0.08), Inches(0.06), Inches(0.28),
                    ">", font_size=10, bold=True, color=MUTED)
    s9x += s9w + gap9


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — Capability Architecture (5 Layers)
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "CAPABILITY ARCHITECTURE",
             "Competitive Intelligence Platform — Five-Layer Architecture", 10)

layers = [
    (ACCENT, "Market Intelligence Layer",
     ["PCW ranking capture (all channels)", "Competitor price monitoring (real-time)",
      "Product & excess tracking", "Offer & promotion detection",
      "Frequency: <15 min refresh", "Coverage: all active PCWs",
      "ADK Market Collection Agent", "Pub/Sub event streaming"]),
    (MID, "Insight & Analysis Layer",
     ["ML trend detection (Vertex AI)", "Ranking movement classification",
      "Competitor strategy inference", "Gap & opportunity scoring",
      "Anomaly flagging (price/product)", "Confidence score assignment",
      "Pegasus model evaluation", "BigQuery analytics pipeline"]),
    (TEAL, "Recommendation Layer",
     ["Pricing action recommendations", "Excess adjustment proposals",
      "Offer optimisation suggestions", "Product feature gap alerts",
      "Simulation-backed evidence", "Priority & urgency scoring",
      "Gemini rationale generation", "Cortex recommendation routing"]),
    (PURPLE, "Governance Layer",
     ["Human approval via Pega", "Tiered authorisation controls",
      "ENVOY Audit Framework", "FCA explainability outputs",
      "Model Armor output validation", "Rejection feedback loop",
      "Compliance change records", "RBAC & ABAC access controls"]),
    (GREEN, "Execution Layer",
     ["AGGS rate submissions", "Duck Creek policy updates",
      "Pricing Services API calls", "Product config changes",
      "Execution confirmation log", "Apigee API management",
      "Post-change monitoring", "ObserveAll alerting"]),
]

l10w = Inches(2.45)
l10x = Inches(0.3)
l10y = Inches(1.15)
l10gap = Inches(0.1)
item_h = Inches(0.56)

for lc10, lname, litems in layers:
    # Header
    add_rect(s, l10x, l10y, l10w, Inches(0.45), fill_rgb=lc10)
    add_textbox(s, l10x + Inches(0.08), l10y + Inches(0.08), l10w - Inches(0.12), Inches(0.32),
                lname, font_size=9, bold=True, color=WHITE)
    # Items
    iy10 = l10y + Inches(0.5)
    for item10 in litems:
        add_rect(s, l10x, iy10, l10w, item_h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
        add_rect(s, l10x, iy10, Inches(0.04), item_h, fill_rgb=lc10)
        add_textbox(s, l10x + Inches(0.1), iy10 + Inches(0.1), l10w - Inches(0.15), item_h - Inches(0.12),
                    item10, font_size=9.5, color=TEXT)
        iy10 += item_h + Inches(0.03)
    l10x += l10w + l10gap


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 11 — Multi-Agent Intelligence Architecture
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "AGENTIC ARCHITECTURE",
             "Multi-Agent Intelligence Architecture — ENVOY ADK", 11)

# Orchestrator bar
add_rect(s, Inches(0.35), Inches(1.2), Inches(12.33), Inches(0.68), fill_rgb=NAVY)
add_rect(s, Inches(0.35), Inches(1.2), Inches(0.06), Inches(0.68), fill_rgb=GOLD)
add_textbox(s, Inches(0.5), Inches(1.25), Inches(2.2), Inches(0.25),
            "ORCHESTRATOR AGENT", font_size=8.5, bold=True, color=GOLD)
add_textbox(s, Inches(2.8), Inches(1.25), Inches(9.7), Inches(0.55),
            "Coordinates end-to-end intelligence workflow via ENVOY ADK. Routes tasks between "
            "specialist agents. Manages execution state via Session Store. Handles agent failures "
            "and retries. Aggregates outputs and escalates to human governance via Pega. "
            "Powered by: ENVOY ADK / Vertex AI Agent Engine / LangGraph / Cloud Workflows",
            font_size=9, color=WHITE)

agent_cards = [
    (ACCENT,  "Market Collection Agent",
     "Autonomously collects PCW pricing, product, excess and offer data across all monitored "
     "competitors. Validates data integrity via ML checks. Enriches with metadata and stores in "
     "BigQuery. Handles site structure changes and data anomalies.",
     ["Agentic", "ADK", "Pub/Sub"]),
    (MID,    "Position Intelligence Agent",
     "Analyses ranking movement across PCW channels. Detects velocity, direction and significance "
     "of rank changes. Classifies movements by driver (price, product, offer, algorithm). Generates "
     "ranking trend reports for downstream agents.",
     ["ML", "Vertex AI", "BigQuery ML"]),
    (TEAL,   "Competitor Analysis Agent",
     "Investigates market changes to determine root cause. Cross-references pricing, product and "
     "offer data via RAG. Uses Gemini to generate structured competitive assessments. Identifies "
     "strategic patterns across competitor portfolios.",
     ["GenAI", "Gemini", "RAG"]),
    (PURPLE, "Pricing Intelligence Agent",
     "Evaluates LBG pricing competitiveness at segment and risk-group level. Identifies pricing "
     "gaps and over-competitiveness. Runs elasticity models. Feeds quantified pricing "
     "recommendations to Recommendation Agent.",
     ["ML", "Pegasus", "Vertex AI"]),
    (GOLD,   "Proposition Intelligence Agent",
     "Monitors competitor product features, excess structures, optional covers and add-ons. Uses "
     "Gemini to analyse proposition narrative and identify differentiators. Tracks cover innovation "
     "and PCW feature weighting changes.",
     ["GenAI", "Gemini", "ML"]),
    (RED,    "Simulation Agent",
     "Models commercial outcomes of proposed pricing and proposition interventions. Runs Monte "
     "Carlo and elasticity simulations. Quantifies expected rank, volume and margin impact per "
     "scenario. Produces scenario comparison for Recommendation Agent.",
     ["ML", "Vertex AI", "BigQuery"]),
    (GREEN,  "Recommendation Agent",
     "Synthesises all agent outputs into prioritised recommendations via Gemini structured output. "
     "Assigns confidence, urgency and risk scores. Formats recommendations for Pega governance "
     "workflow. Stores in ENVOY Policy Registry.",
     ["GenAI", "Gemini", "Cortex"]),
    (RGBColor(0x08, 0x91, 0xB2), "Learning Agent",
     "Tracks recommendation acceptance rates and post-intervention PCW performance. Updates Vertex "
     "AI feature stores with outcome data. Identifies systematic errors. Triggers model retraining "
     "via Pegasus when drift detected.",
     ["ML", "Pegasus", "Vertex AI"]),
]

a11w = Inches(3.0)
a11h = Inches(2.35)
a11gap = Inches(0.12)
rows11 = [[0, 1, 2, 3], [4, 5, 6, 7]]
row_ys11 = [Inches(2.0), Inches(4.47)]

for row_idx, (row_cards, ry11) in enumerate(zip(rows11, row_ys11)):
    for col_idx, card_idx in enumerate(row_cards):
        hc11, title11, body11, tags11 = agent_cards[card_idx]
        ax11 = Inches(0.35) + col_idx * (a11w + a11gap)
        card_box(s, ax11, ry11, a11w, a11h, hc11)
        add_textbox(s, ax11 + Inches(0.1), ry11 + Inches(0.12), a11w - Inches(0.15), Inches(0.3),
                    title11, font_size=10.5, bold=True, color=NAVY)
        add_textbox(s, ax11 + Inches(0.1), ry11 + Inches(0.45), a11w - Inches(0.15), Inches(1.55),
                    body11, font_size=8.5, color=SUB)
        tx11 = ax11 + Inches(0.1)
        for tag11 in tags11:
            tw11 = Inches(len(tag11) * 0.075 + 0.2)
            add_rect(s, tx11, ry11 + a11h - Inches(0.32), tw11, Inches(0.22), fill_rgb=WARM)
            add_textbox(s, tx11 + Inches(0.04), ry11 + a11h - Inches(0.3),
                        tw11 - Inches(0.05), Inches(0.2),
                        tag11, font_size=7.5, bold=True, color=hc11)
            tx11 += tw11 + Inches(0.06)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 12 — Integration Architecture
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "SYSTEMS INTEGRATION",
             "Integration with Existing LBG Architecture", 12)

# Left section
add_textbox(s, Inches(0.5), Inches(1.15), Inches(7.0), Inches(0.3),
            "Existing Systems & ENVOY Integration Points", font_size=12, bold=True, color=NAVY)

sys_rows = [
    (MID,    "AGGS",             "Quote aggregation & PCW submission gateway — primary channel interface",        "Existing"),
    (ACCENT, "Apigee",           "API management, security, rate limiting and audit logging for all platform integrations", "Existing"),
    (PURPLE, "Pega",             "Governance workflow, approval routing, SLA management and decision record management", "Existing"),
    (TEAL,   "Duck Creek",       "Policy administration, rating engine and product configuration",               "Existing"),
    (GREEN,  "Pricing Services", "Rate engine, band management and pricing band submission",                     "Existing"),
    (RGBColor(0x08, 0x91, 0xB2), "Data Platform", "Feature store, ML pipelines and BigQuery analytics layer",   "Existing"),
    (GOLD,   "ENVOY Platform",   "Agent runtime, shared services, governance and observability layer",           "New Capability"),
]
sy12 = Inches(1.5)
for sc12, sname, sdesc, stag in sys_rows:
    add_rect(s, Inches(0.5), sy12, Inches(7.2), Inches(0.52), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, Inches(0.5), sy12, Inches(0.05), Inches(0.52), fill_rgb=sc12)
    add_textbox(s, Inches(0.65), sy12 + Inches(0.05), Inches(1.1), Inches(0.22),
                sname, font_size=9, bold=True, color=TEXT)
    add_textbox(s, Inches(1.85), sy12 + Inches(0.05), Inches(5.1), Inches(0.42),
                sdesc, font_size=8.5, color=SUB)
    tag_w = Inches(1.1) if stag == "New Capability" else Inches(0.7)
    tag_c = GOLD if stag == "New Capability" else TEAL
    add_rect(s, Inches(6.55), sy12 + Inches(0.12), tag_w, Inches(0.22), fill_rgb=tag_c)
    add_textbox(s, Inches(6.57), sy12 + Inches(0.13), tag_w - Inches(0.04), Inches(0.2),
                stag, font_size=7, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    sy12 += Inches(0.57)

# Principle box
add_rect(s, Inches(0.5), sy12 + Inches(0.08), Inches(7.2), Inches(0.75), fill_rgb=NAVY)
add_rect(s, Inches(0.5), sy12 + Inches(0.08), Inches(0.06), Inches(0.75), fill_rgb=GOLD)
add_textbox(s, Inches(0.65), sy12 + Inches(0.12), Inches(6.95), Inches(0.65),
            "Architecture Principle: The PCW CI Platform is a governed capability layer on top of "
            "LBG's existing technology estate. All data flows through Apigee. All decisions flow "
            "through Pega. All AI calls governed by Cortex and Model Armor. No duplication of core systems.",
            font_size=8.5, color=WHITE)

# Right section
rx12 = Inches(7.9)
add_textbox(s, rx12, Inches(1.15), Inches(4.7), Inches(0.3),
            "End-to-End Data & Decision Flow", font_size=12, bold=True, color=NAVY)

flow_nodes = [
    (ACCENT,  "PCWs — Real-Time Market Data Source"),
    (MID,     "ENVOY ADK — Market Collection & Intelligence Agents"),
    (TEAL,    "LBG Data Platform — BigQuery Feature Store & ML Registry"),
    (SUB,     "Apigee — API Management, Security & Audit"),
    (GREEN,   "AGGS / Duck Creek / Pricing Services — Execution Systems"),
    (PURPLE,  "Pega — Governance Workflow & Human Approval"),
    (NAVY,    "Business Users — Review, Approve & Monitor"),
]
fy12 = Inches(1.5)
for i12, (fnc, fnt) in enumerate(flow_nodes):
    add_rect(s, rx12, fy12, Inches(4.7), Inches(0.44), fill_rgb=fnc)
    add_textbox(s, rx12 + Inches(0.1), fy12 + Inches(0.08), Inches(4.5), Inches(0.3),
                fnt, font_size=8.5, bold=(fnc == NAVY), color=WHITE)
    if i12 < len(flow_nodes) - 1:
        add_textbox(s, rx12 + Inches(2.2), fy12 + Inches(0.44), Inches(0.4), Inches(0.2),
                    "v", font_size=9, bold=True, color=MUTED, align=PP_ALIGN.CENTER)
    fy12 += Inches(0.65)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 13 — Human-in-the-Loop Governance
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "GOVERNANCE MODEL",
             "Human-in-the-Loop Decision Model — ENVOY HITL Framework", 13)

tiers = [
    (GREEN,  "AUTO",            "Market Monitoring & Data Collection",
     "Fully automated. ENVOY ADK agents continuously collect, validate and process PCW data. ML "
     "anomaly detection flags material movements. Exceptions escalated via Cloud Workflows. No "
     "human intervention in steady state.",
     "ENVOY ADK\nPub/Sub\nCloud Workflows", "Automated", GREEN),
    (MID,    "ANALYSE",         "Intelligence Generation & Analysis",
     "AI-driven. ML models (Vertex AI, Pegasus) and Gemini analyse data, detect patterns and "
     "generate contextual intelligence. Output quality validated via ENVOY Evaluation Framework "
     "before escalation to recommendation stage.",
     "Vertex AI\nGemini\nPegasus Eval", "AI-Driven", MID),
    (GOLD,   "RECOMMEND",       "Recommendation Review & Human Judgement",
     "Human review required. Pricing and proposition teams receive Gemini-generated recommendations "
     "with full evidence, rationale, simulated impact and confidence scores. Teams approve, modify "
     "or reject. All decisions logged in ENVOY Audit Framework. Target SLA: same-day for urgent signals.",
     "Gemini\nCortex Routing\nPega Workflow", "Human Required", GOLD),
    (PURPLE, "APPROVE",         "Governance Approval & Senior Sign-Off",
     "Senior approval required for material pricing changes. Delegated authority framework applied "
     "in Pega. Compliance team notified for significant movements. Full decision record created in "
     "ENVOY Audit Framework for FCA review.",
     "Pega\nAudit Framework\nModel Armor", "Governed", PURPLE),
    (RED,    "EXECUTE & LEARN", "Execution, Monitoring & Closed-Loop Learning",
     "Approved changes executed via Apigee to AGGS, Duck Creek and Pricing Services. Execution "
     "confirmed and logged. ObserveAll monitors post-change PCW performance. ENVOY Learning Agent "
     "ingests outcomes, updates Pegasus and triggers retraining where required.",
     "Apigee / AGGS\nObserveAll\nPegasus", "Closed-Loop", RED),
]

t13y = Inches(1.2)
t13h = Inches(1.0)
t13gap = Inches(0.08)
for (bc13, badge13, title13, desc13, envoy13, auto13, ac13) in tiers:
    add_rect(s, Inches(0.5), t13y, Inches(12.33), t13h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    # Tier number / badge
    add_rect(s, Inches(0.5), t13y, Inches(1.0), t13h, fill_rgb=bc13)
    add_textbox(s, Inches(0.5), t13y + Inches(0.35), Inches(1.0), Inches(0.3),
                badge13, font_size=8, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    # Title + desc
    add_textbox(s, Inches(1.6), t13y + Inches(0.06), Inches(7.5), Inches(0.28),
                title13, font_size=10, bold=True, color=NAVY)
    add_textbox(s, Inches(1.6), t13y + Inches(0.34), Inches(7.5), Inches(0.6),
                desc13, font_size=8.5, color=SUB)
    # ENVOY component
    add_textbox(s, Inches(9.2), t13y + Inches(0.08), Inches(2.0), Inches(0.85),
                envoy13, font_size=8.5, color=ACCENT)
    # Auto label
    add_rect(s, Inches(11.3), t13y + Inches(0.3), Inches(1.3), Inches(0.3), fill_rgb=ac13)
    add_textbox(s, Inches(11.3), t13y + Inches(0.32), Inches(1.3), Inches(0.26),
                auto13, font_size=8, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    t13y += t13h + t13gap

# Principle bar
add_rect(s, Inches(0.5), Inches(6.3), Inches(12.33), Inches(0.55), fill_rgb=NAVY)
add_textbox(s, Inches(0.7), Inches(6.38), Inches(12.0), Inches(0.4),
            "The platform RECOMMENDS via Gemini.   People DECIDE via Pega.   "
            "Systems EXECUTE via Apigee.   ENVOY LEARNS continuously.",
            font_size=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 14 — Governance & Risk Framework
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "RISK & COMPLIANCE", "Governance & Risk Framework — FCA Aligned", 14)

risk_cards = [
    (MID,    "FCA Alignment & Consumer Duty",
     "Consumer Duty obligations met through explainable AI outputs and maintained human decision "
     "accountability. All pricing decisions remain with FCA-authorised individuals — AI provides "
     "decision support, not autonomous pricing. Recommendations include fair value assessment "
     "context. Regular review against FCA GI pricing rules. Cortex routing ensures no ungoverned model calls."),
    (GREEN,  "Auditability & Decision Lineage",
     "Complete audit trail from PCW data collection through to executed change maintained in ENVOY "
     "Audit Framework. Every recommendation, approval, modification and rejection recorded with "
     "timestamp, user identity, rationale and ENVOY session ID. Audit logs stored in Cloud Logging "
     "with defined retention. Accessible for regulatory review within agreed SLAs. Immutable audit "
     "records via Cloud Storage."),
    (GOLD,   "Explainability & Transparency",
     "All Gemini recommendations include human-readable rationale and source data references. ML "
     "model outputs include SHAP feature importance and confidence intervals via Pegasus. Model "
     "cards maintained for all production models. Pricing teams able to interrogate and challenge "
     "any recommendation before approval. No black-box decisions."),
    (ACCENT, "Data Protection & Privacy",
     "No customer PII used in competitive intelligence workflows. Competitor market data treated "
     "as commercially sensitive. DLP policies enforced via Model Armor and GCP DLP. Role-based "
     "access controls managed via IAM & RBAC. UK data residency maintained (VPC-SC). GDPR-aligned "
     "retention policies applied. Data minimisation principles throughout."),
    (PURPLE, "Model Governance (Pegasus)",
     "All ML and GenAI models subject to LBG model governance policy enforced via Pegasus. Pre-"
     "deployment validation, champion/challenger testing and post-deployment monitoring mandatory. "
     "Model performance reviewed quarterly. Retraining triggered automatically on drift detection. "
     "Model cards and lineage tracked in Vertex AI Model Registry. External model risk review for material models."),
    (RED,    "Operational Resilience & Recovery",
     "Platform designed for graceful degradation — core pricing operations continue if CI platform "
     "is unavailable. Recovery time and recovery point objectives defined per component. Manual "
     "fallback procedures documented and tested quarterly. Dependency risk assessed for all "
     "third-party PCW data sources. Pega workflows continue to function independently of AI layer. "
     "Chaos engineering tests conducted pre-production."),
]

r14x = Inches(0.5)
r14y = Inches(1.2)
r14w = Inches(4.1)
r14h = Inches(2.5)
r14gap = Inches(0.15)

for i14, (rc14, rt14, rb14) in enumerate(risk_cards):
    col14 = i14 % 3
    row14 = i14 // 3
    rx14 = r14x + col14 * (r14w + r14gap)
    ry14 = r14y + row14 * (r14h + r14gap)
    add_rect(s, rx14, ry14, r14w, r14h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, rx14, ry14, r14w, Inches(0.05), fill_rgb=rc14)
    add_textbox(s, rx14 + Inches(0.1), ry14 + Inches(0.1), r14w - Inches(0.15), Inches(0.3),
                rt14, font_size=10, bold=True, color=NAVY)
    add_textbox(s, rx14 + Inches(0.1), ry14 + Inches(0.44), r14w - Inches(0.15), r14h - Inches(0.5),
                rb14, font_size=8.5, color=SUB)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 15 — KPI & Measurement Framework
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "MEASUREMENT FRAMEWORK",
             "KPI & Measurement Framework — Commercial, Operational, Strategic & Risk", 15)

kpi_cols = [
    (ACCENT, "Commercial KPIs",
     ["PCW ranking position (by channel, brand, product line)",
      "Quote conversion rate — PCW-sourced new business",
      "New business volume via PCW channel",
      "Revenue per PCW quote (risk-adjusted)",
      "Competitive win rate vs key competitors",
      "Market share by PCW (where measurable)"]),
    (MID, "Operational KPIs",
     ["Market data freshness — target <15 minutes",
      "Signal to insight latency — target <30 minutes",
      "Insight to recommendation — target <2 hours",
      "Recommendation to decision — target same day",
      "FTE hours saved on monitoring & analysis",
      "ENVOY agent uptime & SLA compliance (%)"]),
    (TEAL, "Strategic KPIs",
     ["PCW channel coverage breadth (% of market)",
      "Recommendation adoption rate (%)",
      "Recommendation accuracy (post-outcome validation)",
      "Intelligence latency vs competitor benchmark",
      "Platform reuse across GI product lines",
      "Pegasus model quality scores (trend)"]),
    (RED, "Risk & Model KPIs",
     ["Audit compliance rate (100% target)",
      "Pegasus model performance vs baseline",
      "Data quality score — BigQuery pipeline",
      "Governance SLA compliance — Pega (%)",
      "Model drift incidents — target zero",
      "FCA review findings — target zero"]),
]

k15x = Inches(0.5)
k15w = Inches(3.0)
k15gap = Inches(0.44)
item15_h = Inches(0.56)

for kc15, kn15, ki15 in kpi_cols:
    add_rect(s, k15x, Inches(1.15), k15w, Inches(0.42), fill_rgb=kc15)
    add_textbox(s, k15x + Inches(0.08), Inches(1.2), k15w - Inches(0.1), Inches(0.32),
                kn15, font_size=10, bold=True, color=WHITE)
    iy15 = Inches(1.62)
    for item15 in ki15:
        add_rect(s, k15x, iy15, k15w, item15_h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
        add_rect(s, k15x, iy15, Inches(0.05), item15_h, fill_rgb=kc15)
        add_textbox(s, k15x + Inches(0.1), iy15 + Inches(0.08), k15w - Inches(0.15), item15_h - Inches(0.1),
                    item15, font_size=9.0, color=TEXT)
        iy15 += item15_h + Inches(0.04)
    k15x += k15w + k15gap


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 16 — Phased Delivery Roadmap
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "DELIVERY ROADMAP",
             "Phased Delivery Roadmap — Four Waves to Full Optimisation", 16)

waves = [
    (ACCENT, "Wave 1", "Market Visibility", "Months 1-3",
     ["PCW data collection pipeline (ADK)", "Competitor baseline dataset (BigQuery)",
      "Ranking capture — 2 pilot PCWs", "ENVOY platform onboarding",
      "Data quality framework (Pegasus)", "Executive monitoring dashboard",
      "ML anomaly detection (Vertex AI)", "Apigee integration setup"]),
    (MID, "Wave 2", "Intelligence", "Months 4-6",
     ["ML trend detection models (Vertex AI)", "Competitor profiling (Gemini + RAG)",
      "GenAI intelligence summaries", "Opportunity identification engine",
      "Full PCW channel coverage", "Pegasus model evaluation live",
      "ENVOY agent observability (ObserveAll)", "Stakeholder feedback & iteration"]),
    (TEAL, "Wave 3", "Decision Support", "Months 7-9",
     ["Gemini recommendation engine", "Pega governance workflow integration",
      "Tiered approval framework", "Pricing simulation (ML, Vertex AI)",
      "AGGS & Duck Creek integration (Apigee)", "Cortex recommendation routing",
      "Model Armor guardrails active", "Audit Framework compliance checks"]),
    (PURPLE, "Wave 4", "Optimisation", "Months 10-12",
     ["ENVOY Learning Agent (closed-loop)", "Continuous optimisation models",
      "Full proposition simulation", "Multi-agent orchestration (A2A)",
      "Platform extensibility — other GI lines", "Pegasus retraining automation",
      "Performance benchmarking vs baseline", "Scale & operate model finalised"]),
]

w16x = Inches(0.5)
w16w = Inches(3.0)
w16gap = Inches(0.44)
item16_h = Inches(0.52)

for wc16, wn16, wt16, wd16, wi16 in waves:
    add_rect(s, w16x, Inches(1.15), w16w, Inches(0.62), fill_rgb=wc16)
    add_textbox(s, w16x + Inches(0.08), Inches(1.18), w16w - Inches(0.1), Inches(0.28),
                wn16 + " — " + wt16, font_size=10, bold=True, color=WHITE)
    add_textbox(s, w16x + Inches(0.08), Inches(1.45), w16w - Inches(0.1), Inches(0.22),
                wd16, font_size=8.5, italic=True, color=WHITE)
    iy16 = Inches(1.82)
    for item16 in wi16:
        add_rect(s, w16x, iy16, w16w, item16_h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
        add_rect(s, w16x, iy16, Inches(0.05), item16_h, fill_rgb=wc16)
        add_textbox(s, w16x + Inches(0.1), iy16 + Inches(0.09), w16w - Inches(0.15), item16_h - Inches(0.1),
                    item16, font_size=9.0, color=TEXT)
        iy16 += item16_h + Inches(0.04)
    w16x += w16w + w16gap

# Timeline bar
tl_x = Inches(0.5)
for wc16b, _, _, wd16b, _ in waves:
    add_rect(s, tl_x, Inches(6.72), Inches(3.0), Inches(0.35), fill_rgb=wc16b)
    add_textbox(s, tl_x + Inches(0.08), Inches(6.76), Inches(2.85), Inches(0.25),
                wd16b, font_size=8.5, bold=True, color=WHITE)
    tl_x += Inches(3.44)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 17 — Business Value Summary
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "BUSINESS CASE",
             "Business Value Summary — Four Dimensions of Value", 17)

value_cards = [
    (ACCENT, "Faster Market Response",
     "Reduce competitor response time from days to hours. ENVOY ADK agents provide continuous "
     "market sensing with <15 minute data freshness. Event-triggered analysis via Pub/Sub ensures "
     "material market movements are surfaced immediately. ML anomaly detection identifies significant "
     "changes without manual review. Intelligence latency reduced from days to <2 hours end-to-end."),
    (TEAL, "Better Commercial Outcomes",
     "Gemini-powered recommendations improve PCW ranking position and conversion performance. ML "
     "simulation quantifies intervention impact before execution — reducing risk of commercial "
     "missteps. Closed-loop Learning Agent ensures recommendation quality compounds over time. "
     "Evidence-based decisions replace analyst judgement under uncertainty. Better rank position "
     "directly drives new business volume growth."),
    (GOLD, "Operational Efficiency",
     "ENVOY agents automate end-to-end data collection, validation, analysis and recommendation "
     "drafting — significantly reducing FTE effort on low-value monitoring tasks. Pricing and "
     "proposition teams redirected to higher-value approval and strategic judgement work. Pega "
     "workflow eliminates manual coordination overhead. ObserveAll provides proactive alerting, "
     "reducing reactive investigation effort."),
    (PURPLE, "Reusable ENVOY Platform Capability",
     "PCW CI Platform is built on ENVOY's enterprise-grade agentic infrastructure — reusable "
     "across LBG General Insurance and broader BCB use cases. ML model patterns, Gemini prompts, "
     "ADK agent designs and Pega governance workflows are all extensible. Each new use case "
     "benefits from accumulated ENVOY platform investment. Lower cost-to-serve for subsequent AI "
     "deployments across the organisation."),
]

v17w = Inches(6.1)
v17h = Inches(2.6)

for i17, (vc17, vt17, vb17) in enumerate(value_cards):
    col17 = i17 % 2
    row17 = i17 // 2
    vx17 = Inches(0.5) + col17 * (v17w + Inches(0.2))
    vy17 = Inches(1.2) + row17 * (v17h + Inches(0.15))
    add_rect(s, vx17, vy17, v17w, v17h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, vx17, vy17, v17w, Inches(0.05), fill_rgb=vc17)
    add_textbox(s, vx17 + Inches(0.12), vy17 + Inches(0.1), v17w - Inches(0.2), Inches(0.3),
                vt17, font_size=11, bold=True, color=NAVY)
    add_textbox(s, vx17 + Inches(0.12), vy17 + Inches(0.44), v17w - Inches(0.2), v17h - Inches(0.5),
                vb17, font_size=9.5, color=SUB)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 18 — Risk Register & Assumptions
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "RISK MANAGEMENT",
             "Key Risks, Assumptions & Mitigations", 18)

add_textbox(s, Inches(0.5), Inches(1.15), Inches(4), Inches(0.28),
            "Risk Register", font_size=12, bold=True, color=NAVY)

risk_rows = [
    (RED,   "PCW data quality and availability below required threshold",
     "Medium", "High",
     "ML data validation layer in BigQuery. Data quality scoring in Pegasus. Manual fallback "
     "process documented. Vendor SLA assessment for data sources."),
    (RED,   "ML/GenAI model accuracy below acceptance threshold",
     "Medium", "High",
     "Pegasus champion/challenger framework. Phased rollout with human validation gates. Clear "
     "accuracy KPIs defined before production deployment."),
    (GOLD,  "Pricing team adoption and change management",
     "Medium", "Medium",
     "Co-design from Wave 1. Explainable AI outputs build trust. Pega workflow familiar to users. "
     "Phased capability introduction reduces change burden."),
    (GOLD,  "FCA scrutiny of AI-assisted pricing recommendation inputs",
     "Low", "High",
     "Human decision accountability maintained. Full explainability via Pegasus and Gemini. Legal "
     "& Compliance review at each wave gate. FCA engagement planned."),
    (GREEN, "ENVOY platform integration and onboarding complexity",
     "Low", "Medium",
     "ENVOY onboarding model agreed. Reuse of existing ADK patterns. Integration spikes in Wave 1. "
     "Platform team support embedded in delivery."),
]

r18y = Inches(1.5)
for rc18, rdesc18, rlik18, rimp18, rmit18 in risk_rows:
    rh18 = Inches(0.82)
    add_rect(s, Inches(0.5), r18y, Inches(7.6), rh18, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, Inches(0.5), r18y, Inches(0.05), rh18, fill_rgb=rc18)
    add_textbox(s, Inches(0.65), r18y + Inches(0.06), Inches(3.8), Inches(0.28),
                rdesc18, font_size=8.5, bold=True, color=TEXT)
    add_textbox(s, Inches(0.65), r18y + Inches(0.35), Inches(1.1), Inches(0.22),
                "Likelihood: " + rlik18, font_size=7.5, color=SUB)
    add_textbox(s, Inches(1.9), r18y + Inches(0.35), Inches(0.9), Inches(0.22),
                "Impact: " + rimp18, font_size=7.5, color=SUB)
    add_textbox(s, Inches(3.3), r18y + Inches(0.35), Inches(4.7), Inches(0.42),
                rmit18, font_size=8.0, color=SUB)
    r18y += rh18 + Inches(0.06)

# Key Assumptions
add_textbox(s, Inches(8.3), Inches(1.15), Inches(4.0), Inches(0.28),
            "Key Assumptions", font_size=12, bold=True, color=NAVY)

assumptions = [
    "Google Cloud and ENVOY platform approved as strategic infrastructure for this use case",
    "Cortex is the strategic AI control plane — all model routing governed through Cortex",
    "HITL (Human-in-the-Loop) retained for all recommendation approval — no fully autonomous pricing changes",
    "PCW data is available at sufficient frequency and quality to support near-real-time monitoring",
    "Pricing and proposition teams have capacity to engage in co-design and adopt AI-assisted workflows",
]
ay18 = Inches(1.5)
for asm in assumptions:
    add_rect(s, Inches(8.3), ay18, Inches(4.4), Inches(0.72), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, Inches(8.3), ay18, Inches(0.05), Inches(0.72), fill_rgb=MID)
    add_textbox(s, Inches(8.42), ay18 + Inches(0.07), Inches(4.2), Inches(0.62),
                asm, font_size=8.5, color=TEXT)
    ay18 += Inches(0.78)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 19 — Recommendation & Next Steps (Dark cover style)
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)

add_rect(s, Inches(0), Inches(0), W, H, fill_rgb=NAVY)
add_rect(s, Inches(0), Inches(0), W, Inches(0.08), fill_rgb=GOLD)
add_rect(s, Inches(0), Inches(0), Inches(0.08), H, fill_rgb=GOLD)

add_textbox(s, Inches(0.5), Inches(0.42), Inches(12.0), Inches(0.28),
            "RECOMMENDATION & DECISION REQUIRED",
            font_size=8, bold=True, color=GOLD)

# Large recommendation box
add_rect(s, Inches(0.5), Inches(0.82), Inches(12.33), Inches(1.15), fill_rgb=DKNAVY)
add_rect(s, Inches(0.5), Inches(0.82), Inches(0.06), Inches(1.15), fill_rgb=GOLD)
add_textbox(s, Inches(0.65), Inches(0.88), Inches(12.0), Inches(1.0),
            "Proceed with a focused MVP targeting a single PCW channel and a defined set of "
            "pricing and proposition use cases — building on LBG's ENVOY Agentic Platform, "
            "Google Cloud infrastructure and existing system investments. The MVP validates the "
            "end-to-end workflow from PCW data collection through ENVOY ADK agent orchestration "
            "to Pega-governed recommendation delivery, establishing confidence in capability and "
            "commercial impact before scaling.",
            font_size=11.5, color=WHITE)

add_textbox(s, Inches(0.5), Inches(2.15), Inches(5), Inches(0.25),
            "IMMEDIATE NEXT STEPS", font_size=8, bold=True, color=MUTED)

next_steps = [
    "Confirm executive sponsorship, investment approval and ENVOY platform onboarding agreement",
    "Establish cross-functional delivery team spanning Pricing, Product, Technology, Risk and Compliance",
    "Select pilot PCW channel and define MVP scope with pricing team co-design",
    "Conduct PCW data availability assessment and ENVOY ADK integration spike",
    "Define success criteria, baseline KPIs and Pegasus model evaluation framework",
    "Commence Wave 1 delivery: ENVOY platform setup, data pipelines and monitoring dashboard",
]
ns_positions = [
    (Inches(0.5),  Inches(2.48)),
    (Inches(6.5),  Inches(2.48)),
    (Inches(0.5),  Inches(3.1)),
    (Inches(6.5),  Inches(3.1)),
    (Inches(0.5),  Inches(3.72)),
    (Inches(6.5),  Inches(3.72)),
]
for i19, (ns, (nsx, nsy)) in enumerate(zip(next_steps, ns_positions)):
    add_rect(s, nsx, nsy, Inches(0.38), Inches(0.38), fill_rgb=GOLD)
    add_textbox(s, nsx + Inches(0.04), nsy + Inches(0.05), Inches(0.3), Inches(0.28),
                str(i19 + 1), font_size=11, bold=True, color=NAVY, align=PP_ALIGN.CENTER)
    add_textbox(s, nsx + Inches(0.46), nsy + Inches(0.04), Inches(5.8), Inches(0.55),
                ns, font_size=9.5, color=WHITE)

add_textbox(s, Inches(0.5), Inches(4.7), Inches(6), Inches(0.25),
            "ENVOY PLATFORM COMMITMENTS", font_size=8, bold=True, color=GOLD)

commitments = [
    (ACCENT,  "Governance: 100% of AI recommendations governed via Cortex, Model Armor and Pega before execution"),
    (TEAL,    "Observability: Full agent traceability via ObserveAll and Dynatrace from Day 1 of production"),
    (PURPLE,  "Reusability: All ENVOY agent patterns, prompts and ML models registered in shared services for BCB reuse"),
]
cx19 = Inches(0.5)
for cc19, ct19 in commitments:
    add_rect(s, cx19, Inches(5.0), Inches(4.0), Inches(0.82), fill_rgb=DKNAVY)
    add_rect(s, cx19, Inches(5.0), Inches(4.0), Inches(0.05), fill_rgb=cc19)
    add_textbox(s, cx19 + Inches(0.1), Inches(5.1), Inches(3.8), Inches(0.65),
                ct19, font_size=9, color=WHITE)
    cx19 += Inches(4.12)

add_textbox(s, Inches(0.5), Inches(6.0), Inches(12.33), Inches(0.42),
            "Transforming competitor monitoring into continuous competitive intelligence — "
            "powered by ENVOY, Gemini, Vertex AI and ML, governed by human oversight.",
            font_size=9.5, italic=True, color=MUTED, align=PP_ALIGN.CENTER)

add_textbox(s, W - Inches(1.1), H - Inches(0.35), Inches(1.0), Inches(0.25),
            "19 / 20", font_size=8, color=MUTED, align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 20 — Appendix: ENVOY Technical Reference
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "APPENDIX",
             "ENVOY Technical Reference — Platform Components & PCW CI Mapping", 20)

# Section A — ENVOY Component Mapping
add_textbox(s, Inches(0.5), Inches(1.15), Inches(4.0), Inches(0.28),
            "ENVOY Component Mapping", font_size=11, bold=True, color=NAVY)

comp_rows = [
    ("Vertex AI Agent Engine", "ADK agent hosting & execution"),
    ("ADK (Agent Dev Kit)",    "PCW collection, analysis, recommendation agents"),
    ("LangGraph",              "Multi-step agent workflow orchestration"),
    ("Gemini Pro",             "Competitor analysis & recommendation generation"),
    ("Cortex",                 "Model routing & guardrail enforcement"),
    ("Pegasus (LBG)",          "ML model evaluation & quality monitoring"),
    ("Model Armor",            "Prompt protection & output validation"),
    ("Vector Search",          "RAG for competitor knowledge base"),
    ("BigQuery",               "Market data storage & ML feature engineering"),
    ("Pub/Sub",                "Event-driven agent triggering"),
    ("Cloud Workflows",        "Long-running process orchestration"),
    ("Apigee",                 "API gateway for AGGS, Duck Creek, Pricing"),
    ("Pega",                   "Human approval workflow & governance"),
    ("ObserveAll",             "Agent observability & business KPI monitoring"),
    ("ENVOY Audit Framework",  "Full decision lineage & FCA audit trail"),
]
cy20 = Inches(1.48)
for comp, usage in comp_rows:
    add_rect(s, Inches(0.5), cy20, Inches(4.1), Inches(0.34), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.25)
    add_textbox(s, Inches(0.55), cy20 + Inches(0.05), Inches(1.7), Inches(0.26),
                comp, font_size=7.5, bold=True, color=TEXT)
    add_textbox(s, Inches(2.3), cy20 + Inches(0.05), Inches(2.25), Inches(0.26),
                usage, font_size=7.5, color=SUB)
    cy20 += Inches(0.36)

# Section B — ENVOY Shared Services Used
add_textbox(s, Inches(4.5), Inches(1.15), Inches(4.1), Inches(0.28),
            "ENVOY Shared Services Used", font_size=11, bold=True, color=NAVY)

shared_rows = [
    ("Memory Store",        "Agent context persistence across PCW sessions"),
    ("Session Store",       "Multi-agent workflow state management"),
    ("Tool Registry",       "PCW data collection and API tools registration"),
    ("Agent Registry",      "PCW CI agent catalogue and version management"),
    ("Prompt Registry",     "Gemini prompt versioning for PCW analysis"),
    ("Policy Registry",     "Recommendation governance rules storage"),
    ("Evaluation Framework","Automated quality gates for recommendations"),
    ("MCP Registry",        "PCW data source MCP server catalogue"),
    ("A2A Registry",        "Inter-agent communication protocol registry"),
    ("Audit Framework",     "Immutable recommendation and decision log"),
]
sy20 = Inches(1.48)
for sname20, susage20 in shared_rows:
    add_rect(s, Inches(4.5), sy20, Inches(4.1), Inches(0.34), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.25)
    add_textbox(s, Inches(4.55), sy20 + Inches(0.05), Inches(1.6), Inches(0.26),
                sname20, font_size=7.5, bold=True, color=TEXT)
    add_textbox(s, Inches(6.2), sy20 + Inches(0.05), Inches(2.35), Inches(0.26),
                susage20, font_size=7.5, color=SUB)
    sy20 += Inches(0.36)

# Section C — AI Capability Classification
add_textbox(s, Inches(9.0), Inches(1.15), Inches(3.9), Inches(0.28),
            "AI Capability Classification", font_size=11, bold=True, color=NAVY)

ai_class = [
    (ACCENT,  "Machine Learning (Vertex AI / Pegasus)",
     "Ranking prediction, anomaly detection, elasticity modelling, embedding generation, drift monitoring"),
    (TEAL,    "Generative AI (Gemini)",
     "Competitor analysis synthesis, recommendation rationale, briefing generation, explanation outputs"),
    (PURPLE,  "Agentic (ENVOY ADK)",
     "Autonomous PCW collection, multi-agent orchestration, event-driven investigation, simulation workflows"),
    (NAVY,    "Platform Services",
     "LangGraph, Pub/Sub, Cloud Workflows, Eventarc, BigQuery, Apigee, Pega, ObserveAll"),
]
acy = Inches(1.48)
for acc, atn, atd in ai_class:
    add_rect(s, Inches(9.0), acy, Inches(3.9), Inches(0.85), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.25)
    add_rect(s, Inches(9.0), acy, Inches(3.9), Inches(0.05), fill_rgb=acc)
    add_textbox(s, Inches(9.08), acy + Inches(0.08), Inches(3.75), Inches(0.24),
                atn, font_size=8.5, bold=True, color=NAVY)
    add_textbox(s, Inches(9.08), acy + Inches(0.32), Inches(3.75), Inches(0.5),
                atd, font_size=8.0, color=SUB)
    acy += Inches(0.92)

# Key Design Principles
add_textbox(s, Inches(9.0), acy + Inches(0.1), Inches(3.9), Inches(0.28),
            "Key Design Principles", font_size=11, bold=True, color=NAVY)
principles = [
    "- Human oversight maintained at all recommendation and execution decision points",
    "- All AI calls governed and routed through Cortex — no ungoverned model access",
    "- Full observability from data ingestion to executed change via ObserveAll and Audit Framework",
    "- Platform designed for extensibility — reusable across LBG BCB General Insurance use cases",
]
bullet_list(s, Inches(9.0), acy + Inches(0.42), Inches(3.9), Inches(1.5),
            principles, font_size=9.5, color=SUB, indent="")


# ── Save ──────────────────────────────────────────────────────────────────────
prs.save("/home/user/rag/LBG_PCW_CI_Platform_v3.pptx")
print("Saved successfully")
