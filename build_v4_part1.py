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
            "LLOYDS BANKING GROUP  |  GENERAL INSURANCE  |  COMPETITIVE INTELLIGENCE PROGRAMME",
            font_size=8, bold=True, color=GOLD)

add_textbox(s, Inches(0.5), Inches(1.1), Inches(8.3), Inches(0.55),
            "PCW Competitive Intelligence", font_size=32, bold=True, color=WHITE)
add_textbox(s, Inches(0.5), Inches(1.62), Inches(8.3), Inches(0.55),
            "& Optimisation Platform", font_size=32, bold=True, color=WHITE)

# Gold rule
add_rect(s, Inches(0.5), Inches(2.28), Inches(0.6), Inches(0.04), fill_rgb=GOLD)

add_textbox(s, Inches(0.5), Inches(2.4), Inches(8.3), Inches(0.35),
            "Transforming Market Monitoring into Continuous Competitive Advantage Across All Price Comparison Website Channels",
            font_size=12, italic=True, color=MUTED)

# Tech label
add_textbox(s, Inches(0.5), Inches(2.88), Inches(8.3), Inches(0.3),
            "Machine Learning  |  Gemini / Generative AI  |  ENVOY Agentic Platform  |  Google Cloud",
            font_size=9.5, color=MUTED)

# Executive message box
add_rect(s, Inches(0.5), Inches(3.3), Inches(8.3), Inches(1.85), fill_rgb=DKNAVY)
add_rect(s, Inches(0.5), Inches(3.3), Inches(0.06), Inches(1.85), fill_rgb=GOLD)
add_textbox(s, Inches(0.65), Inches(3.38), Inches(8.0), Inches(1.7),
            "This platform harnesses the full spectrum of AI capability available within LBG's ENVOY Agentic Platform — combining traditional ML-driven pricing and ranking models running on Vertex AI, Gemini-powered competitive analysis and intelligence synthesis, and multi-agent Agentic automation orchestrated via the Agent Developer Kit (ADK) and Vertex AI Agent Engine — to deliver continuous, governed, explainable competitive intelligence and optimisation recommendations across all Price Comparison Website channels, with every AI output reviewed by authorised decision-makers before execution and every decision recorded in the ENVOY Audit Framework.",
            font_size=9, color=WHITE)

# ── Right panel content ──
rx = Inches(9.2)
add_textbox(s, rx, Inches(0.18), Inches(3.8), Inches(0.28),
            "POWERED BY ENVOY", font_size=8, bold=True, color=GOLD)
add_textbox(s, rx, Inches(0.45), Inches(3.8), Inches(0.35),
            "Enterprise Agent Runtime & Governance Platform — Google Cloud Native, FCA Aligned, Multi-Agent, Secure by Design",
            font_size=9, italic=True, color=WHITE)

metrics = [
    ("30–50%", "Faster intelligence delivery vs current manual process — hours not days"),
    ("80%",    "Reusable ENVOY agent components across BCB use cases — build once, deploy many"),
    ("100%",   "Agent calls governed via Cortex control plane — no ungoverned model access"),
    ("1 Platform", "Shared infrastructure across BCB General Insurance — no duplication"),
    ("Full",   "Observability and traceability via ObserveAll and Dynatrace — every agent action visible"),
]
my = Inches(0.88)
for val, desc in metrics:
    add_rect(s, rx, my, Inches(3.9), Inches(0.48), fill_rgb=DKNAVY)
    add_rect(s, rx, my, Inches(0.06), Inches(0.48), fill_rgb=GOLD)
    add_textbox(s, rx + Inches(0.12), my + Inches(0.03), Inches(3.7), Inches(0.18),
                val, font_size=10, bold=True, color=GOLD)
    add_textbox(s, rx + Inches(0.12), my + Inches(0.21), Inches(3.7), Inches(0.24),
                desc, font_size=7.5, color=WHITE)
    my += Inches(0.52)

add_textbox(s, rx, my + Inches(0.05), Inches(3.8), Inches(0.22),
            "DELIVERY PHASES", font_size=8, bold=True, color=GOLD)
my += Inches(0.3)
waves = [
    ("Wave 1 | Market Visibility | Months 1–3",   ACCENT),
    ("Wave 2 | Intelligence & Analysis | Months 4–6", MID),
    ("Wave 3 | Decision Support | Months 7–9",    TEAL),
    ("Wave 4 | Optimisation & Scale | Months 10–12", PURPLE),
]
for wtext, wc in waves:
    add_rect(s, rx, my, Inches(3.9), Inches(0.38), fill_rgb=DKNAVY, line_rgb=wc, line_pt=0.75)
    add_textbox(s, rx + Inches(0.1), my + Inches(0.07), Inches(3.6), Inches(0.26),
                wtext, font_size=8.5, bold=True, color=wc)
    my += Inches(0.44)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — Executive Summary
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "EXECUTIVE SUMMARY", "Strategic Context, Challenge and Recommendation", 2)

cards = [
    (ACCENT, LIGHT, "THE OPPORTUNITY", ACCENT,
     "PCWs are a primary and growing General Insurance acquisition channel under daily competitive pressure", NAVY,
     "Price Comparison Websites now influence the majority of UK General Insurance new business, with over 80% of motor customers and a growing proportion of home customers using at least one PCW during their purchase journey. Customers simultaneously compare premium, excess levels, product features, optional add-on covers and brand reputation across ten or more competing providers in a single session. Small movements in PCW ranking position — even a shift from position four to position two — can drive material increases in quote volume and new business conversion, directly impacting LBG's top-line growth. The competitive intensity on PCWs continues to increase as more providers invest in dynamic pricing and real-time proposition management, raising the stakes for firms without equivalent capability.",
     SUB),
    (MID, LIGHT, "THE CHALLENGE", MID,
     "Current monitoring is periodic, manual, siloed and unable to match the velocity of market change", NAVY,
     "LBG's existing approach to PCW competitive intelligence relies on scheduled manual reviews conducted at irregular intervals by individual analysts across pricing, product and proposition teams. Data is collected inconsistently, stored in disparate spreadsheets and interpreted independently by different functions without a common taxonomy or analytical framework. By the time competitive trends are identified, escalated and converted into actions, the market has typically already moved — leaving LBG responding to events that occurred days or weeks earlier. There is no simulation capability to model intervention impact, no continuous cross-channel tracking and no closed feedback loop to measure whether actions taken have achieved their intended commercial outcomes.",
     SUB),
    (NAVY, NAVY, "THE RECOMMENDATION", GOLD,
     "Deploy an ENVOY-powered Competitive Intelligence & Optimisation Platform", WHITE,
     "Leverage LBG's ENVOY Agentic Platform — combining ML models on Vertex AI evaluated through Pegasus, Gemini-powered Generative AI and ADK-orchestrated Agentic agents on Google Cloud — to establish a continuous, governed, end-to-end competitive intelligence and optimisation capability. The platform automatically collects PCW market data via intelligent agents, detects ranking and competitor behaviour changes using ML, synthesises actionable intelligence and recommendations using Gemini, routes all recommendations through Pega-governed human approval workflows, and executes approved changes via Apigee-managed integrations to AGGS, Duck Creek and Pricing Services — with every step observable through ObserveAll and auditable through the ENVOY Audit Framework.",
     RGBColor(0xCC, 0xD6, 0xE8)),
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
    add_textbox(s, cx + Inches(0.12), cy + Inches(0.35), cw - Inches(0.2), Inches(0.52),
                ttl, font_size=11, bold=True, color=ttl_c)
    add_textbox(s, cx + Inches(0.12), cy + Inches(0.92), cw - Inches(0.2), Inches(2.72),
                body, font_size=9, color=body_c)
    cx += Inches(4.17)

# Outcome chips
add_textbox(s, Inches(0.5), Inches(5.15), Inches(6), Inches(0.22),
            "EXPECTED OUTCOMES", font_size=7.5, bold=True, color=MUTED)
outcomes = [
    "Materially improved PCW ranking position across Motor, Home and GI product lines through evidence-based interventions",
    "Competitor response time reduced from days to under two hours via continuous ENVOY agent monitoring and event-driven analysis",
    "Simulation-backed, evidence-based pricing and proposition decisions replacing analyst judgement under uncertainty",
    "Significant reduction in analyst FTE effort on low-value data collection, formatting and consolidation tasks",
    "Reusable ENVOY platform capability extensible across broader BCB General Insurance use cases at lower incremental cost",
]
ox = Inches(0.5)
for oc in outcomes:
    ow = Inches(2.45)
    add_rect(s, ox, Inches(5.38), ow, Inches(0.72), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, ox, Inches(5.38), Inches(0.05), Inches(0.72), fill_rgb=TEAL)
    add_textbox(s, ox + Inches(0.1), Inches(5.43), ow - Inches(0.15), Inches(0.62),
                oc, font_size=8, color=TEXT)
    ox += Inches(2.58)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — Why PCWs Matter
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "MARKET CONTEXT", "Why Price Comparison Websites Are Business-Critical for LBG General Insurance", 3)

