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
# SLIDE 11 — Multi-Agent Intelligence Architecture
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "AGENTIC ARCHITECTURE",
             "Multi-Agent Intelligence Architecture — ENVOY ADK Specialist Agent Network", 11)

# Orchestrator bar
add_rect(s, Inches(0.35), Inches(1.2), Inches(12.33), Inches(0.68), fill_rgb=NAVY)
add_rect(s, Inches(0.35), Inches(1.2), Inches(0.06), Inches(0.68), fill_rgb=GOLD)
add_textbox(s, Inches(0.5), Inches(1.25), Inches(2.2), Inches(0.25),
            "ORCHESTRATOR AGENT", font_size=8.5, bold=True, color=GOLD)
add_textbox(s, Inches(2.8), Inches(1.25), Inches(9.7), Inches(0.55),
            "Coordinates the end-to-end competitive intelligence workflow across all specialist agents, routing analysis tasks based on signal type, significance and urgency. Manages multi-step workflow execution state via the ENVOY Session Store, persisting context across long-running investigations. Handles agent failures with automatic retry and fallback logic. Aggregates specialist agent outputs into unified intelligence packages and escalates to the ENVOY governance layer and Pega workflow when human approval is required. Provides full workflow observability through ObserveAll and maintains complete execution audit trail in the ENVOY Audit Framework for every agent action taken.  |  Powered by: ENVOY ADK / Vertex AI Agent Engine / LangGraph / Cloud Workflows / Session Store",
            font_size=8.5, color=WHITE)

agent_cards = [
    (ACCENT,  "Market Collection Agent",
     "Autonomously and continuously collects PCW pricing, excess structure, product feature, optional cover and promotional offer data across all monitored competitors and channels, operating on a defined schedule supplemented by real-time event-triggered collection via Pub/Sub when upstream anomaly detection flags a potential market change. Validates data integrity using ML-based quality models registered in Pegasus, flagging anomalies and gaps for automated remediation or human review. Enriches raw PCW data with competitor metadata from the ENVOY Knowledge Graph and stores validated datasets in BigQuery with full data lineage. Adapts to PCW site structure changes through adaptive collection logic registered and versioned in the ENVOY Tool Registry.",
     ["Agentic", "ADK", "Pub/Sub", "BigQuery"]),
    (MID,    "Position Intelligence Agent",
     "Analyses PCW ranking data from the Market Collection Agent to identify and classify ranking movements by direction, velocity, magnitude and statistical significance, using time-series ML models trained on historical PCW ranking data and continuously evaluated through Pegasus. Detects both rapid, sharp ranking changes indicative of acute competitor pricing actions and gradual, sustained ranking drift patterns indicating structural competitive disadvantage building over time. Classifies ranking movements by probable driver — price change, product feature update, excess structure revision, PCW algorithm change or competitor promotional activity — to focus downstream analysis. Generates ranked-change alerts for significant movements and contributes structured ranking intelligence to the Orchestrator Agent.",
     ["ML", "Vertex AI", "BigQuery ML", "Pegasus"]),
    (TEAL,   "Competitor Analysis Agent",
     "Investigates market changes identified by the Position Intelligence Agent to determine root cause and strategic context, using RAG-based retrieval from the ENVOY competitor knowledge base in Vertex AI Vector Search combined with Gemini-powered synthesis of retrieved competitor data, product documentation and market intelligence. Cross-references pricing data, product feature changes, optional cover updates and promotional offer activity to construct a comprehensive picture of each competitor's current strategy and recent tactical adjustments. Produces structured competitive assessment reports with Gemini-generated narrative, key findings, strategic implications and recommended investigation priorities — stored in BigQuery and passed to the Pricing and Proposition Intelligence Agents for specialist analysis.",
     ["GenAI", "Gemini", "RAG", "Vector Search"]),
    (PURPLE, "Pricing Intelligence Agent",
     "Evaluates LBG's pricing competitiveness at granular segment, risk group and product line level against each monitored competitor on each active PCW channel, using ML pricing models on Vertex AI incorporating competitor pricing history, risk mix adjustments, PCW algorithm weighting factors and LBG's current pricing position. Identifies specific pricing gaps where LBG is uncompetitively priced for commercially significant risk segments, and over-competitiveness where margin is unnecessarily sacrificed without corresponding ranking benefit. Runs preliminary elasticity estimates to quantify the volume and revenue impact of closing identified pricing gaps, passing structured intelligence with quantified recommendations to the Simulation Agent for full commercial scenario modelling.",
     ["ML", "Vertex AI", "Pegasus", "BigQuery"]),
    (GOLD,   "Proposition Intelligence Agent",
     "Monitors competitor product feature sets, excess tier structures, optional cover inclusions, add-on package compositions and promotional offer terms across all PCWs, using Gemini to extract and structure proposition data from competitor documentation alongside ML-based feature scoring models that translate product attributes into PCW-relevant competitiveness scores. Identifies LBG proposition gaps — features or cover elements that competitors offer and LBG does not, or where LBG's excess structure or optional cover pricing creates a measurable PCW ranking disadvantage. Tracks cover innovation trends across the competitive set to provide advance warning of emerging proposition differentiators that could impact future PCW ranking if unaddressed.",
     ["GenAI", "Gemini", "ML", "Vector Search"]),
    (RED,    "Simulation Agent",
     "Runs comprehensive pricing elasticity, volume impact and margin simulation models on Vertex AI to quantify the expected commercial outcomes of each potential intervention identified by the Pricing and Proposition Intelligence Agents — including expected PCW ranking position change, associated quote volume uplift or reduction, margin impact and net revenue effect across defined time horizons. Generates multiple intervention scenarios at varying degrees of pricing or proposition change, with confidence intervals based on historical simulation accuracy stored in the ENVOY feature store. Produces structured scenario comparison reports passed to the Recommendation Agent as quantified evidence underpinning each recommendation to pricing teams.",
     ["ML", "Vertex AI", "BigQuery", "Simulation Models"]),
    (GREEN,  "Recommendation Agent",
     "Synthesises the structured intelligence outputs of all upstream specialist agents into a prioritised, actionable recommendation set using Gemini structured output generation — each recommendation comprising a clear action statement, Gemini-drafted human-readable rationale, supporting evidence references, confidence score, urgency classification (immediate / near-term / strategic), simulated commercial impact range and risk assessment. Screens recommendations through the ENVOY Policy Engine for business and regulatory compliance, applies Model Armor output validation, and formats outputs to Pega workflow schema for direct governance workflow ingestion. Routes recommendations through Cortex to the appropriate approval tier based on change type, magnitude and risk profile.",
     ["GenAI", "Gemini", "Cortex", "Policy Engine", "Model Armor"]),
    (RGBColor(0x08, 0x91, 0xB2), "Learning Agent",
     "Continuously tracks the outcomes of executed recommendations by ingesting post-change PCW performance data from ObserveAll and comparing observed ranking, volume and margin outcomes against pre-change baselines and simulation-predicted results — calculating recommendation accuracy scores and simulation calibration metrics fed back into the feature store. Identifies systematic patterns in recommendation over- or under-performance by type, competitor, PCW channel or market condition, generating structured model improvement reports for the data science team in Pegasus. Triggers automated retraining of ML models on Vertex AI when performance drift exceeds defined statistical thresholds, ensuring platform predictive accuracy compounds over time.",
     ["ML", "Pegasus", "Vertex AI", "ObserveAll"]),
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
                    body11, font_size=9, color=SUB)
        tx11 = ax11 + Inches(0.1)
        for tag11 in tags11:
            tw11 = Inches(len(tag11) * 0.075 + 0.2)
            add_rect(s, tx11, ry11 + a11h - Inches(0.32), tw11, Inches(0.22), fill_rgb=WARM)
            add_textbox(s, tx11 + Inches(0.04), ry11 + a11h - Inches(0.3),
                        tw11 - Inches(0.05), Inches(0.2),
                        tag11, font_size=8, bold=True, color=hc11)
            tx11 += tw11 + Inches(0.06)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 12 — Integration Architecture
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "SYSTEMS INTEGRATION",
             "Integration with Existing LBG Architecture — Capability Layer on Established Technology Estate", 12)

# Left section
add_textbox(s, Inches(0.5), Inches(1.15), Inches(7.0), Inches(0.3),
            "Existing Systems & ENVOY Integration Points", font_size=12, bold=True, color=NAVY)

sys_rows = [
    (MID,    "AGGS",
     "Quote aggregation and PCW rate submission gateway — the primary interface for submitting approved pricing changes to Price Comparison Websites at speed. ENVOY integrates via Apigee-managed REST APIs to submit rate updates, confirm submission status and retrieve PCW feedback data for the Learning Agent's post-change performance tracking. Existing AGGS integration patterns and security controls are reused in full.",
     "Existing"),
    (ACCENT, "Apigee",
     "LBG's enterprise API management platform providing security policy enforcement, rate limiting, request routing and complete audit logging for all integration traffic between the ENVOY platform and downstream core systems. All ENVOY-to-system API calls are mediated through Apigee — ensuring no direct system-to-system calls, consistent security policy enforcement and a comprehensive integration audit trail that supplements the ENVOY Audit Framework records.",
     "Existing"),
    (PURPLE, "Pega",
     "LBG's enterprise workflow and case management platform used for all governance approval routing, SLA management, authority delegation and decision record management within the competitive intelligence platform. Pega receives structured recommendations from the ENVOY Recommendation Agent via Apigee, manages the complete approval workflow lifecycle including modification and rejection handling, and writes approved decisions back to the ENVOY Audit Framework to complete the lineage chain.",
     "Existing"),
    (TEAL,   "Duck Creek",
     "Policy administration and rating engine platform used for product configuration updates and rating rule changes following human approval. ENVOY integrates via Apigee to submit approved product feature and excess structure changes, with execution confirmation returned to the ENVOY audit trail and ObserveAll post-change monitoring initiated automatically to track the market impact of executed product updates.",
     "Existing"),
    (GREEN,  "Pricing Services",
     "LBG's internal rate calculation and pricing band management service. ENVOY submits approved pricing band adjustments via Apigee-managed APIs following human approval through the Pega governance workflow, with real-time execution confirmation returned to Cloud Logging and the Learning Agent for immediate inclusion in post-change PCW performance tracking.",
     "Existing"),
    (RGBColor(0x08, 0x91, 0xB2), "Data Platform",
     "LBG's enterprise data platform providing BigQuery-based analytical storage, ML feature engineering pipelines and model training infrastructure for all ENVOY competitive intelligence workloads. ENVOY uses the Data Platform as the primary store for competitive intelligence data, ML training datasets, simulation results and recommendation outcome data — leveraging existing data governance, lineage and quality controls.",
     "Existing"),
    (GOLD,   "ENVOY Platform",
     "LBG's enterprise Agentic AI runtime providing agent hosting (Vertex AI Agent Engine), orchestration (ADK, LangGraph), shared services (Memory, Session, Tool, Agent, Prompt, Policy Registries), governance (Cortex, Model Armor, Policy Engine, Audit Framework) and full observability (ObserveAll integration, Dynatrace, Cloud Logging) for all PCW competitive intelligence AI workloads.",
     "New Capability"),
]
sy12 = Inches(1.5)
for sc12, sname, sdesc, stag in sys_rows:
    add_rect(s, Inches(0.5), sy12, Inches(7.2), Inches(0.52), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, Inches(0.5), sy12, Inches(0.05), Inches(0.52), fill_rgb=sc12)
    add_textbox(s, Inches(0.65), sy12 + Inches(0.05), Inches(1.1), Inches(0.22),
                sname, font_size=9, bold=True, color=TEXT)
    add_textbox(s, Inches(1.85), sy12 + Inches(0.05), Inches(5.1), Inches(0.42),
                sdesc, font_size=9, color=SUB)
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
            "Architecture Principle: The PCW Competitive Intelligence Platform is implemented as a governed capability layer on top of LBG's existing and approved technology estate. All data flows are mediated through Apigee. All human decisions are managed through Pega. All AI model calls are routed through Cortex. All agent outputs are validated through Model Armor. No new core systems are introduced and no duplication of existing capability is created — the platform adds intelligence and automation on top of the foundation that already exists.",
            font_size=9.5, color=WHITE)

# Right section
rx12 = Inches(7.9)
add_textbox(s, rx12, Inches(1.15), Inches(4.7), Inches(0.3),
            "End-to-End Data & Decision Flow", font_size=12, bold=True, color=NAVY)