# Left column
lx = Inches(0.5)
add_textbox(s, lx, Inches(1.15), Inches(6.0), Inches(0.3),
            "The PCW Landscape", font_size=12, bold=True, color=NAVY)

left_cards = [
    ("Customer Behaviour & Channel Influence",
     "Over 80% of UK motor insurance customers use at least one Price Comparison Website during their purchase journey, with multi-PCW behaviour — visiting two or more platforms before purchasing — increasingly common as customers maximise their comparison coverage. Home insurance PCW penetration continues to grow year-on-year as post-cost-of-living price sensitivity makes comparison shopping the default consumer behaviour rather than the exception for the majority of the UK insurance-buying population. Customers simultaneously evaluate ten or more competing providers on price, excess levels, optional cover inclusions, add-on packages, claims process ratings and brand trust scores, meaning LBG is competing on multiple dimensions in every single PCW session. Any sustained period of sub-optimal PCW positioning — whether caused by uncompetitive pricing, product feature gaps or PCW algorithm changes — translates directly and immediately into lost quote volume and reduced new business conversion across the affected product lines."),
    ("Ranking Economics & Volume Impact",
     "PCW results pages exhibit strong position bias: positions one to three capture a disproportionate share of customer clicks, quote completions and policy purchases compared to positions four and below, making rank position one of the single most commercially important variables in LBG's PCW performance. Empirical analysis across UK PCW markets indicates that moving from position five to position two can increase quote volume by 30–50% depending on the specific PCW, brand profile, product line and risk segment. The relationship between rank position and conversion is non-linear — the incremental value of moving from third to first significantly outweighs the value of moving from eighth to sixth. Rank position is determined by a combination of premium competitiveness, product feature scoring, excess structure alignment, PCW algorithm weighting and, increasingly, customer review scores — requiring competitive intelligence spanning both pricing and proposition in equal measure."),
    ("Competitor Velocity & Market Dynamics",
     "Analysis of UK PCW markets shows that leading competitors make pricing or proposition adjustments multiple times per week, with frequency increasing during peak periods — renewal windows, seasonal weather events and competitor campaign launches — creating sustained periods of market volatility that require continuous monitoring rather than periodic review. Regulatory changes such as the FCA's General Insurance pricing rules have intensified market dynamics, as competitors repriced portfolios and adjusted PCW strategies in response, creating periods of significant ranking volatility requiring rapid, informed responses from all market participants. Claims inflation cycles, reinsurance cost movements and weather events create market-wide pricing pressures that competitors respond to at different speeds, generating both risks — where competitors move before LBG — and opportunities where LBG can establish competitive advantage through faster, better-informed responses. Without continuous monitoring capability, LBG cannot reliably detect these movements until their impact on quote volumes is already being felt and the window for optimal response has narrowed."),
]
ly = Inches(1.5)
for ttl, body in left_cards:
    ch = Inches(1.82)
    add_rect(s, lx, ly, Inches(6.0), ch, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, lx, ly, Inches(0.05), ch, fill_rgb=ACCENT)
    add_textbox(s, lx + Inches(0.12), ly + Inches(0.08), Inches(5.8), Inches(0.26),
                ttl, font_size=10.5, bold=True, color=NAVY)
    add_textbox(s, lx + Inches(0.12), ly + Inches(0.35), Inches(5.8), ch - Inches(0.4),
                body, font_size=9, color=SUB)
    ly += ch + Inches(0.08)

# Right column
rx2 = Inches(6.8)
add_textbox(s, rx2, Inches(1.15), Inches(5.8), Inches(0.3),
            "Strategic Implications for LBG", font_size=12, bold=True, color=NAVY)

right_cards = [
    (MID, "Real-Time Intelligence is Now a Competitive Necessity",
     "Firms that can sense and respond to material PCW market movements within hours — rather than days or weeks — consistently outperform on PCW conversion metrics and new business volumes across the UK General Insurance market. Intelligence latency is directly and measurably correlated with lost volume during competitor campaign periods, regulatory-driven repricing events and seasonal market shifts. The growing investment by major PCW competitors in dynamic pricing infrastructure and real-time market monitoring means that periodic manual review processes are no longer adequate to maintain competitive parity, let alone competitive advantage. Establishing a continuous, automated competitive intelligence capability is therefore not a discretionary enhancement but a structural competitive requirement for LBG to protect and grow its PCW new business volumes in an increasingly dynamic market.",
     Inches(1.62), NAVY),
    (MID, "Proposition is as Critical as Price",
     "PCW ranking algorithms have evolved significantly beyond simple premium comparison, increasingly incorporating product feature scores, excess structure alignment, optional cover availability, claims process quality ratings and customer review data alongside raw premium in their ranking calculations. This means pricing competitiveness alone is insufficient to maintain strong PCW positions — LBG must also monitor and respond to competitor proposition changes including new optional covers, revised excess tiers, enhanced product features and bundled add-on packages. Competitive intelligence must therefore span the full product proposition, requiring a combination of structured data analysis, natural language processing for proposition assessment and ML models for feature scoring — all capabilities available within the ENVOY platform. Proposition gaps that go undetected can persist for weeks or months in a manual monitoring environment, silently eroding PCW ranking and conversion performance.",
     Inches(1.62), NAVY),
    (RED, "Current State Risk",
     "Without a continuous monitoring capability, LBG is systematically exposed to periods of sustained competitive disadvantage on PCWs — particularly during competitor promotional campaigns, FCA-triggered market-wide repricing events, claims inflation cycles and PCW algorithm updates, all of which create significant ranking volatility requiring rapid, informed responses. Each monitoring gap represents a window during which competitor movements that disadvantage LBG's ranking go undetected and unaddressed, translating directly into lost quote volume and foregone new business revenue. The reputational and commercial risk of a prolonged period of poor PCW positioning — particularly on high-volume PCWs during peak renewal periods — is material and is not currently being systematically managed through the existing manual review process.",
     Inches(1.45), RED),
]
ry = Inches(1.5)
for sc, ttl, body, ch, ttl_c in right_cards:
    add_rect(s, rx2, ry, Inches(5.8), ch, fill_rgb=WARM, line_rgb=BORDER, line_pt=0.4)
    add_rect(s, rx2, ry, Inches(0.05), ch, fill_rgb=sc)
    add_textbox(s, rx2 + Inches(0.12), ry + Inches(0.08), Inches(5.6), Inches(0.26),
                ttl, font_size=10.5, bold=True, color=ttl_c)
    add_textbox(s, rx2 + Inches(0.12), ry + Inches(0.36), Inches(5.6), ch - Inches(0.42),
                body, font_size=9, color=SUB)
    ry += ch + Inches(0.12)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — Current State Assessment
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "CURRENT STATE ASSESSMENT", "How We Operate Today — Diagnosis of the Current Monitoring Model", 4)