flow_nodes = [
    (ACCENT,  "PCWs — Real-Time Market Data Source"),
    (MID,     "ENVOY ADK — Specialist Intelligence Agent Network"),
    (TEAL,    "LBG Data Platform — BigQuery Feature Store & ML Registry"),
    (SUB,     "Apigee — API Management, Security & Audit Gateway"),
    (GREEN,   "AGGS / Duck Creek / Pricing Services — Execution Systems"),
    (PURPLE,  "Pega — Governance Workflow & Human Approval Layer"),
    (NAVY,    "Business Users — Review, Approve, Monitor & Override"),
]
fy12 = Inches(1.5)
for i12, (fnc, fnt) in enumerate(flow_nodes):
    add_rect(s, rx12, fy12, Inches(4.7), Inches(0.44), fill_rgb=fnc)
    add_textbox(s, rx12 + Inches(0.1), fy12 + Inches(0.08), Inches(4.5), Inches(0.3),
                fnt, font_size=10.5, bold=True, color=WHITE)
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
    (GREEN,  "AUTO",
     "Market Monitoring & Data Collection",
     "Fully automated operation in steady state. ENVOY ADK Market Collection Agents continuously collect, validate and store PCW market data under ENVOY orchestration without human intervention. ML anomaly detection models on Vertex AI analyse the data stream in real time, flagging material market movements exceeding significance thresholds for automated escalation to the analysis stage. Data quality failures, collection anomalies and SLA breaches trigger automated alerts via ObserveAll and escalate to the data operations team only when automated self-healing is unsuccessful. Target data freshness: under 15 minutes from competitor change to platform awareness.",
     "ENVOY ADK\nPub/Sub\nCloud Workflows\nVertex AI Anomaly Detection\nObserveAll",
     "Fully Automated", GREEN),
    (MID,    "ANALYSE",
     "Intelligence Generation & Market Insight",
     "AI-driven analysis executed by specialist ENVOY agents without human intervention. ML models on Vertex AI, governed through Pegasus, classify market signals and detect competitive patterns. The Competitor Analysis Agent uses Gemini RAG to synthesise intelligence from retrieved knowledge. Pricing and Proposition Intelligence Agents quantify competitive gaps and opportunities. All agent outputs are automatically quality-screened by the ENVOY Evaluation Framework — groundedness scoring, hallucination detection and confidence assessment via Pegasus — before being passed to the Recommendation Agent. Outputs failing quality thresholds are flagged for data science review rather than being automatically escalated.",
     "Vertex AI\nGemini\nPegasus Eval\nENVOY Evaluation Framework\nBigQuery",
     "AI-Driven", MID),
    (GOLD,   "RECOMMEND",
     "Recommendation Review & Human Judgement",
     "Human review is mandatory at this stage without exception. The Recommendation Agent delivers structured, prioritised recommendations to pricing and proposition teams through Pega, with each recommendation accompanied by Gemini-generated rationale, simulation-validated commercial impact, confidence score and full supporting evidence. Analysts review recommendations in the context of their professional knowledge of the pricing environment, business strategy and regulatory obligations — and may approve, modify with documented rationale, or reject. All decisions, including specific reasoning for modifications and rejections, are captured in the ENVOY Audit Framework. Target SLA: same-day review for urgent recommendations, 48 hours for standard recommendations.",
     "Gemini\nCortex\nPega Workflow\nENVOY Audit Framework\nModel Armor",
     "Human Required", GOLD),
    (PURPLE, "APPROVE",
     "Governance Approval & Senior Sign-Off",
     "Senior governance approval is required for material pricing or proposition changes, as defined by a delegated authority framework configured in Pega that automatically routes recommendations based on change type, financial magnitude, regulatory risk and product line classification. The Compliance team is automatically notified for changes above defined thresholds or touching regulated pricing dimensions. The complete recommendation package, analyst review notes and full decision lineage are presented to the approver within Pega — no requirement to access separate systems. All approvals, modifications and escalations are permanently recorded in the ENVOY Audit Framework and are accessible for FCA regulatory review within defined SLA timescales.",
     "Pega Governance Workflow\nENVOY Audit Framework\nRBAC & ABAC\nCompliance Notification",
     "Governed", PURPLE),
    (RED,    "EXECUTE & LEARN",
     "Execution, Monitoring & Closed-Loop Learning",
     "Following governance approval, ENVOY automatically executes approved changes via Apigee-managed APIs to AGGS, Duck Creek and Pricing Services, with execution confirmation logged in Cloud Logging and the ENVOY Audit Framework completing the decision-to-execution lineage chain. ObserveAll immediately initiates post-change PCW performance monitoring, tracking ranking position, quote volume and conversion metrics against pre-change baselines and simulation-predicted outcomes. The ENVOY Learning Agent ingests outcome data, calculates recommendation accuracy scores, updates the ML feature store in BigQuery and surfaces model performance trends in Pegasus — triggering automated model retraining on Vertex AI when performance drift is detected.",
     "Apigee / AGGS\nDuck Creek\nObserveAll\nPegasus\nVertex AI\nLearning Agent",
     "Closed-Loop", RED),
]