steps = [
    ("01 / MONITORING",
     "Market reviews are conducted on an ad hoc or loosely scheduled basis with no defined minimum frequency or coverage requirement across PCW channels, product lines or competitor sets. Individual analysts access PCW platforms manually, capturing data in varied formats with no common taxonomy, data dictionary or quality standard — meaning the competitive dataset that results is inconsistent, incomplete and not reliably comparable across time periods or teams. Coverage varies significantly across the organisation: some teams monitor selected competitors on selected PCWs periodically, while others have limited visibility of market positioning altogether. Competitor changes — pricing adjustments, product enhancements, offer launches, PCW algorithm responses — can therefore occur and persist for days or weeks before detection, during which time their impact on ranking position and quote volumes is already being felt."),
    ("02 / ANALYSIS",
     "Data collected through manual monitoring is consolidated in spreadsheets, shared drives and email threads with no common data model, no version control and no systematic approach to data quality validation or anomaly detection. Analysis is conducted independently by pricing, product and proposition teams who often arrive at different conclusions from similar data, creating inconsistencies in the competitive picture presented to decision-makers across the organisation. Historical data is rarely stored in a structured, queryable format — making trend analysis, competitor behaviour pattern detection and longitudinal comparison either impossible or highly time-consuming. There is no automated pattern detection, no anomaly flagging and no systematic significance scoring to distinguish material market movements requiring immediate action from routine market noise that can safely be deferred."),
    ("03 / DECISIONS",
     "Pricing and proposition decisions are made on the basis of incomplete, inconsistent and often outdated competitive intelligence, with decision-makers relying heavily on individual analyst judgement in the absence of systematic, data-driven competitive context. The lead time from initial data collection through analysis, escalation and decision typically spans multiple days to several weeks, by which time the competitive landscape has frequently changed further. There is no simulation or modelling capability to assess the likely commercial impact — on ranking position, quote volume or new business margin — of proposed interventions before execution, meaning decisions are made under significant uncertainty about their likely outcomes. The absence of a structured decision framework means similar competitive situations may be assessed and responded to differently by different teams, creating inconsistency in LBG's competitive behaviour across product lines and PCW channels."),
    ("04 / EXECUTION",
     "Once a decision to act is reached, execution requires manual coordination across multiple teams — pricing, product configuration, operations and technology — with no automated workflow, no defined SLA for execution speed and no systematic tracking of change status from approval to live market deployment. The multi-team handoff process introduces additional latency between decision and market impact, further widening the gap between competitor movement and LBG's effective response. Changes are implemented through existing systems — AGGS, Duck Creek and Pricing Services — but without a standardised, automated integration pattern, making each execution an ad hoc exercise that varies in speed and reliability depending on team availability and process adherence. There is no mechanism to automatically initiate post-change impact monitoring once a change is executed, meaning the feedback loop between action and outcome measurement is manual, irregular and incomplete."),
    ("05 / OUTCOME",
     "The cumulative effect of delayed monitoring, incomplete analysis, uncertain decisions and slow execution is a fundamentally reactive competitive posture in which LBG consistently responds to competitor actions rather than anticipating or pre-empting them, ceding competitive advantage during every monitoring and decision gap. Opportunity windows — periods during which LBG could improve ranking position by acting on competitor weaknesses or market gaps — are routinely missed because they are not identified in time for an effective response to be mounted. The manual effort required to sustain even the current incomplete monitoring process represents a significant ongoing FTE cost that is difficult to justify given the limited, inconsistent intelligence it produces. The absence of a closed feedback loop means there is no reliable mechanism to determine whether competitive actions taken have achieved their intended outcomes, making continuous improvement of the competitive response process effectively impossible."),
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
by = Inches(4.05)
# Left friction card
add_rect(s, Inches(0.35), by, Inches(5.8), Inches(2.15), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
add_rect(s, Inches(0.35), by, Inches(5.8), Inches(0.05), fill_rgb=ACCENT)
add_textbox(s, Inches(0.47), by + Inches(0.1), Inches(5.6), Inches(0.3),
            "Key Friction Points", font_size=11, bold=True, color=NAVY)
bullet_list(s, Inches(0.47), by + Inches(0.45), Inches(5.6), Inches(1.6),
            ["No single source of truth for competitor positioning data — multiple teams maintain separate, inconsistent datasets with no common taxonomy, data standard or quality framework, making organisational alignment on competitive position difficult to achieve",
             "Analysis capability does not scale with market complexity — the number of PCWs, competitors, product lines and proposition dimensions requiring monitoring far exceeds what manual effort can sustain reliably or consistently",
             "Decision latency creates exploitable competitive windows — the time between competitor action and LBG response regularly spans multiple days, during which ranking and volume impact accumulates without countermeasure",
             "No closed-loop measurement framework — the absence of systematic outcome tracking makes it impossible to determine whether competitive interventions have achieved their intended commercial impact or to improve future decisions",
             "Siloed tooling and data across pricing, product and operations teams — no integrated view of competitive position, no shared analytical framework and no common decision-support infrastructure to align responses"],
            font_size=9)

# Right org impact card
add_rect(s, Inches(6.7), by, Inches(5.88), Inches(2.15), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.4)
add_rect(s, Inches(6.7), by, Inches(5.88), Inches(0.05), fill_rgb=RED)
add_textbox(s, Inches(6.82), by + Inches(0.1), Inches(5.65), Inches(0.3),
            "Organisational Impact", font_size=11, bold=True, color=NAVY)
bullet_list(s, Inches(6.82), by + Inches(0.45), Inches(5.65), Inches(1.6),
            ["Sub-optimal PCW ranking position sustained during competitor promotional campaigns, seasonal peaks and regulatory repricing events due to delayed detection of competitive movements and slow organisational response",
             "Pricing teams making decisions without full, current competitive market context — introducing unnecessary uncertainty and increasing the risk of commercially suboptimal outcomes including margin sacrifice without ranking benefit",
             "Product proposition gaps versus competitors going undetected and unaddressed for extended periods, silently eroding PCW feature scoring and ranking performance across multiple product lines simultaneously",
             "Significant FTE effort consumed by low-value data collection, formatting and consolidation tasks that should be automated — reducing capacity for higher-value analytical and strategic pricing work",
             "Inconsistent competitive responses across product lines and PCW channels — similar competitive situations handled differently, creating unpredictable and suboptimal market behaviour that undermines competitive positioning"],
            font_size=9)

# Result bar
add_rect(s, Inches(0.35), Inches(6.38), Inches(12.63), Inches(0.52),
         fill_rgb=RGBColor(0xFE, 0xF3, 0xC7))
add_rect(s, Inches(0.35), Inches(6.38), Inches(0.06), Inches(0.52), fill_rgb=GOLD)
add_textbox(s, Inches(0.5), Inches(6.43), Inches(12.3), Inches(0.42),
            "Net Result: LBG operates a reactive competitive posture on PCWs, consistently responding to competitor actions after their market impact has already been felt — ceding competitive advantage during every monitoring gap and analysis delay in the current process",
            font_size=9, bold=True, color=TEXT)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — Strategic Hypothesis
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "STRATEGIC RATIONALE", "The Strategic Hypothesis — From Reactive Monitoring to Proactive Optimisation", 5)

blocks = [
    ("IF", ACCENT,
     "LBG establishes continuous, automated, real-time capture of competitor pricing, product features, excess structures, optional covers and full proposition data across all active PCW channels — creating a persistent, validated, queryable competitive intelligence dataset that is independent of manual collection schedules, individual analyst availability or team bandwidth constraints, and that refreshes with a target data freshness of less than 15 minutes from market change to platform awareness via ENVOY ADK agents and Pub/Sub event streaming"),
    ("AND", MID,
     "This intelligence is processed by a layered AI capability stack on LBG's ENVOY platform on Google Cloud — with ML models on Vertex AI evaluated through Pegasus performing pattern detection, trend identification, anomaly flagging and pricing elasticity simulation; Gemini-powered Generative AI synthesising unstructured competitor data, drafting recommendation rationale and generating explainable intelligence briefings; and ENVOY ADK-orchestrated Agentic workflows autonomously coordinating multi-step investigation, simulation and recommendation generation with full observability through ObserveAll and governed routing through Cortex"),
    ("THEN", TEAL,
     "Pricing, product and proposition decision-makers receive timely, structured, prioritised and fully explainable AI-generated recommendations — each accompanied by supporting evidence, confidence scores, simulated commercial impact quantification and human-readable rationale drafted by Gemini — enabling faster, better-informed competitive interventions within a clear, FCA-compliant human governance framework in which every recommendation, approval, modification and rejection is permanently recorded in the ENVOY Audit Framework"),
]

by2 = Inches(1.2)
bh = Inches(1.05)
for lbl, lc, content in blocks:
    add_rect(s, Inches(0.5), by2, Inches(0.6), bh, fill_rgb=lc)
    add_textbox(s, Inches(0.5), by2 + Inches(0.32), Inches(0.6), Inches(0.36),
                lbl, font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(s, Inches(1.1), by2, Inches(11.73), bh, fill_rgb=WHITE, line_rgb=BORDER, line_pt=0.5)
    add_textbox(s, Inches(1.2), by2 + Inches(0.1), Inches(11.5), bh - Inches(0.15),
                content, font_size=9.5, color=TEXT)
    by2 += Inches(1.15)

# Result bar
add_rect(s, Inches(0.5), Inches(4.7), Inches(12.33), Inches(1.05), fill_rgb=NAVY)
add_rect(s, Inches(0.5), Inches(4.7), Inches(0.06), Inches(1.05), fill_rgb=GOLD)
add_textbox(s, Inches(0.65), Inches(4.75), Inches(1.2), Inches(0.25),
            "RESULTING IN", font_size=8, bold=True, color=GOLD)
add_textbox(s, Inches(0.65), Inches(5.0), Inches(12.0), Inches(0.7),
            "Improved PCW ranking and new business conversion across Motor, Home and GI product lines  |  Competitor response time reduced from days to hours through continuous ENVOY agent monitoring  |  Significant reduction in analyst FTE effort through intelligent automation  |  A reusable, extensible, enterprise-grade AI platform capability built on ENVOY's governance, evaluation and observability infrastructure",
            font_size=9.5, color=WHITE)

# Three metric boxes
metrics5 = [
    ("Speed", "Market signal to governed recommendation delivered in under 2 hours — versus a current process that typically takes multiple days from competitor change to decision-maker awareness and often longer to decision and execution"),
    ("Coverage", "100% of active PCW channels monitored continuously at sub-15-minute data freshness — versus current periodic, partial manual spot checks that leave significant monitoring gaps and detection delays"),
    ("Governance", "100% of AI-generated recommendations reviewed and approved by an authorised human decision-maker before any market change is executed — no autonomous pricing action without human sign-off at every stage"),
]
mx5 = Inches(0.5)
for mk, mv in metrics5:
    add_rect(s, mx5, Inches(5.95), Inches(3.9), Inches(1.0), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, mx5, Inches(5.95), Inches(3.9), Inches(0.05), fill_rgb=TEAL)
    add_textbox(s, mx5 + Inches(0.1), Inches(6.03), Inches(3.7), Inches(0.22),
                mk + ":", font_size=8.5, bold=True, color=TEAL)
    add_textbox(s, mx5 + Inches(0.1), Inches(6.23), Inches(3.7), Inches(0.65),
                mv, font_size=9, color=SUB)
    mx5 += Inches(4.02)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — ENVOY Platform Overview (Dense capability matrix)
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "ENVOY PLATFORM", "ENVOY — LBG's Enterprise Agentic AI Runtime & Governance Platform", 6)

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
    ("PLATFORM SERVICES",NAVY,   Inches(5.26)),
]
for rl, rc, ry in row_labels:
    add_rect(s, Inches(0.5), ry, Inches(0.42), row_h, fill_rgb=rc)
    add_textbox(s, Inches(0.5), ry + Inches(0.42), Inches(0.42), Inches(0.38),
                rl, font_size=6.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Grid data — expanded descriptions
grid_data = [
    # Row 1 AGENTIC
    [
        ["Agent execution engine — manages lifecycle, tool calls & state",
         "Session & state management — persists context across workflows",
         "Memory & tool execution — retrieves agent memory & tools",
         "Multi-agent (A2A) execution — coordinates agent collaboration",
         "MCP tool integration — connects to external data sources"],
        ["Workflow orchestration — coordinates multi-step pipelines",
         "Agent coordination (A2A) — manages inter-agent communication",
         "Event-driven execution — triggers from Pub/Sub market events",
         "Long-running process management — workflows spanning hours",
         "Human-in-the-loop triggers — escalates to Pega at governance gates",
         "Escalation & routing — exception handling and human paths"],
        ["Context assembly — builds rich context packages per agent call",
         "RAG orchestration — retrieves ranked knowledge from Vector Search",
         "Cross-agent context sharing — passes intelligence via Session Store",
         "Knowledge retrieval — queries competitor intelligence in real time",
         "Policy & rule retrieval — accesses pricing rules from Policy Registry",
         "MCP server access — connects to PCW data source MCP servers"],
        ["Enterprise guardrails — enforces policy on all agent inputs/outputs",
         "PII masking & DLP — detects & redacts personal data via GCP DLP",
         "Prompt protection — prevents injection attacks via Model Armor",
         "Model routing (Cortex) — routes all model calls through control plane",
         "Output validation — validates agent outputs against defined schemas",
         "Compliance controls — enforces regulatory rules on all outputs"],
        ["Prompt evaluation — assesses prompt quality over time",
         "Agent & workflow evaluation — end-to-end perf via Pegasus",
         "Hallucination detection — identifies unsupported Gemini claims",
         "Safety & bias checks — screens outputs for unsafe content",
         "Regression testing — validates behaviour against golden datasets",
         "Golden dataset testing — curated test sets for quality assurance"],
        ["Agent traces & logs — full execution traces in Cloud Logging",
         "Tool & prompt visibility — records all tool calls for auditability",
         "Cost & latency monitoring — tracks token usage via ObserveAll",
         "Drift & anomaly detection — detects performance degradation",
         "Audit trails & alerts — alerts for policy violations & degradation",
         "SLA & reliability monitoring — platform availability & SLA compliance"],
    ],
    # Row 2 ML MODELS
    [
        ["Memory ranking — scores agent memory entries by relevance",
         "Intent classification — classifies requests and market signals",
         "Tool recommendation — selects optimal tools per agent task",
         "Session summarisation — compresses sessions to concise summaries"],
        ["Routing prediction — predicts optimal workflow path from input",
         "Next best action — recommends next agent action in workflows",
         "SLA breach prediction — forecasts governance SLA compliance",
         "Queue prioritisation — prioritises by commercial urgency"],
        ["Embedding generation — dense vector representations of competitor data",
         "Retrieval ranking — scores retrieved knowledge by relevance",
         "Semantic similarity — measures distance between market signals",
         "Context relevance scoring — rates retrieved context relevance"],
        ["Toxicity detection — classifies outputs for policy violations",
         "PII detection (ML) — identifies personal data in unstructured text",
         "Policy violation scoring — quantifies output compliance risk",
         "Risk & confidence scoring — probability scores per recommendation"],
        ["Quality scoring — rates recommendation quality dimensions",
         "Groundedness scoring — measures data-grounding of outputs",
         "Faithfulness scoring — evaluates output faithfulness to evidence",
         "Model drift detection — identifies statistical drift over time"],
        ["Anomaly detection — unusual patterns in agent performance",
         "Capacity prediction — forecasts infrastructure requirements",
         "Failure prediction — predicts component failures proactively",
         "Usage forecasting — models future platform cost and usage"],
    ],
    # Row 3 GEN AI
    [
        ["Agent reasoning — structured reasoning chains for agent decisions",
         "Tool use planning — plans sequences of tool calls for tasks",
         "Memory summarisation — compresses agent memory efficiently",
         "Response generation — structured formatted recommendation outputs"],
        ["Workflow planning — decomposes objectives into workflow steps",
         "Decision rationale — drafts human-readable recommendation rationale",
         "Task decomposition — breaks compound tasks into subtasks",
         "Dynamic replanning — replans workflows when obstacles arise"],
        ["RAG & retrieval — formulates queries, synthesises retrieved knowledge",
         "Context synthesis — integrates multi-agent outputs into narratives",
         "Document summarisation — extracts insights from product documents",
         "Policy interpretation — translates policy into agent constraints"],
        ["Guardrail reasoning — evaluates borderline cases against policies",
         "Policy compliance check — assesses recommendations for compliance",
         "Output transformation — reformats outputs to governance schemas",
         "Explanation generation — FCA-compliant AI decision explanations"],
        ["Evaluation explanation — natural-language evaluation summaries",
         "Error analysis — recommends remediation for agent failures",
         "Test case generation — creates golden tests from edge cases",
         "Insight summarisation — executive summaries of quality reports"],
        ["Anomaly explanation — root cause analysis for platform anomalies",
         "Incident summarisation — structured reports for platform events",
         "Auto-remediation advice — recommends fixes for operational issues",
         "Operational insights — actionable intelligence from telemetry"],
    ],
    # Row 4 PLATFORM SERVICES
    [
        ["Session Store — persists state across multi-turn agent workflows",
         "Memory Store — stores long-term agent knowledge and history",
         "A2A Registry — agent-to-agent communication & discovery",
         "MCP Registry — catalogues available MCP tool servers",
         "Tool Registry — authorised tool catalogue per agent class"],
        ["LangGraph — stateful graph-based multi-agent orchestration",
         "Cloud Workflows — durable enterprise process orchestration",
         "Pub/Sub — real-time market event stream delivery",
         "Eventarc — routes GCP events to ENVOY agent triggers",
         "Routing Rules Engine — business governance routing logic"],
        ["Vertex AI Vector Search — low-latency semantic search",
         "BigQuery — competitor market data storage at scale",
         "Cloud SQL (PostgreSQL) — ENVOY relational metadata store",
         "Knowledge Graph — competitor & market relationship modelling",
         "MCP Servers — structured data sources as MCP servers"],
        ["Cortex (Control Plane) — centralised governance & policy enforcement",
         "Model Armor — prompt injection protection & output safety",
         "Policy Engine — evaluates recommendations against policy rules",
         "RBAC & ABAC — role and attribute-based access controls",
         "Compliance Rules — FCA, GDPR & LBG compliance as policies"],
        ["Pegasus (LBG) — proprietary ML evaluation & governance platform",
         "Vertex AI Evaluation — automated Gemini quality assessment",
         "ADK Evaluation — agent performance evaluation framework",
         "Evaluation Framework — quality gate enforcement & scheduling",
         "Golden Test Suites — curated reference datasets for regression"],
        ["ObserveAll (LBG) — enterprise observability for agents & models",
         "Dynatrace — full-stack infrastructure & APM monitoring",
         "Cloud Monitoring — GCP resource metrics & uptime monitoring",
         "Cloud Logging — centralised structured log management",
         "Audit Framework — immutable decision & action audit trail"],
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
slide_chrome(s, "AI TECHNOLOGY STRATEGY", "AI Capability Spectrum — Deploying the Right AI Technology for Each Problem", 7)

cols7 = [
    {
        "header": "Machine Learning",
        "sub": "Pattern Detection, Prediction & Simulation",
        "hc": ACCENT,
        "tags": ["Vertex AI", "Pegasus (LBG)", "BigQuery ML"],
        "use_label": "PCW Applications",
        "use_cases": [
            "PCW ranking position trend prediction and trajectory modelling across all monitored channels and competitors, trained on historical ranking data and updated continuously via Pegasus retraining pipelines",
            "Pricing elasticity modelling to quantify the expected new business volume and revenue impact of proposed price changes across risk segments and PCW channels, with confidence intervals and scenario comparison",
            "Competitor behaviour clustering to identify strategic groupings across the competitor set and predict likely future competitive moves based on historical behaviour patterns detected in PCW data",
            "Anomaly detection to flag statistically significant departures from expected market patterns in real time, enabling immediate investigation of material competitor movements before their volume impact accumulates",
            "Quote conversion propensity scoring to prioritise competitive interventions by expected commercial impact, ensuring pricing team attention is directed at the highest-value opportunities first",
            "Pricing simulation modelling of proposed interventions before recommendation to pricing teams, quantifying expected ranking, volume and margin outcomes with Pegasus-evaluated confidence scores",
        ],
        "chars": "High predictive accuracy on structured market data with SHAP-based explainability. All models evaluated, monitored and governed through Pegasus with champion/challenger testing and automated drift detection. Production-proven at LBG scale with low inference latency suitable for near-real-time competitive monitoring.",
        "w": Inches(3.3),
    },
    {
        "header": "Generative AI (Gemini)",
        "sub": "Analysis, Synthesis, Explanation & Recommendation",
        "hc": TEAL,
        "tags": ["Gemini Pro / Flash", "Vertex AI", "RAG via BigQuery"],
        "use_label": "PCW Applications",
        "use_cases": [
            "Competitor proposition narrative analysis — extracting key features, differentiators and strategic positioning signals from PCW product descriptions, terms and conditions and marketing materials at scale",
            "Executive intelligence briefing generation — synthesising multi-source competitive data from across the ENVOY agent network into concise, structured, readable briefings for senior stakeholders with key actions highlighted",
            "Recommendation rationale drafting — producing human-readable, FCA-compliant explanations of AI-generated pricing and proposition recommendations that enable pricing teams to make informed approval decisions",
            "Market commentary synthesis — integrating pricing, product, offer and ranking data from multiple agents into coherent competitive market narratives that contextualise movements and identify strategic patterns",
            "Regulatory change impact assessment — interpreting FCA guidance updates and translating their competitive implications for PCW positioning into actionable intelligence for the pricing and compliance teams",
            "Customer review sentiment analysis — extracting structured competitive intelligence from PCW customer review data to identify service and product quality differentiators that influence PCW algorithm ranking",
        ],
        "chars": "Transforms large volumes of unstructured competitor data into actionable, readable intelligence — reducing analyst synthesis effort by 60–80% for routine briefing tasks. All Gemini outputs governed through Model Armor and Cortex. Hallucination detection and groundedness scoring via Pegasus Evaluation Framework before presentation to decision-makers.",
        "w": Inches(3.3),
    },
    {
        "header": "Agentic AI (ENVOY / ADK)",
        "sub": "Orchestration, Automation & Multi-Step Intelligence",
        "hc": PURPLE,
        "tags": ["ENVOY ADK", "Vertex AI Agent Engine", "LangGraph"],
        "use_label": "PCW Applications",
        "use_cases": [
            "Autonomous end-to-end PCW market data collection, validation and enrichment without human intervention, operating on defined schedules and triggered by real-time market events via Pub/Sub",
            "Multi-step competitor investigation workflows that chain ML analysis, Gemini synthesis and human escalation into coherent, governed end-to-end intelligence generation processes orchestrated via LangGraph",
            "Event-triggered analysis — automatically initiating deep, multi-agent investigation when ML anomaly detection flags a material market movement, ensuring rapid response without manual escalation",
            "Cross-agent intelligence aggregation — combining outputs from specialist pricing, proposition, ranking and competitor analysis agents into unified, coherent recommendation packages via the Orchestrator Agent",
            "Simulation scenario orchestration — autonomously running and comparing multiple pricing and proposition intervention scenarios via the Simulation Agent before synthesis into recommendation packages",
            "Governance escalation routing — automatically determining the appropriate Pega approval tier based on recommendation type, magnitude and risk classification, and routing accordingly via Cortex",
        ],
        "chars": "Combines ML models and Gemini GenAI within governed, observable, multi-step autonomous workflows. Human-in-the-loop gates enforced at defined decision points via Pega. Full execution observability through ObserveAll and Dynatrace with complete audit trail in the ENVOY Audit Framework.",
        "w": Inches(3.3),
    },
    {
        "header": "ENVOY Platform Foundation",
        "sub": None,
        "hc": NAVY,
        "tags": [],
        "use_label": None,
        "use_cases": [],
        "chars": None,
        "w": Inches(2.85),
        "platform_items": [
            "Google Cloud Platform (GCP)",
            "Vertex AI Agent Engine",
            "ADK — Agent Developer Kit",
            "Gemini Pro & Flash (LLM)",
            "Cortex — AI Control Plane",
            "Pegasus — LBG Model Evaluation",
            "Model Armor — Safety Layer",
            "Apigee — API Management Gateway",
            "Pega — Governance Workflow Engine",
            "ObserveAll — Enterprise Observability",
            "Dynatrace — Infrastructure Monitoring",
            "ENVOY Audit Framework",
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
                        pi, font_size=8.5, color=WHITE)
            iy += Inches(0.46)
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
        # Use cases label
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(0.95), cw7 - Inches(0.15), Inches(0.22),
                    col.get("use_label", "PCW Use Cases"), font_size=7.5, bold=True, color=MUTED)
        bullet_list(s, c7x + Inches(0.1), c7y + Inches(1.15), cw7 - Inches(0.15), Inches(2.6),
                    col["use_cases"], font_size=9.0, color=SUB)
        # Characteristics
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(3.85), cw7 - Inches(0.15), Inches(0.22),
                    "Characteristics", font_size=7.5, bold=True, color=MUTED)
        add_textbox(s, c7x + Inches(0.1), c7y + Inches(4.08), cw7 - Inches(0.15), Inches(1.95),
                    col["chars"], font_size=8.5, italic=True, color=SUB)

    c7x += cw7 + gap7


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — ENVOY Shared Services & Google Cloud Foundation
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "PLATFORM FOUNDATION", "ENVOY Shared Services & Google Cloud Platform Infrastructure", 8)

add_textbox(s, Inches(0.5), Inches(1.15), Inches(7), Inches(0.28),
            "ENVOY Shared Services — Enterprise-Grade Reusable Platform Components", font_size=10, bold=True, color=NAVY)

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

add_textbox(s, Inches(0.5), Inches(2.0), Inches(9), Inches(0.28),
            "Google Cloud Platform Foundation — Technology Stack Underpinning the Competitive Intelligence Platform",
            font_size=10, bold=True, color=NAVY)

gcp_cols = [
    (MID,    "CHANNELS",
     ["APIs — RESTful and event-driven integration endpoints for all platform interactions",
      "Events — Pub/Sub and Eventarc for real-time event-driven agent triggering",
      "Applications — internal LBG business applications integrated via Apigee",
      "PCW Data Feeds — structured market data ingestion from Price Comparison Websites",
      "Webhook Triggers — real-time competitor change notification via event streaming"]),
    (ACCENT, "AGENT PLATFORM",
     ["Vertex AI Agent Engine — fully managed agent hosting, execution and scaling on GCP",
      "ADK (Agent Developer Kit) — framework for agent development, deployment and lifecycle management",
      "MCP Protocol — Model Context Protocol enabling structured tool integration for agents",
      "A2A Protocol — Agent-to-Agent communication standard for multi-agent coordination",
      "Agent Registry — centralised catalogue of all deployed agent versions and capabilities"]),
    (TEAL,   "AI PLATFORM",
     ["Gemini Pro / Flash — Google's foundation LLM powering analysis, synthesis and recommendation",
      "Cortex Control Plane — centralised model routing, policy enforcement and access governance",
      "Pegasus (LBG) — LBG's proprietary model evaluation, quality management and governance platform",
      "Model Armor — prompt injection protection and unsafe output filtering for all model calls",
      "Vertex AI Studio — model experimentation, fine-tuning and prompt engineering environment"]),
    (PURPLE, "KNOWLEDGE",
     ["Vertex AI Vector Search — low-latency semantic search over competitive intelligence embeddings",
      "BigQuery — enterprise-scale structured market data storage, analytics and ML feature engineering",
      "Cloud SQL (PostgreSQL) — relational store for ENVOY metadata, config and audit data",
      "Cloud Storage — competitive intelligence archive and ML model artefact repository",
      "Knowledge Graph — models relationships between competitors, products, PCWs and market events"]),
    (GREEN,  "INTEGRATION",
     ["Apigee API Gateway — secure, governed API management for all platform-to-system integrations",
      "Cloud Run — containerised microservice hosting for platform integration components",
      "Pub/Sub — reliable real-time event streaming between all platform components and agents",
      "Cloud Workflows — durable, managed orchestration for long-running process workflows",
      "Eventarc — event-driven routing from GCP services to ENVOY ADK agent triggers"]),
    (RGBColor(0x08, 0x91, 0xB2), "EVALUATION",
     ["Pegasus (LBG) — proprietary ML model evaluation, governance and retraining management",
      "Vertex AI Evaluation — automated Gemini output quality assessment across defined dimensions",
      "ADK Evaluation — ENVOY agent performance evaluation across accuracy and reliability",
      "Golden Test Suites — curated reference datasets for regression and quality gate testing",
      "Evaluation Pipelines — automated, scheduled quality gate enforcement across all models"]),
    (GOLD,   "OBSERVABILITY",
     ["ObserveAll (LBG) — enterprise observability integrating agent, model and business KPI metrics",
      "Dynatrace — full-stack infrastructure and application performance monitoring on GCP",
      "Cloud Monitoring — GCP resource metrics, uptime and SLA compliance monitoring",
      "Cloud Logging — centralised structured log management, alerting and audit support",
      "Audit Framework — immutable decision and action audit trail for FCA and governance compliance"]),
    (RED,    "SECURITY",
     ["IAM & RBAC — identity and role-based access control across all platform components",
      "VPC-SC — VPC Service Controls enforcing UK data residency and network boundaries",
      "Encryption — at-rest and in-transit encryption for all data, models and artefacts",
      "DLP — GCP Data Loss Prevention for PII detection and automatic redaction",
      "Model Armor — adversarial prompt protection and unsafe content output filtering",
      "FCA Controls — regulatory compliance requirements enforced as executable platform policies"]),
]
gcx = Inches(0.5)
gcw = Inches(1.55)
gcy = Inches(2.3)
gch = Inches(3.1)
for (gc, gh, gi) in gcp_cols:
    add_rect(s, gcx, gcy, gcw, gch, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, gcx, gcy, gcw, Inches(0.35), fill_rgb=gc)
    add_textbox(s, gcx + Inches(0.05), gcy + Inches(0.05), gcw - Inches(0.08), Inches(0.28),
                gh, font_size=8, bold=True, color=WHITE)
    bullet_list(s, gcx + Inches(0.07), gcy + Inches(0.4), gcw - Inches(0.1), gch - Inches(0.42),
                gi, font_size=8, color=SUB, indent="")
    gcx += gcw + Inches(0.04)

# Build vs Reuse
add_textbox(s, Inches(0.5), Inches(5.55), Inches(4), Inches(0.25),
            "Build vs Reuse — Architecture Principle", font_size=9, bold=True, color=NAVY)
reuse_items = [
    (GREEN,  "REUSE",
     "Apigee, Pega workflow engine, AGGS, Duck Creek, Pricing Services, ENVOY shared services and all existing Google Cloud infrastructure are reused without modification. Zero parallel infrastructure is created, and no existing capability is duplicated. Every integration reuses established Apigee patterns and governance controls already in place."),
    (MID,    "EXTEND",
     "Vertex AI ML pipelines and Pegasus evaluation framework are extended with new PCW-specific models, features, evaluation datasets and quality metrics. Existing MLOps patterns are reused and new PCW domain models are registered in the shared Model Registry, benefiting from existing governance and monitoring infrastructure."),
    (TEAL,   "CONFIGURE",
     "Gemini prompt templates are versioned and registered in the ENVOY Prompt Registry. Cortex routing rules are configured for PCW intelligence workflows. Model Armor policies are tuned for the PCW domain. RBAC policies are extended to cover new PCW CI platform roles without disrupting existing access control structures."),
    (PURPLE, "BUILD",
     "PCW-specific ENVOY ADK agents and intelligence orchestration workflows are the net-new capabilities — built on the existing ENVOY platform foundation using established ADK patterns, registered in the Agent Registry and governed through existing ENVOY governance, evaluation and observability controls from Day 1."),
]
rx8 = Inches(0.5)
for rc8, rl8, rd8 in reuse_items:
    bw8 = Inches(3.0)
    add_rect(s, rx8, Inches(5.8), bw8, Inches(1.05), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, rx8, Inches(5.8), Inches(0.05), Inches(1.05), fill_rgb=rc8)
    add_textbox(s, rx8 + Inches(0.1), Inches(5.83), Inches(0.7), Inches(0.22),
                rl8, font_size=8, bold=True, color=rc8)
    add_textbox(s, rx8 + Inches(0.1), Inches(6.04), bw8 - Inches(0.15), Inches(0.75),
                rd8, font_size=9, color=SUB)
    rx8 += bw8 + Inches(0.12)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — Target Operating Model
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "OPERATING MODEL",
             "Target Operating Model — ENVOY-Powered Seven-Stage Competitive Intelligence Cycle", 9)

steps9 = [
    (ACCENT,  "1 / SENSE",
     "ENVOY ADK Market Collection Agents autonomously and continuously collect PCW pricing, product, excess, optional cover and offer data across all monitored competitors and channels, operating on a defined schedule supplemented by real-time event-triggered collection via Pub/Sub when upstream anomaly detection flags a potential market change requiring immediate investigation. Data is validated against ML-based quality models in BigQuery, enriched with competitor metadata from the ENVOY Knowledge Graph, and streamed into the competitive intelligence feature store with a target freshness of under 15 minutes from market change to platform awareness. Agent execution, data quality metrics and collection SLA compliance are all continuously monitored by ObserveAll, with automated alerts and agent self-healing logic managing collection interruptions without human intervention in steady state.",
     "Agentic (ADK) + ML Validation + Pub/Sub", ACCENT),
    (MID,     "2 / ANALYSE",
     "ML models on Vertex AI, evaluated and governed through Pegasus, analyse the collected competitive intelligence dataset to detect ranking movements, pricing anomalies, competitor behaviour patterns and proposition changes — classifying each signal by significance, velocity, probable cause and commercial urgency using trained classification and anomaly detection models continuously updated with new market data. Material signals meeting defined significance thresholds automatically trigger the Competitor Analysis Agent via Cloud Workflows, while routine market updates are batched for periodic intelligence briefing generation. All model outputs include confidence scores and SHAP-based feature importance explanations, and are quality-checked by the Pegasus Evaluation Framework for groundedness and accuracy before onward processing to the Simulation and Recommendation stages.",
     "ML (Vertex AI) + Pegasus Eval + GenAI (Gemini)", MID),
    (TEAL,    "3 / SIMULATE",
     "The ENVOY Simulation Agent runs pricing elasticity and volume simulation models on Vertex AI to quantify the likely commercial impact — in ranking position change, quote volume delta and new business margin movement — of each potential intervention identified by the analysis stage, generating a ranked set of intervention scenarios with confidence intervals for each key outcome metric based on LBG's historical PCW performance data. Simulation results are stored in BigQuery and automatically retrieved by the Recommendation Agent as quantified evidence underpinning each recommendation, ensuring that every recommendation presented to pricing teams is supported by a simulation-validated estimate of expected commercial impact rather than analyst intuition alone.",
     "ML Simulation (Vertex AI) + BigQuery", TEAL),
    (PURPLE,  "4 / RECOMMEND",
     "The ENVOY Recommendation Agent uses Gemini to synthesise the outputs of all upstream specialist agents into a structured, prioritised set of actionable recommendations, each accompanied by a Gemini-generated human-readable rationale, supporting evidence references, confidence score, urgency classification and simulated impact quantification that together provide pricing teams with everything they need to make an informed approval decision without querying additional systems. Recommendations are validated against business and regulatory policy rules by the ENVOY Policy Engine and screened through Model Armor before being formatted for Pega governance workflow and routed through Cortex to the appropriate approval tier based on change type, magnitude and risk classification.",
     "GenAI (Gemini) + Cortex Routing + Policy Engine", PURPLE),
    (GOLD,    "5 / GOVERN",
     "Recommendations are delivered to pricing and proposition teams through Pega-managed governance workflows that present the full recommendation package — rationale, evidence, simulation results, confidence scores and risk assessment — in a single, structured interface, enabling informed human judgement without the need to navigate separate systems or request additional context from the intelligence team. Tiered approval authority is applied automatically — tactical adjustments follow a streamlined single-approver process while material pricing changes route to senior sign-off — with all routing, escalation and SLA management handled by Pega. Every approval, modification, rejection and escalation is permanently recorded in the ENVOY Audit Framework with full decision lineage and user attribution for FCA compliance.",
     "Human + Pega Workflow + ENVOY Audit Framework", GOLD),
    (GREEN,   "6 / EXECUTE",
     "Approved changes are executed automatically through Apigee-managed API integrations to AGGS for PCW rate submissions, Duck Creek for policy and product updates, and Pricing Services for band and rate adjustments — eliminating manual handoffs and reducing execution latency from approval to live market deployment from days to minutes. Execution is confirmed via API response, logged in Cloud Logging and the ENVOY Audit Framework, and a post-change monitoring task is automatically initiated in ObserveAll to track the PCW performance impact of the executed change against the pre-change baseline and the simulation-predicted outcome trajectory, immediately beginning the learning cycle.",
     "Agentic + Apigee + AGGS / Duck Creek / Pricing Services", GREEN),
    (RGBColor(0x08, 0x91, 0xB2), "7 / LEARN",
     "The ENVOY Learning Agent continuously ingests post-execution PCW performance data from ObserveAll, comparing observed ranking, volume and margin outcomes against both pre-change baselines and simulation-predicted results to calculate recommendation accuracy scores and identify systematic patterns in model over- or under-prediction that indicate recalibration requirements. Model performance trends are surfaced in Pegasus dashboards and reviewed by the data science team, with automated retraining of ML models triggered on Vertex AI when statistical drift exceeds defined thresholds — ensuring the platform's predictive accuracy and recommendation quality compound over time as the feature store accumulates richer intervention and outcome data.",
     "ML (Vertex AI) + Pegasus + GenAI (Gemini) + ObserveAll", RGBColor(0x08, 0x91, 0xB2)),
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
                tag9, font_size=7, bold=True, color=tc9)
    if i < 6:
        add_textbox(s, s9x + s9w + Inches(0.01), s9y + Inches(0.08), Inches(0.06), Inches(0.28),
                    ">", font_size=10, bold=True, color=MUTED)
    s9x += s9w + gap9


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — Capability Architecture (5 Layers)
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "CAPABILITY ARCHITECTURE",
             "Competitive Intelligence Platform — Five-Layer Capability Architecture", 10)