t13y = Inches(1.2)
t13h = Inches(1.0)
t13gap = Inches(0.08)
for (bc13, badge13, title13, desc13, envoy13, auto13, ac13) in tiers:
    add_rect(s, Inches(0.5), t13y, Inches(12.33), t13h, fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, Inches(0.5), t13y, Inches(1.0), t13h, fill_rgb=bc13)
    add_textbox(s, Inches(0.5), t13y + Inches(0.35), Inches(1.0), Inches(0.3),
                badge13, font_size=8, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(s, Inches(1.6), t13y + Inches(0.06), Inches(7.5), Inches(0.28),
                title13, font_size=10, bold=True, color=NAVY)
    add_textbox(s, Inches(1.6), t13y + Inches(0.34), Inches(7.5), Inches(0.6),
                desc13, font_size=9, color=SUB)
    add_textbox(s, Inches(9.2), t13y + Inches(0.08), Inches(2.0), Inches(0.85),
                envoy13, font_size=8, color=ACCENT)
    add_rect(s, Inches(11.3), t13y + Inches(0.3), Inches(1.3), Inches(0.3), fill_rgb=ac13)
    add_textbox(s, Inches(11.3), t13y + Inches(0.32), Inches(1.3), Inches(0.26),
                auto13, font_size=8, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    t13y += t13h + t13gap

# Principle bar
add_rect(s, Inches(0.5), Inches(6.3), Inches(12.33), Inches(0.55), fill_rgb=NAVY)
add_textbox(s, Inches(0.7), Inches(6.38), Inches(12.0), Inches(0.4),
            "The platform RECOMMENDS via Gemini and ENVOY agents.   People DECIDE and APPROVE via Pega.   "
            "Systems EXECUTE via Apigee.   ENVOY LEARNS continuously via Pegasus.   Every step governed, observable and auditable.",
            font_size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 14 — Governance & Risk Framework
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "RISK & COMPLIANCE",
             "Governance & Risk Framework — FCA-Aligned, Auditable and Explainable by Design", 14)

risk_cards = [
    (MID,    "FCA Alignment & Consumer Duty",
     "The platform is designed to meet LBG's obligations under the FCA Consumer Duty and General Insurance pricing rules, maintaining human accountability for all pricing decisions and providing full explainability for every AI-assisted recommendation presented to pricing teams. All pricing and proposition decisions remain with FCA-authorised individuals — ENVOY provides structured decision support with quantified evidence, not autonomous pricing. Gemini-generated recommendation rationale is reviewed by Compliance during the establishment phase and periodically thereafter for fair value consistency. Cortex routing ensures no model calls occur outside the governed platform perimeter. All AI outputs are screened through Model Armor before presentation to decision-makers. The ENVOY Audit Framework provides a complete, immutable record of every AI recommendation and human decision, formatted for FCA regulatory review within agreed SLA timescales."),
    (GREEN,  "Auditability & Decision Lineage",
     "The ENVOY Audit Framework maintains a complete, chronologically ordered, immutable audit record of the entire competitive intelligence and recommendation workflow — from initial PCW data collection through ML analysis, Gemini synthesis, recommendation generation, human review, governance approval and execution outcome — with every step timestamped, attributed to the responsible agent or user identity, and linked by a unique recommendation lineage ID. Every modification made by a human reviewer — the specific change made to an AI-generated recommendation and the documented rationale for that change — is permanently recorded alongside the original AI output, providing a complete picture of AI-human interaction in the decision process. Audit records are stored in immutable Cloud Storage with defined retention periods and are accessible for FCA regulatory review, internal audit and model governance review within agreed SLA timescales."),
    (GOLD,   "Explainability & Transparency",
     "Every recommendation delivered by the ENVOY platform is accompanied by a Gemini-generated human-readable rationale explaining in plain language why the recommendation is being made, what competitive evidence supports it, what the simulated commercial impact is expected to be and what confidence level has been assigned by the underlying ML models. ML model outputs include SHAP-based feature importance scores produced by Pegasus, allowing pricing teams to understand which competitive factors are driving each model prediction and to challenge the model's reasoning before approving a recommendation. Model cards are maintained for all production ML and GenAI models, documenting training data, evaluation performance, known limitations and appropriate use constraints. Gemini outputs include explicit references to the source data used in synthesis, enabling analysts to verify the factual basis of intelligence briefings before making approval decisions."),
    (ACCENT, "Data Protection & Privacy",
     "The PCW competitive intelligence platform processes exclusively competitor market data and LBG internal pricing and product data — no customer PII is collected, stored or processed at any stage of the competitive intelligence workflow. DLP policies enforced through GCP Data Loss Prevention and Model Armor automatically detect and redact any PII that might inadvertently appear in competitor data sources before entering the ENVOY pipeline. Role-based access controls managed through IAM and RBAC restrict access to competitive intelligence data, models and recommendation outputs to authorised individuals, with access review conducted quarterly. UK data residency is maintained through VPC Service Controls. Data minimisation principles are applied throughout — only data necessary for the competitive intelligence purpose is collected, retained for the minimum necessary period and deleted according to GDPR-aligned retention schedules."),
    (PURPLE, "Model Governance (Pegasus)",
     "All ML and GenAI models used in the platform are subject to LBG's model governance policy, enforced through Pegasus. Pre-deployment validation requires each model meets defined accuracy, groundedness, fairness and stability criteria before production promotion, with mandatory champion/challenger testing demonstrating improvement over replaced model versions. Post-deployment monitoring tracks model performance, input data distribution and output quality on a continuous basis, with automated alerts for threshold breaches. Model drift — detected through statistical tests on input feature and output prediction distributions — automatically triggers a retraining workflow on Vertex AI. Model cards are maintained for every production model documenting training data provenance, evaluation results, known limitations, risk classification and approved use cases, with external model risk review required for models classified as high-risk."),
    (RED,    "Operational Resilience & Recovery",
     "The platform is architected for graceful degradation — if the ENVOY intelligence layer becomes unavailable, core pricing operations continue unaffected through existing AGGS, Duck Creek and Pricing Services systems, with the competitive intelligence capability temporarily reduced to manual monitoring rather than core operations being disrupted. Recovery time and recovery point objectives are defined for each platform component based on business criticality, with the recommendation delivery and governance workflow components classified highest priority for recovery. Manual fallback procedures — including manual monitoring checklists, analyst escalation paths and direct Pega workflow initiation without AI input — are documented, tested quarterly and maintained by the platform operations team. Chaos engineering tests are conducted in pre-production before each major release to validate resilience under component failure conditions."),
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
                rb14, font_size=9, color=SUB)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 15 — KPI & Measurement Framework
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "MEASUREMENT FRAMEWORK",
             "KPI & Measurement Framework — Four Dimensions of Platform Performance", 15)

kpi_cols = [
    (ACCENT, "Commercial KPIs",
     ["PCW ranking position by channel, brand and product line — primary measure of competitive market positioning, tracked daily across all monitored PCWs with trend analysis and target-setting reviewed by senior leadership on a monthly basis",
      "Quote conversion rate for PCW-sourced new business — measures the proportion of PCW quotes converting to bound policies, providing a direct, commercially meaningful measure of competitive positioning effectiveness",
      "New business volume via PCW channel — tracks the number of new policies written through PCW channels, providing a direct measure of top-line growth impact attributable to competitive positioning improvements from platform recommendations",
      "Revenue per PCW quote (risk-adjusted) — measures the quality of PCW-sourced new business, ensuring ranking improvements are achieved through genuinely competitive pricing rather than unsustainably discounted rates that sacrifice long-term profitability",
      "Competitive win rate versus key monitored competitors — tracks the proportion of shared risk segments where LBG achieves a superior PCW ranking position to each named competitor, providing a relative competitive measure",
      "Market share by PCW where measurable — tracks LBG's estimated share of PCW-sourced GI new business to provide a strategic long-term indicator of competitive positioning trajectory across the UK market"]),
    (MID, "Operational KPIs",
     ["Market data freshness (minutes from competitor change to platform awareness) — primary operational SLA targeting under 15 minutes in steady state, monitored continuously by ObserveAll with automated alerting on SLA breach events",
      "Signal to insight latency (time from data collection to intelligence briefing generation) — targeting under 30 minutes for material market signals, measured end-to-end by ENVOY workflow timestamps and reported weekly",
      "Insight to recommendation delivery (time from intelligence generation to Pega workflow initiation) — targeting under 2 hours for urgent recommendations, with Gemini synthesis time tracked separately as a component metric",
      "Recommendation to decision turnaround (time from Pega workflow initiation to human approval or rejection) — targeting same-day for urgent and 48 hours for standard, with SLA compliance tracked and reported via Pega dashboards",
      "FTE hours saved on monitoring and analysis per week versus pre-platform baseline — measures the operational efficiency gain from intelligent automation and is reported monthly as part of the platform business case tracking",
      "ENVOY agent uptime and SLA compliance (%) — measures the reliability and availability of the ENVOY ADK agent network in production, with a target of 99.5% availability and monthly availability reports generated from ObserveAll"]),
    (TEAL, "Strategic KPIs",
     ["PCW channel coverage breadth (% of commercially material PCW channels monitored continuously) — tracks the platform's coverage expansion toward the target of 100% of active PCW channels, reported monthly with a channel-by-channel coverage map",
      "Recommendation adoption rate (% of AI recommendations approved without material modification) — measures the degree of pricing team trust in and reliance on AI-generated recommendations, expected to grow as platform track record and explainability build",
      "Recommendation accuracy score (% of adopted recommendations achieving predicted ranking or volume outcome within defined tolerance bands) — measures real-world predictive accuracy and is the primary measure of simulation model quality",
      "Intelligence latency advantage versus estimated competitor benchmark — tracks LBG's estimated speed-to-insight relative to key competitor PCW intelligence processes as a strategic indicator of competitive monitoring advantage",
      "Platform reuse across GI product lines (number of GI products and channels benefiting from ENVOY platform capability) — measures progress toward the strategic objective of a shared, reusable competitive intelligence platform across BCB GI",
      "Pegasus model quality scores trend — tracks the composite model quality score across all production ML and GenAI models as an indicator of the long-term trajectory of platform intelligence quality and recommendation reliability"]),
    (RED, "Risk & Model KPIs",
     ["Audit compliance rate (% of recommendations with complete ENVOY Audit Framework records) — must maintain 100% compliance as a non-negotiable regulatory requirement, with any breach triggering an immediate investigation and remediation process",
      "Pegasus model performance versus pre-deployment baseline (% of models meeting or exceeding performance benchmarks monthly) — primary measure of production model quality degradation, with automatic retraining triggered on breach",
      "BigQuery data quality score (% of competitive intelligence records meeting completeness, accuracy and timeliness quality standards) — tracks the integrity of the intelligence foundation underpinning all AI model outputs and recommendations",
      "Pega governance SLA compliance (% of recommendations processed within defined approval timescales) — measures the efficiency and reliability of the human governance layer, with SLA breaches reported to the delivery governance forum",
      "Model drift incidents (number of instances where automated drift detection triggers retraining) — all drift events are managed events; any unmanaged drift reaching production triggers a formal model incident review",
      "FCA review findings (number of adverse findings from FCA or internal audit review of AI-assisted pricing process) — target zero adverse findings, with any finding triggering a formal remediation process and root cause analysis"]),
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
             "Phased Delivery Roadmap — Four Waves to Full Competitive Optimisation Capability", 16)

waves = [
    (ACCENT, "Wave 1", "Market Visibility", "Months 1–3",
     ["ENVOY platform onboarding and GCP infrastructure provisioning with central platform team support",
      "ENVOY ADK Market Collection Agent development and deployment for 2 pilot PCW channels",
      "Competitor baseline dataset construction in BigQuery including data quality framework and lineage",
      "Initial ML anomaly detection model trained on baseline data and deployed on Vertex AI via Pegasus",
      "Executive monitoring dashboard delivering real-time PCW ranking and competitor activity view",
      "Apigee integration patterns established for AGGS and LBG Data Platform connections",
      "ENVOY Audit Framework and RBAC policies configured for platform from Day 1",
      "ObserveAll observability dashboard configured for agent telemetry and data quality monitoring"]),
    (MID, "Wave 2", "Intelligence & Analysis", "Months 4–6",
     ["ML trend detection and ranking classification models deployed on Vertex AI with Pegasus evaluation",
      "Competitor Analysis Agent developed — Gemini RAG pipeline with Vertex AI Vector Search live",
      "Gemini-powered intelligence briefing generation — automated executive summaries to pricing teams",
      "Opportunity identification scoring engine — ML-based commercial prioritisation of market signals",
      "Full PCW channel coverage expansion to all commercially material PCW channels and brands",
      "Pegasus evaluation live for all production ML models and Gemini outputs — quality gates active",
      "ENVOY agent observability in ObserveAll — full agent telemetry, cost and performance dashboards",
      "Stakeholder feedback cycle — pricing team review and iteration of intelligence quality and format"]),
    (TEAL, "Wave 3", "Decision Support", "Months 7–9",
     ["Gemini Recommendation Agent — structured, Pega-formatted recommendation delivery to pricing teams",
      "Simulation Agent — Vertex AI pricing elasticity and volume modelling for all recommendations",
      "Pega governance workflow integration — tiered approval, SLA management and decision audit logging",
      "AGGS and Duck Creek integration via Apigee — automated execution of approved pricing changes",
      "Cortex model routing and Model Armor guardrails configured and validated for production",
      "Delegated authority framework configured in Pega — material and immaterial change routing logic",
      "ENVOY Audit Framework compliance check — FCA and internal audit readiness formally validated",
      "Change management programme — pricing team capability building, training and process adoption"]),
    (PURPLE, "Wave 4", "Optimisation & Scale", "Months 10–12",
     ["ENVOY Learning Agent — closed-loop outcome measurement and Pegasus model recalibration live",
      "Pegasus retraining automation — drift-triggered model retraining pipelines on Vertex AI active",
      "Proposition Intelligence Agent — Gemini-powered full product and cover competitive monitoring",
      "Full multi-agent A2A orchestration — Orchestrator Agent coordinating all specialist agents via ADK",
      "Advanced simulation capability — full proposition and pricing scenario comparison and ranking",
      "Platform extensibility framework — architecture documented and registered for BCB GI reuse",
      "Performance benchmarking — platform KPIs versus pre-launch baseline, formal ROI measurement",
      "Scale and operate model — BAU support model, platform team structure and governance cadence"]),
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
             "Business Value Summary — Four Dimensions of Sustainable Competitive Advantage", 17)

value_cards = [
    (ACCENT, "Faster Market Response",
     "The ENVOY-powered platform reduces competitor response time from multiple days under the current manual process to under two hours from competitor market change to governed recommendation delivery — fundamentally transforming LBG's competitive posture from reactive to proactive on Price Comparison Websites. ENVOY ADK agents provide continuous PCW monitoring with sub-15-minute data freshness, eliminating the monitoring blindspots that currently allow competitor pricing and proposition changes to go undetected for days. Event-driven analysis via Pub/Sub triggers immediate multi-agent investigation when ML anomaly detection flags a material market movement, ensuring significant competitor actions receive a rapid, evidence-based response rather than being discovered in the next scheduled review. The compounding effect of sustained responsiveness improvement is a structural shift in LBG's competitive position — reducing the duration and frequency of sub-optimal PCW ranking periods and protecting new business volumes during competitor campaign periods."),
    (TEAL, "Better Commercial Outcomes",
     "Gemini-powered recommendations supported by Vertex AI simulation quantify the expected commercial impact of each proposed intervention — in PCW ranking change, quote volume delta and margin movement — before execution, enabling pricing teams to make better-informed decisions with greater confidence and lower risk of commercially suboptimal outcomes. ML elasticity models trained on LBG's historical PCW performance data provide increasingly accurate intervention impact estimates that improve over time as the ENVOY Learning Agent ingests post-execution outcome data and recalibrates model parameters through Pegasus. The closed-loop learning architecture ensures recommendation quality compounds continuously — each recommendation outcome enriches the feature store and improves the next round of model predictions and simulation accuracy. Evidence-based, simulation-validated recommendations replace analyst judgement under uncertainty, reducing the risk of interventions that achieve ranking improvement at the cost of unacceptable margin sacrifice."),
    (GOLD, "Operational Efficiency",
     "ENVOY agents automate the end-to-end data collection, validation, analysis, synthesis and recommendation drafting workflow — releasing pricing, product and proposition team capacity for higher-value strategic and judgement-intensive work that was previously crowded out by manual monitoring effort. The Pega governance workflow eliminates manual coordination overhead between pricing, product, operations and technology teams, replacing ad hoc email-and-meeting coordination with a structured, SLA-managed, auditable process that is faster, more reliable and fully transparent. ObserveAll proactive alerting and ENVOY agent self-monitoring reduce reactive investigation effort by surfacing performance issues before they impact business outcomes. The scalable ENVOY agent architecture means expanding monitoring coverage to additional PCW channels, competitor sets and product lines requires agent configuration and data pipeline extension rather than proportional headcount increases."),
    (PURPLE, "Reusable Strategic Platform",
     "The PCW Competitive Intelligence Platform is built on ENVOY's enterprise-grade Agentic AI infrastructure — designed from the outset for extensibility beyond the initial PCW use case as the foundation for a broader BCB competitive and market intelligence capability across General Insurance and other LBG business lines. Every component — ENVOY ADK agent patterns, Gemini prompt templates in the Prompt Registry, ML model architectures and Pegasus evaluation frameworks, Pega governance workflow designs, Apigee integration patterns and ENVOY Audit Framework configurations — is documented, versioned and registered in ENVOY shared services, available for reuse at materially lower incremental cost and delivery time. The investment in ENVOY platform onboarding, GCP infrastructure, Pegasus model governance and Apigee integration patterns made in Wave 1 benefits every subsequent use case, creating a compounding return on platform investment that significantly improves the economics of AI capability delivery across LBG General Insurance."),
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
                vb17, font_size=9, color=SUB)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 18 — Risk Register & Assumptions
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "RISK MANAGEMENT",
             "Key Risks, Assumptions & Mitigations", 18)

add_textbox(s, Inches(0.5), Inches(1.15), Inches(4), Inches(0.28),
            "Risk Register", font_size=12, bold=True, color=NAVY)

risk_rows = [
    (RED,   "PCW data quality, availability and collection reliability fall below the threshold required for near-real-time competitive monitoring at the data freshness and completeness levels needed for ML model accuracy and recommendation reliability",
     "Medium", "High",
     "ML-based data quality validation layer in BigQuery with automated quality scoring and ObserveAll alerting. Data quality KPIs tracked in Pegasus and reported weekly. Vendor SLA assessment and contractual protections for commercial data sources. Manual fallback monitoring procedures documented and tested quarterly. Alternative data source identification for high-criticality PCW channels where single-source dependency risk is unacceptable."),
    (RED,   "ML and GenAI model accuracy and recommendation quality fall below acceptance thresholds required to generate business confidence in AI-assisted pricing decisions, reducing adoption and limiting commercial impact against the business case",
     "Medium", "High",
     "Pegasus champion/challenger evaluation framework mandated before any model promoted to production, with clear accuracy and groundedness threshold acceptance criteria agreed with pricing stakeholders at each wave gate. Phased rollout with extensive human validation of early recommendations before reducing review intensity. Gemini hallucination detection and groundedness scoring applied to all recommendation rationale outputs via the Evaluation Framework."),
    (GOLD,  "Pricing and proposition team adoption of AI-assisted workflows is slower than anticipated due to distrust of AI outputs, insufficient explainability or inadequate change management support during the transition from manual processes",
     "Medium", "Medium",
     "Pricing team co-design engagement from Wave 1, ensuring recommendation format and evidence package reflect what pricing professionals need to make confident approval decisions. Explainable AI outputs — SHAP scores, Gemini rationale, simulation evidence, source references — designed to build rather than undermine human expertise. Structured change management programme with team-level champions, training and regular feedback collection throughout all waves."),
    (GOLD,  "FCA scrutiny of AI-assisted pricing recommendation processes intensifies, requiring material changes to the governance framework, explainability standards or human accountability model during delivery",
     "Low", "High",
     "Human accountability for all pricing decisions is non-negotiable and built into every layer of the platform design — AI assists, humans decide, every time. Full explainability and audit trail maintained by design from Day 1, exceeding current regulatory expectations. Legal & Compliance review conducted at each wave gate before production launch. FCA engagement planned to brief on platform approach before public launch. Model governance documentation prepared to regulatory review standard from the outset."),
    (GREEN, "ENVOY platform onboarding complexity, ADK agent development effort or GCP infrastructure provisioning timelines exceed initial estimates, causing Wave 1 delivery delays that cascade through the phased roadmap",
     "Low", "Medium",
     "ENVOY onboarding model agreed with the central platform team before delivery commencement, with dedicated platform team support embedded in the delivery team. ADK agent development approach validated through a Wave 1 technical spike in Month 1. Existing GCP and ENVOY expertise reused through the embedded platform team. Apigee integration complexity de-risked through an integration spike in Month 1. Delivery timeline includes defined contingency at each wave gate for technical risk resolution."),
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
                rmit18, font_size=9.0, color=SUB)
    r18y += rh18 + Inches(0.06)