layers = [
    (ACCENT, "Market Intelligence Layer",
     ["PCW ranking capture across all active channels and brands",
      "Competitor price monitoring with near-real-time refresh",
      "Product feature & excess structure tracking per competitor",
      "Optional cover & add-on monitoring across PCW channels",
      "Promotional offer & campaign detection and alerting",
      "PCW algorithm change detection via ML pattern analysis",
      "Data freshness SLA: sub-15-minute target via ADK agents",
      "ENVOY ADK Market Collection Agent — core data engine",
      "Pub/Sub event streaming pipeline for real-time triggers",
      "BigQuery raw intelligence data landing zone and lineage"]),
    (MID, "Insight & Analysis Layer",
     ["ML trend detection models — Vertex AI, Pegasus-governed",
      "Ranking movement velocity & significance classification",
      "Competitor strategy pattern inference across the market",
      "Pricing gap & over-competitiveness scoring per segment",
      "Opportunity identification with commercial impact scoring",
      "Anomaly flagging with confidence and urgency scoring",
      "SHAP explainability for all ML model prediction outputs",
      "Pegasus continuous model quality evaluation & alerting",
      "BigQuery ML feature engineering & model training pipelines",
      "Gemini competitive context synthesis for briefing generation"]),
    (TEAL, "Recommendation Layer",
     ["Pricing action recommendations with simulation evidence",
      "Excess adjustment proposals with rationale and impact",
      "Optional cover optimisation suggestions with gap analysis",
      "Product feature gap priority alerts with competitor mapping",
      "Simulation-backed commercial impact quantification ranges",
      "Priority, urgency and risk classification per recommendation",
      "Gemini-generated human-readable recommendation rationale",
      "Cortex recommendation routing & governance control",
      "Model Armor output validation before governance handoff",
      "Policy Engine compliance screening of all recommendations"]),
    (PURPLE, "Governance Layer",
     ["Human approval routing via Pega workflow automation",
      "Tiered authority framework — material vs immaterial changes",
      "ENVOY Audit Framework — complete, immutable decision log",
      "FCA-compliant explainability outputs per recommendation",
      "Model Armor safety validation at governance entry point",
      "Recommendation modification and rejection tracking",
      "Rejection rationale capture for model feedback loop",
      "Compliance change record management and notifications",
      "RBAC & ABAC access enforcement across platform roles",
      "Governance SLA monitoring and breach alerting via Pega"]),
    (GREEN, "Execution Layer",
     ["AGGS — approved PCW rate submissions via Apigee APIs",
      "Duck Creek — policy & product configuration updates",
      "Pricing Services — rate band management and submission",
      "Product Services — optional cover configuration updates",
      "Apigee — API management, security and audit logging",
      "Execution confirmation logging in ENVOY Audit Framework",
      "Post-change monitoring initiation via ObserveAll triggers",
      "ObserveAll — PCW ranking and volume impact tracking",
      "Cloud Logging — execution records and error capture",
      "Learning Agent outcome data ingestion from ObserveAll"]),
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
        add_textbox(s, l10x + Inches(0.1), iy10 + Inches(0.08), l10w - Inches(0.15), item_h - Inches(0.1),
                    item10, font_size=9.5, color=TEXT)
        iy10 += item_h + Inches(0.03)
    l10x += l10w + l10gap


# ── Save ──────────────────────────────────────────────────────────────────────
prs.save("/home/user/rag/part1.pptx")
print("Part 1 saved")