# Key Assumptions
add_textbox(s, Inches(8.3), Inches(1.15), Inches(4.0), Inches(0.28),
            "Key Assumptions", font_size=12, bold=True, color=NAVY)

assumptions = [
    "Google Cloud Platform and the ENVOY Agentic AI Platform are confirmed as the approved strategic infrastructure for this use case, with platform team support capacity and ENVOY onboarding commitment confirmed prior to Wave 1 commencement",
    "Cortex is the agreed strategic AI control plane for LBG, through which all model routing for the competitive intelligence platform will be governed — no direct model calls outside of the Cortex perimeter are permitted at any stage",
    "Human-in-the-Loop is retained as a firm design principle for all recommendation approval — the platform will never autonomously execute a pricing or proposition change without an authorised human reviewer approving in Pega",
    "PCW market data is available at sufficient quality, frequency and granularity to support near-real-time competitive monitoring at sub-15-minute data freshness for all commercially material PCW channels and product lines",
    "Pricing and proposition team stakeholders have confirmed capacity and willingness to engage in co-design during Wave 1 and to participate in the recommendation review and approval process from Wave 3 onwards",
]
ay18 = Inches(1.5)
for asm in assumptions:
    add_rect(s, Inches(8.3), ay18, Inches(4.4), Inches(0.72), fill_rgb=WARM, line_rgb=BORDER, line_pt=0.3)
    add_rect(s, Inches(8.3), ay18, Inches(0.05), Inches(0.72), fill_rgb=MID)
    add_textbox(s, Inches(8.42), ay18 + Inches(0.07), Inches(4.2), Inches(0.62),
                asm, font_size=9, color=TEXT)
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
            "Proceed with a focused Minimum Viable Platform targeting a single, high-volume PCW channel and a defined set of Motor and Home pricing and proposition use cases — building on LBG's ENVOY Agentic Platform and Google Cloud infrastructure and reusing all existing approved system integrations. The MVP will validate the complete end-to-end workflow: from automated PCW data collection through ENVOY ADK multi-agent intelligence generation, Gemini-powered recommendation synthesis and Pega-governed human approval, to Apigee-executed change delivery and ObserveAll-monitored outcome measurement — establishing proof of commercial impact, operational reliability, model quality and regulatory compliance before scaling investment across all PCW channels and GI product lines.",
            font_size=11, color=WHITE)

add_textbox(s, Inches(0.5), Inches(2.15), Inches(5), Inches(0.25),
            "IMMEDIATE NEXT STEPS", font_size=8, bold=True, color=MUTED)

next_steps = [
    "Confirm executive sponsorship, Wave 1 investment approval and formal ENVOY platform onboarding agreement with the central ENVOY team and Google Cloud account management",
    "Establish a cross-functional delivery team spanning Pricing, Product Management, Technology, Data Science, Risk, Compliance and the ENVOY platform team with clearly defined roles, governance and decision rights",
    "Conduct a co-design workshop with the pricing team to select the pilot PCW channel, define the MVP recommendation use cases and agree the Pega governance workflow design and delegated authority framework",
    "Execute a technical spike to assess PCW data availability and quality, validate the ENVOY ADK integration approach and establish the BigQuery data pipeline and Apigee integration patterns with core systems",
    "Define the platform success criteria, establish pre-launch KPI baselines across all four measurement dimensions and configure the Pegasus model evaluation and ObserveAll observability frameworks before Wave 1 begins",
    "Commence Wave 1 delivery: ENVOY platform provisioning on GCP, Market Collection Agent development for pilot PCW, BigQuery competitive intelligence data model and executive monitoring dashboard",
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
                ns, font_size=10, color=WHITE)

add_textbox(s, Inches(0.5), Inches(4.7), Inches(6), Inches(0.25),
            "ENVOY PLATFORM COMMITMENTS", font_size=8, bold=True, color=GOLD)

commitments = [
    (ACCENT,  "Governance: 100% of AI recommendations governed and routed through Cortex, screened by Model Armor and reviewed by authorised human decision-makers via Pega before any market change is executed — without exception, at every stage of the recommendation lifecycle"),
    (TEAL,    "Observability: Full agent execution traceability through ObserveAll and Dynatrace, complete decision audit trail in the ENVOY Audit Framework and real-time platform SLA monitoring from Day 1 of production operations — not added later, built in from the start"),
    (PURPLE,  "Reusability: All ENVOY agent patterns, Gemini prompt templates, ML model architectures, Pega workflow designs and Apigee integration patterns are registered in ENVOY shared services and documented for reuse across BCB General Insurance use cases at materially reduced incremental delivery cost"),
]
cx19 = Inches(0.5)
for cc19, ct19 in commitments:
    add_rect(s, cx19, Inches(5.0), Inches(4.0), Inches(0.82), fill_rgb=DKNAVY)
    add_rect(s, cx19, Inches(5.0), Inches(4.0), Inches(0.05), fill_rgb=cc19)
    add_textbox(s, cx19 + Inches(0.1), Inches(5.1), Inches(3.8), Inches(0.65),
                ct19, font_size=9.5, color=WHITE)
    cx19 += Inches(4.12)

add_textbox(s, Inches(0.5), Inches(6.0), Inches(12.33), Inches(0.42),
            "Transforming competitor monitoring into continuous, governed competitive intelligence and optimisation — powered by ENVOY, Gemini, Vertex AI and ML, with human oversight at every decision point.",
            font_size=12, italic=True, color=MUTED, align=PP_ALIGN.CENTER)

add_textbox(s, W - Inches(1.1), H - Inches(0.35), Inches(1.0), Inches(0.25),
            "19 / 20", font_size=8, color=MUTED, align=PP_ALIGN.RIGHT)


# ════════════════════════════════════════════════════════════════════════════════
# SLIDE 20 — Appendix: ENVOY Technical Reference
# ════════════════════════════════════════════════════════════════════════════════
s = prs.slides.add_slide(blank_layout)
slide_chrome(s, "APPENDIX",
             "ENVOY Technical Reference — Platform Components & PCW CI Capability Mapping", 20)

# Section A — ENVOY Component Mapping
add_textbox(s, Inches(0.5), Inches(1.15), Inches(4.0), Inches(0.28),
            "ENVOY Component to PCW CI Use Case Mapping", font_size=11, bold=True, color=NAVY)

comp_rows = [
    ("Vertex AI Agent Engine",
     "Hosts and manages all ENVOY ADK PCW intelligence agents — Market Collection, Position Intelligence, Competitor Analysis, Pricing Intelligence, Proposition Intelligence, Simulation, Recommendation and Learning agents — providing fully managed agent execution and scaling"),
    ("ADK (Agent Developer Kit)",
     "Framework used to develop, configure, deploy and lifecycle-manage all eight PCW specialist agents and the Orchestrator Agent — providing tool use capabilities, memory management, A2A communication and Pega escalation integration"),
    ("LangGraph",
     "Stateful multi-agent workflow orchestration for complex, multi-step competitor investigation and recommendation generation workflows that span multiple specialist agents across extended time horizons"),
    ("Gemini Pro / Flash",
     "Powers competitor analysis synthesis, recommendation rationale generation, executive intelligence briefing production, market commentary, regulatory impact assessment and FCA-compliant explanation generation"),
    ("Cortex (Control Plane)",
     "Routes all Gemini and ML model calls through centralised governance enforcement — no PCW CI model call occurs outside the Cortex perimeter, ensuring complete control and policy compliance for every AI interaction"),
    ("Pegasus (LBG Evaluation)",
     "Evaluates all PCW CI ML models (ranking prediction, elasticity, anomaly detection) and Gemini outputs (groundedness, faithfulness, hallucination) on a continuous basis with automated quality gates and drift-triggered retraining"),
    ("Model Armor",
     "Provides prompt injection attack protection and unsafe or policy-violating output filtering for all Gemini calls in the PCW CI recommendation workflow — the safety layer between models and business outputs"),
    ("Vertex AI Vector Search",
     "Powers RAG retrieval for the Competitor Analysis Agent — semantic search over the ENVOY competitor intelligence knowledge base to retrieve relevant product documentation, pricing history and market intelligence"),
    ("BigQuery",
     "Primary store for PCW competitive intelligence data, ML feature engineering pipelines, simulation results, recommendation history and Learning Agent outcome data — the analytical backbone of the platform"),
    ("Pub/Sub",
     "Event streaming backbone delivering real-time market change events to trigger ENVOY agent workflows immediately when ML anomaly detection identifies material competitor movements requiring urgent investigation"),
    ("Cloud Workflows",
     "Orchestrates long-running PCW intelligence workflows including multi-agent investigation sequences, simulation batch runs and governance escalation processes that persist across extended execution windows"),
    ("Apigee",
     "Mediates all ENVOY-to-core-system API calls (AGGS, Duck Creek, Pricing Services) with security policy enforcement, rate limiting and full audit logging that supplements the ENVOY Audit Framework records"),
    ("Pega",
     "Manages the human recommendation review and approval workflow, delegated authority routing, SLA enforcement and governance decision records — the human governance layer for every AI-generated recommendation"),
    ("ObserveAll (LBG)",
     "Provides integrated ENVOY agent telemetry, post-execution PCW performance tracking, business KPI monitoring and proactive alerting for the competitive intelligence platform across all production workloads"),
    ("ENVOY Audit Framework",
     "Maintains the complete, immutable, chronological audit trail of every agent action, AI recommendation and human approval decision — the FCA compliance and model governance record for the entire platform"),
]
cy20 = Inches(1.48)
for comp, usage in comp_rows:
    add_rect(s, Inches(0.5), cy20, Inches(4.1), Inches(0.34), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.25)
    add_textbox(s, Inches(0.55), cy20 + Inches(0.05), Inches(1.7), Inches(0.26),
                comp, font_size=7.5, bold=True, color=TEXT)
    add_textbox(s, Inches(2.3), cy20 + Inches(0.05), Inches(2.25), Inches(0.26),
                usage, font_size=8.5, color=SUB)
    cy20 += Inches(0.36)

# Section B — ENVOY Shared Services Used
add_textbox(s, Inches(4.5), Inches(1.15), Inches(4.1), Inches(0.28),
            "ENVOY Shared Services — PCW CI Platform Usage", font_size=11, bold=True, color=NAVY)

shared_rows = [
    ("Memory Store",
     "Persists competitor intelligence context across multi-turn, long-running ENVOY agent investigation workflows — enabling coherent, contextually rich agent interactions over extended analysis sessions"),
    ("Session Store",
     "Manages multi-agent workflow execution state across the Orchestrator Agent and all eight specialist PCW CI agents — the stateful backbone of the multi-agent architecture"),
    ("Tool Registry",
     "Catalogues all authorised tools available to PCW CI agents — PCW data collection APIs, BigQuery query interfaces, Apigee integration calls and analytics tools — with version control and access governance"),
    ("Agent Registry",
     "Maintains the versioned catalogue of all deployed PCW CI ENVOY agents with capability descriptions, routing metadata, deployment history and performance characteristics for governance and discovery"),
    ("Prompt Registry",
     "Stores and versions all Gemini prompt templates used in competitor analysis, recommendation generation, briefing production and regulatory explanation — enabling systematic prompt governance and A/B testing"),
    ("Policy Registry",
     "Holds business and regulatory policy rules applied by the Policy Engine to screen all PCW CI recommendations — the authoritative source of compliance rules for the recommendation governance process"),
    ("Evaluation Framework",
     "Coordinates automated quality gate enforcement for all PCW CI ML model and Gemini output quality assessments via Pegasus — the orchestration layer for continuous quality management"),
    ("MCP Registry",
     "Catalogues available PCW data source MCP servers used by the Market Collection Agent for structured competitor data retrieval — enabling standardised, governed data source management"),
    ("A2A Registry",
     "Manages the agent-to-agent communication protocol registrations enabling structured, governed coordination between PCW CI specialist agents via the A2A protocol"),
    ("Audit Framework",
     "Provides the immutable, chronologically ordered recommendation lineage and decision audit trail required for FCA compliance, internal audit review and ENVOY model governance processes"),
]
sy20 = Inches(1.48)
for sname20, susage20 in shared_rows:
    add_rect(s, Inches(4.5), sy20, Inches(4.1), Inches(0.34), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.25)
    add_textbox(s, Inches(4.55), sy20 + Inches(0.05), Inches(1.6), Inches(0.26),
                sname20, font_size=7.5, bold=True, color=TEXT)
    add_textbox(s, Inches(6.2), sy20 + Inches(0.05), Inches(2.35), Inches(0.26),
                susage20, font_size=8.5, color=SUB)
    sy20 += Inches(0.36)

# Section C — AI Capability Classification
add_textbox(s, Inches(9.0), Inches(1.15), Inches(3.9), Inches(0.28),
            "AI Capability Classification", font_size=11, bold=True, color=NAVY)

ai_class = [
    (ACCENT,  "Machine Learning (Vertex AI / Pegasus)",
     "Ranking position trend prediction and trajectory modelling. Pricing elasticity and new business volume simulation. Competitor behaviour pattern clustering and classification. Data quality validation and anomaly detection on PCW data streams. Quote conversion propensity scoring for intervention prioritisation. Model evaluation, quality monitoring and drift detection via Pegasus throughout the full model lifecycle."),
    (TEAL,    "Generative AI (Gemini / Vertex AI)",
     "Competitor proposition narrative extraction, synthesis and gap identification. Recommendation rationale and FCA-compliant explanation generation for every recommendation. Executive competitive intelligence briefing production for senior stakeholders. RAG-based competitor knowledge base querying via Vector Search. Hallucination detection and groundedness scoring applied to all outputs via Pegasus Evaluation Framework."),
    (PURPLE,  "Agentic AI (ENVOY ADK / Vertex AI Agent Engine)",
     "Autonomous continuous PCW data collection and validation without human intervention. Multi-step competitor investigation workflow orchestration via LangGraph and Cloud Workflows. Event-driven market change analysis triggered by real-time Pub/Sub events. Cross-agent intelligence aggregation and recommendation synthesis via the Orchestrator Agent. Governance escalation routing to Pega for human approval."),
    (NAVY,    "Platform & Integration Services",
     "LangGraph and Cloud Workflows for stateful agent orchestration. Pub/Sub and Eventarc for real-time event streaming. BigQuery and Vertex AI Vector Search for data storage and knowledge retrieval. Apigee for API management and security. Pega for governance workflows. ObserveAll and Dynatrace for full-stack observability. ENVOY Audit Framework for FCA-compliant compliance records."),
]
acy = Inches(1.48)
for acc, atn, atd in ai_class:
    add_rect(s, Inches(9.0), acy, Inches(3.9), Inches(0.85), fill_rgb=LIGHT, line_rgb=BORDER, line_pt=0.25)
    add_rect(s, Inches(9.0), acy, Inches(3.9), Inches(0.05), fill_rgb=acc)
    add_textbox(s, Inches(9.08), acy + Inches(0.08), Inches(3.75), Inches(0.24),
                atn, font_size=8.5, bold=True, color=NAVY)
    add_textbox(s, Inches(9.08), acy + Inches(0.32), Inches(3.75), Inches(0.5),
                atd, font_size=9, color=SUB)
    acy += Inches(0.92)

# Key Design Principles
add_textbox(s, Inches(9.0), acy + Inches(0.1), Inches(3.9), Inches(0.28),
            "Key Design Principles", font_size=11, bold=True, color=NAVY)
principles = [
    "- Human oversight is non-negotiable at the recommendation approval and execution decision stages — no pricing or proposition change is executed without an authorised human reviewer approving the recommendation in the Pega governance workflow, without exception",
    "- All AI model calls are routed through Cortex and screened through Model Armor — there is no path for an ungoverned or unmonitored model call to occur within the PCW CI platform perimeter, ensuring complete policy compliance for every AI interaction",
    "- Full observability is maintained from PCW data collection through agent execution, recommendation delivery, human approval and post-execution outcome measurement — every component monitored by ObserveAll with complete audit trail in the ENVOY Audit Framework",
    "- The platform is architected for extensibility and reuse across BCB General Insurance — every ENVOY agent, prompt template, ML model and integration pattern is registered in shared services, documented and available for subsequent use cases at materially reduced incremental delivery cost and timeline",
]
bullet_list(s, Inches(9.0), acy + Inches(0.42), Inches(3.9), Inches(1.5),
            principles, font_size=9.5, color=SUB, indent="")


# ── Save ──────────────────────────────────────────────────────────────────────
prs.save("/home/user/rag/part2.pptx")
print("Part 2 saved")
