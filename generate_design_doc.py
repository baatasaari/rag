from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

doc = Document()

# ── Page margins ──────────────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin    = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)

# ── Colour palette ────────────────────────────────────────────────────────────
LBG_GREEN      = RGBColor(0x00, 0x6A, 0x4E)   # LBG brand green
LBG_DARK       = RGBColor(0x1A, 0x1A, 0x2E)   # near-black
ACCENT_BLUE    = RGBColor(0x00, 0x5B, 0x96)   # section accent
TABLE_HEADER   = RGBColor(0x00, 0x6A, 0x4E)   # table header bg
TABLE_ALT      = RGBColor(0xF0, 0xF7, 0xF4)   # alternate row bg
CODE_BG        = RGBColor(0xF5, 0xF5, 0xF5)   # code block bg
WHITE          = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GREY     = RGBColor(0xD0, 0xD0, 0xD0)

# ── Helper utilities ──────────────────────────────────────────────────────────

def rgb_hex(rgb: RGBColor) -> str:
    return '{:02X}{:02X}{:02X}'.format(rgb[0], rgb[1], rgb[2])

def set_cell_bg(cell, rgb: RGBColor):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement('w:shd')
    shd.set(qn('w:val'),   'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'),  rgb_hex(rgb))
    tcPr.append(shd)

def set_cell_border(cell, sides=('top','bottom','left','right'), color='C0C0C0', sz='4'):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for side in sides:
        border = OxmlElement(f'w:{side}')
        border.set(qn('w:val'),   'single')
        border.set(qn('w:sz'),    sz)
        border.set(qn('w:space'), '0')
        border.set(qn('w:color'), color)
        tcBorders.append(border)
    tcPr.append(tcBorders)

def add_horizontal_rule(doc):
    p   = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pb  = OxmlElement('w:pBdr')
    bot = OxmlElement('w:bottom')
    bot.set(qn('w:val'),   'single')
    bot.set(qn('w:sz'),    '6')
    bot.set(qn('w:space'), '1')
    bot.set(qn('w:color'), '006A4E')
    pb.append(bot)
    pPr.append(pb)
    return p

def heading1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after  = Pt(6)
    r = p.add_run(text)
    r.font.size  = Pt(18)
    r.font.bold  = True
    r.font.color.rgb = LBG_GREEN
    add_horizontal_rule(doc)
    return p

def heading2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(4)
    r = p.add_run(text)
    r.font.size  = Pt(14)
    r.font.bold  = True
    r.font.color.rgb = ACCENT_BLUE
    return p

def heading3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after  = Pt(3)
    r = p.add_run(text)
    r.font.size  = Pt(12)
    r.font.bold  = True
    r.font.color.rgb = LBG_DARK
    return p

def body(doc, text, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.font.color.rgb = LBG_DARK
    return p

def bullet(doc, text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.left_indent  = Inches(0.25 * (level + 1))
    p.paragraph_format.space_after  = Pt(3)
    r = p.add_run(text)
    r.font.size = Pt(10)
    r.font.color.rgb = LBG_DARK
    return p

def code_block(doc, text):
    """Monospaced block with light grey background."""
    for line in text.strip().split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(0)
        p.paragraph_format.left_indent  = Inches(0.2)
        pPr = p._p.get_or_add_pPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'),   'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'),  'F5F5F5')
        pPr.append(shd)
        r = p.add_run(line if line else ' ')
        r.font.name  = 'Courier New'
        r.font.size  = Pt(8)
        r.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
    doc.add_paragraph()   # breathing room after block

def styled_table(doc, headers, rows, col_widths=None):
    n_cols = len(headers)
    table  = doc.add_table(rows=1 + len(rows), cols=n_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Header row
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        cell = hdr.cells[i]
        set_cell_bg(cell, TABLE_HEADER)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(h)
        r.font.bold  = True
        r.font.size  = Pt(9)
        r.font.color.rgb = WHITE

    # Data rows
    for ri, row_data in enumerate(rows):
        row = table.rows[ri + 1]
        bg  = TABLE_ALT if ri % 2 == 0 else WHITE
        for ci, val in enumerate(row_data):
            cell = row.cells[ci]
            set_cell_bg(cell, bg)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            r = p.add_run(str(val))
            r.font.size = Pt(9)
            r.font.color.rgb = LBG_DARK

    # Column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)

    doc.add_paragraph()
    return table

def page_break(doc):
    doc.add_page_break()

# ══════════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ══════════════════════════════════════════════════════════════════════════════
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(60)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('LBG RAG PLATFORM')
r.font.size  = Pt(32)
r.font.bold  = True
r.font.color.rgb = LBG_GREEN

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Enterprise-Grade Retrieval-Augmented Generation')
r.font.size  = Pt(18)
r.font.color.rgb = ACCENT_BLUE

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Conversational AI Multi-Agent System')
r.font.size  = Pt(14)
r.font.color.rgb = LBG_DARK

doc.add_paragraph()
add_horizontal_rule(doc)
doc.add_paragraph()

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run('Architecture & Design Document')
r.font.size = Pt(13)
r.font.bold = True

meta = [
    ('Classification', 'INTERNAL'),
    ('Version',        '1.0'),
    ('Date',           '26 May 2025'),
    ('Platform',       'Google Cloud Platform (GCP)'),
    ('Status',         'Design — Pre-Implementation'),
]
doc.add_paragraph()
for label, val in meta:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{label}:  ')
    r.font.bold = True
    r.font.size = Pt(10)
    r = p.add_run(val)
    r.font.size = Pt(10)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS (manual)
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, 'Table of Contents')
toc_items = [
    ('1',  'Design Principles'),
    ('2',  'The Critical Gemini Embedding Insight: Asymmetric Task Types'),
    ('3',  'Full System Architecture'),
    ('4',  'Gemini Embedding Engine Architecture'),
    ('5',  'Vector Store Strategy: AlloyDB vs Vertex AI Vector Search'),
    ('6',  'All RAG Patterns'),
    ('7',  'Multi-Agent Architecture'),
    ('8',  'Ingestion Platform (Cloud Composer DAG)'),
    ('9',  'Chunking Layer — All Strategies'),
    ('10', 'Observability Architecture (Full Stack)'),
    ('11', 'Data Lineage Architecture'),
    ('12', 'Security & Compliance Layer'),
    ('13', 'Resilience Architecture'),
    ('14', 'Evaluation Framework'),
    ('15', 'CI/CD for RAG'),
    ('16', 'GCP IAM & Identity Design'),
    ('17', 'Complete GCP Technology Stack'),
    ('18', 'Complete Project Structure'),
    ('19', 'Configuration Reference'),
]
for num, title in toc_items:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(f'  {num}.  {title}')
    r.font.size = Pt(10)
    r.font.color.rgb = ACCENT_BLUE

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — DESIGN PRINCIPLES
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '1. Design Principles')
body(doc, 'This is not a RAG wrapper. This is a RAG Platform — a fully instrumented, governed, resilient '
     'data product that can be audited by regulators, operated by SREs, and evolved by ML engineers '
     'without downtime. The platform is deployed entirely on Google Cloud Platform with Gemini Embeddings '
     'at its core.')

styled_table(doc,
    ['Principle', 'Expression'],
    [
        ('Configurability first',     'Every behavioural decision is a config key, not a code change. Schema-validated YAML drives all behaviour.'),
        ('Pluggable by contract',     'Components are swapped by implementing a protocol/interface and registering in the plugin registry. Zero other changes.'),
        ('Pattern-agnostic core',     'The same pipeline executes Naive RAG, CRAG, Self-RAG, Graph RAG, RAPTOR. Pattern selection is a config key.'),
        ('Agent-native',              'RAG is a first-class tool in the agent mesh, not a sidecar. Any agent can invoke it via the Tool Registry.'),
        ('Asymmetric embeddings',     'Gemini task_type is enforced per pipeline stage. RETRIEVAL_DOCUMENT at ingestion. RETRIEVAL_QUERY at query time. Never mixed.'),
        ('Observable by default',     'Every hop emits an OTel span, a structured JSON log line, and a Cloud Monitoring metric. Evaluation is built-in.'),
        ('Fail-safe degradation',     'Every retrieval path has a tested fallback chain. Circuit breakers trip automatically. DLQs catch ingestion failures.'),
        ('Data residency compliance', 'All GCP services deployed in europe-west2. VPC Service Controls enforce data perimeter. Required for FCA compliance.'),
        ('Least privilege identity',  'Workload Identity for GKE, IAM bindings for Cloud Run. No long-lived service account keys anywhere.'),
        ('Immutable audit trail',     'Append-only audit log table in AlloyDB, WAL-archived to GCS. Supports FCA regulatory inspection.'),
    ],
    col_widths=[2.0, 4.5]
)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — GEMINI EMBEDDING INSIGHT
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '2. The Critical Gemini Embedding Insight: Asymmetric Task Types')
body(doc, 'This is the most important architectural implication of choosing Gemini Embeddings, and it '
     'changes both the ingestion and query pipelines fundamentally. Most naive RAG implementations get '
     'this wrong, resulting in suboptimal retrieval accuracy.')

heading2(doc, '2.1 Asymmetric Embedding — The Core Concept')
body(doc, 'Gemini text-embedding-004 produces DIFFERENT vector representations for the SAME text '
     'depending on the task_type parameter. Document space and query space are distinct but '
     'aligned for retrieval. This is Matryoshka-style asymmetric embedding.')

code_block(doc, """
INGESTION TIME                          QUERY TIME
─────────────                           ──────────
task_type = RETRIEVAL_DOCUMENT          task_type = RETRIEVAL_QUERY

The model produces DIFFERENT            The model produces DIFFERENT
vector representations optimised        vector representations optimised
for being retrieved.                    for retrieving documents.

WRONG (symmetric — naive implementations):
  Ingest: embed(chunk, task=RETRIEVAL_DOCUMENT)    ✓
  Query:  embed(query, task=RETRIEVAL_DOCUMENT)    ✗  wrong task type
  Result: suboptimal retrieval accuracy

CORRECT (asymmetric — what this design enforces):
  Ingest: embed(chunk, task=RETRIEVAL_DOCUMENT)    ✓
  Query:  embed(query, task=RETRIEVAL_QUERY)       ✓
  Result: optimised retrieval alignment

ENFORCEMENT:
  EmbeddingEngine rejects calls without explicit task_type.
  Ingestion pipeline hardcodes RETRIEVAL_DOCUMENT.
  Query pipeline hardcodes RETRIEVAL_QUERY.
  Unit tests assert task_type on every embedding call.
""")

heading2(doc, '2.2 Full Task Type Reference')
styled_table(doc,
    ['Task Type', 'Used In Pipeline Stage', 'Optimised For'],
    [
        ('RETRIEVAL_DOCUMENT',  'Ingestion pipeline',             'Documents stored in vector index — maximises retrievability'),
        ('RETRIEVAL_QUERY',     'Query pipeline',                 'User queries against the index — maximises retrieval precision'),
        ('SEMANTIC_SIMILARITY', 'Semantic cache lookup, Evaluation', 'Symmetric similarity scoring between two texts'),
        ('CLASSIFICATION',      'Query intent analyser',          'Classifying text into predefined categories'),
        ('CLUSTERING',          'RAPTOR ingestion (cluster-then-summarise)', 'Grouping similar documents together'),
        ('QUESTION_ANSWERING',  'QA evaluation pipeline',         'Answer-to-question alignment scoring'),
        ('FACT_VERIFICATION',   'CRAG document grader',           'Claim-to-evidence alignment for groundedness checking'),
    ],
    col_widths=[2.0, 2.2, 2.3]
)

heading2(doc, '2.3 Output Dimensionality Options')
body(doc, 'text-embedding-004 supports configurable output dimensions via Matryoshka Representation '
     'Learning. The model trains nested representations — a 256-dim vector is the first 256 dims of '
     'a 768-dim vector, enabling post-hoc truncation without re-embedding.')

styled_table(doc,
    ['Dimensions', 'Index Size', 'Accuracy', 'Latency', 'Recommended Use'],
    [
        ('768', '~3 KB/vector', 'Highest', 'Standard', 'Production retrieval, ingestion storage'),
        ('512', '~2 KB/vector', 'Good',    'Faster',   'Balance of cost and accuracy'),
        ('256', '~1 KB/vector', 'Adequate', 'Fastest',  'Semantic cache lookups, low-latency paths'),
    ],
    col_widths=[1.2, 1.3, 1.2, 1.2, 2.6]
)
body(doc, 'LBG Recommendation: Store vectors at 768d. Use 256d truncation for semantic cache lookups '
     'to maximise cache throughput without re-embedding.')

heading2(doc, '2.4 Model Selection: text-embedding-004 vs text-multilingual-embedding-002')
styled_table(doc,
    ['Model', 'Languages', 'Dimensions', 'Best For'],
    [
        ('text-embedding-004',               'English-optimised', '768', 'Standard LBG corpus (English)'),
        ('text-multilingual-embedding-002',  '100+ languages',    '768', 'Welsh-language content, international customers'),
    ],
    col_widths=[2.8, 1.5, 1.2, 2.0]
)
body(doc, 'Language detection is performed in the Clean stage of the ingestion pipeline. The '
     'EmbeddingEngine automatically selects the correct model based on detected language.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — FULL SYSTEM ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '3. Full System Architecture')
body(doc, 'The platform is structured as a layered architecture where each layer has a single '
     'responsibility and communicates with adjacent layers only via well-defined interfaces. '
     'All cross-cutting concerns (observability, security, resilience) are applied uniformly '
     'across all layers.')

heading2(doc, '3.1 Architectural Layers (Top to Bottom)')
layers = [
    ('External Interfaces',        'Cloud Endpoints / Apigee, Cloud Run (REST/gRPC/WebSocket), Pub/Sub (async ingestion triggers)'),
    ('API Gateway & Security',     'Cloud Armor (WAF), Cloud IAP (AuthN/AuthZ), Correlation ID injection, Cloud DLP inbound scan, Audit log entry'),
    ('Agent Orchestration',        'Supervisor, Router, Retriever, Critic, Synthesiser agents. Tool Registry and Dispatcher. Configurable HITL gates.'),
    ('RAG Pattern Engine',         'Naive, Advanced, CRAG, Self-RAG, Fusion, Graph, Hierarchical, Agentic, Speculative, RAPTOR, Adaptive Router'),
    ('Query Processing',           'Query Analyser (intent + NER), Query Transformer (HyDE/Step-back/Multi-query), RBAC Filter Builder, Validator'),
    ('Embedding (Query)',          'Vertex AI text-embedding-004, task_type=RETRIEVAL_QUERY, 768d. Semantic cache check first.'),
    ('Retrieval',                  'Dense (AlloyDB pgvector), Sparse (Vertex AI Search / BM25), Graph (Neo4j), Hybrid (RRF fusion), Semantic Cache (Memorystore)'),
    ('Augmentation',               'Re-ranker (Cohere / Cross-Encoder), Context Compressor, Document Grader (CRAG), Hallucination Detector'),
    ('Generation',                 'Prompt Builder (versioned templates in GCS), Vertex AI Gemini 2.0 Flash, Response Validator, Citation Injector'),
    ('Storage Fabric',             'AlloyDB pgvector (vectors), AlloyDB (doc store + lineage), Neo4j GKE (graph), Memorystore Redis (cache), GCS (blobs)'),
    ('Observability (Cross-cut)',   'Cloud Trace (OTel spans), Cloud Logging (structured JSON), Cloud Monitoring (40+ metrics), Grafana dashboards'),
    ('Security (Cross-cut)',        'Cloud DLP, Cloud IAM + Workload Identity, VPC Service Controls, Secret Manager, Immutable Audit Log'),
    ('Resilience (Cross-cut)',      'Circuit breakers, Retry + backoff, Bulkhead isolation, Pub/Sub dead-letter topics, Health checks'),
]
styled_table(doc,
    ['Layer', 'Components & Services'],
    layers,
    col_widths=[2.2, 4.3]
)

heading2(doc, '3.2 Data Flow: Query Path')
code_block(doc, """
User Request
    │  [Cloud Armor WAF + Cloud IAP AuthN]
    │  [Correlation ID injected]
    │  [Cloud Audit Log: query.received]
    ▼
API Gateway (Cloud Endpoints / Apigee)
    │  [OTel TraceContext propagated]
    ▼
Query Analyser
    ├── Intent classification  (task_type=CLASSIFICATION)
    ├── Entity extraction (NER)
    ├── Complexity score → pattern selection
    └── Metadata filter inference (RBAC-aware)
    │
    ▼
Query Transformer (if Advanced/Fusion/CRAG pattern)
    ├── HyDE: generate hypothetical document
    ├── Step-back: abstract to general principle
    ├── Multi-query: N sub-queries for parallel retrieval
    └── Sub-query decomposition
    │
    ▼
Semantic Cache Check (Memorystore Redis)
    ├── embed(query, task=SEMANTIC_SIMILARITY, dimensions=256)
    ├── Lookup: cosine similarity threshold = 0.97
    ├── HIT  → return cached response (p50 < 5ms)
    └── MISS → continue to retrieval
    │
    ▼
Embedding (query): text-embedding-004, task_type=RETRIEVAL_QUERY, 768d
    │
    ├──────────────────┬──────────────────────────┐
    ▼                  ▼                          ▼
Dense Retrieval    Sparse Retrieval          Graph Retrieval
AlloyDB pgvector   Vertex AI Search          Neo4j GKE
(HNSW cosine)      (BM25 keyword)            (entity traversal)
top_k=20           top_k=20                  depth=2
    │                  │                          │
    └──────────────────┴──────────────────────────┘
                        │
                   RRF Fusion
             (Reciprocal Rank Fusion)
                        │
                   Re-ranker
              (Cohere Rerank API)
                   top_n=5
                        │
               Context Compressor
              (LLM extract relevant)
                        │
                  Prompt Builder
            (versioned template + context
             + conversation history + citations)
                        │
               Vertex AI Gemini 2.0 Flash
                        │
               Response Validator
               (guardrails + faithfulness)
                        │
               Citation Injector
                        │
                 Final Response
                        │
    [async] → Pub/Sub: rag.eval.pending → Evaluation Worker
    [async] → Cache store (if high confidence)
    [sync]  → Cloud Logging: structured response log
    [sync]  → Cloud Trace: span closed
""")

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — EMBEDDING ENGINE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '4. Gemini Embedding Engine Architecture')

heading2(doc, '4.1 Engine Configuration')
code_block(doc, """
embedding:
  provider: vertex_ai
  model: text-embedding-004
  project_id: ${GCP_PROJECT_ID}
  location: europe-west2          # EU data residency for LBG / FCA

  task_types:                     # enforced by engine — callers cannot override
    ingestion:      RETRIEVAL_DOCUMENT
    query:          RETRIEVAL_QUERY
    cache_lookup:   SEMANTIC_SIMILARITY
    evaluation:     SEMANTIC_SIMILARITY
    clustering:     CLUSTERING        # RAPTOR ingestion
    classification: CLASSIFICATION    # query intent analyser

  dimensions:
    default:    768
    fast_path:  256               # semantic cache, low-latency paths

  batching:
    max_batch_size: 250           # Vertex AI text-embedding-004 limit
    max_concurrent_batches: 10
    batch_timeout_ms: 5000

  rate_limits:
    requests_per_minute: 1500
    tokens_per_minute: 4000000
    retry_on_429: true
    backoff_multiplier: 2.0

  fallback:
    provider: vertex_ai
    model: text-multilingual-embedding-002   # quota failover

  cost_tracking:
    enabled: true
    metric_name: rag/embedding/cost_usd
    price_per_1k_chars: 0.000025
""")

heading2(doc, '4.2 Language-Based Model Routing')
body(doc, 'Language detection is performed during the Clean stage of ingestion. The embedding engine '
     'uses this to route to the correct model automatically.')

styled_table(doc,
    ['Condition', 'Model Selected', 'Task Type', 'Dimensions'],
    [
        ('document.language == "en"',  'text-embedding-004',              'RETRIEVAL_DOCUMENT', '768'),
        ('document.language != "en"',  'text-multilingual-embedding-002', 'RETRIEVAL_DOCUMENT', '768'),
        ('query.language == "en"',     'text-embedding-004',              'RETRIEVAL_QUERY',    '768'),
        ('query.language != "en"',     'text-multilingual-embedding-002', 'RETRIEVAL_QUERY',    '768'),
        ('cache lookup (any)',          'text-embedding-004',              'SEMANTIC_SIMILARITY', '256'),
        ('clustering (RAPTOR)',         'text-embedding-004',              'CLUSTERING',          '768'),
    ],
    col_widths=[2.2, 2.2, 1.8, 1.2]
)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — VECTOR STORE STRATEGY
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '5. Vector Store Strategy: AlloyDB vs Vertex AI Vector Search')

heading2(doc, '5.1 Decision Matrix')
styled_table(doc,
    ['Criterion', 'AlloyDB + pgvector', 'Vertex AI Vector Search'],
    [
        ('Vector scale',       '≤ 50M vectors',            '10M → billions'),
        ('Query latency',      '5–20ms (HNSW)',             '1–5ms (ScaNN hardware-accelerated)'),
        ('Hybrid queries',     '✓ Native SQL + vector',     '✗ Metadata filtering only (restricts)'),
        ('Update latency',     'Real-time (row insert)',    'Streaming: ~seconds / Batch: ~minutes'),
        ('SQL integration',    '✓ Full PostgreSQL',         '✗ Separate API'),
        ('Lineage JOIN queries','✓ Same DB, native JOIN',   '✗ Separate store required'),
        ('Index types',        'IVFFLAT, HNSW',             'ScaNN (TreeAH)'),
        ('Cost model',         'Per vCPU/RAM (predictable)', 'Per node-hour + per query'),
        ('Phase 1 & 2',        '✓ Recommended',             '—'),
        ('Phase 3 (>50M)',     '—',                         '✓ Recommended'),
    ],
    col_widths=[2.0, 2.2, 2.3]
)
body(doc, 'Architecture Decision: Start with AlloyDB + pgvector. The VectorStore protocol means '
     'migration to Vertex AI Vector Search requires zero application code changes — only config update.')

heading2(doc, '5.2 AlloyDB pgvector Index Configuration')
code_block(doc, """
storage:
  vector_store:
    provider: alloydb_pgvector
    cluster: lbg-rag-alloydb-cluster
    instance: lbg-rag-primary
    database: rag_platform
    pool_size: 20
    max_overflow: 40

    index:
      type: hnsw                    # HNSW: best query recall, higher build cost
      hnsw:
        m: 16                       # connections per node (16–64; higher = better recall + more RAM)
        ef_construction: 64         # build-time accuracy (64–128 recommended)
        ef_search: 40               # query-time accuracy (must be ≥ top_k)

    dimensions: 768
    distance_metric: cosine         # for normalised Gemini vectors
""")

heading2(doc, '5.3 Vertex AI Vector Search Configuration (Scale-Out)')
code_block(doc, """
storage:
  vector_store_scaleout:
    provider: vertex_ai_vector_search
    project_id: ${GCP_PROJECT_ID}
    location: europe-west2
    index_id: ${VERTEX_INDEX_ID}
    endpoint_id: ${VERTEX_ENDPOINT_ID}
    update_mode: streaming          # streaming | batch
    approximate_neighbors_count: 50
    distance_measure: DOT_PRODUCT_DISTANCE   # for L2-normalised Gemini vectors
    # Restricts (metadata filters) applied server-side — RBAC enforced
""")

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — RAG PATTERNS
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '6. All RAG Patterns')

heading2(doc, '6.1 Adaptive Pattern Router')
body(doc, 'The Adaptive Router analyses each query and selects the appropriate RAG pattern. '
     'This is the default pattern — it prevents over-engineering simple queries with complex patterns '
     'and ensures complex queries get appropriate treatment.')

styled_table(doc,
    ['Query Type', 'Pattern Selected', 'Trigger Signal'],
    [
        ('Simple factual lookup',         'Naive RAG',          'Low complexity score, single entity, high corpus confidence'),
        ('Multi-step analytical',         'Advanced RAG',       'Medium complexity, multiple entities, requires step-back'),
        ('Uncertain retrieval quality',   'CRAG',               'Low corpus coverage, out-of-domain detected'),
        ('Needs self-assessment',         'Self-RAG',           'High-stakes response, compliance-relevant topic'),
        ('Multiple perspectives needed',  'Fusion RAG',         'Broad topic, ambiguous query, high user intent diversity'),
        ('Relational / entity graph',     'Graph RAG',          'Entities detected, "how does X relate to Y" intent'),
        ('Long document context',         'Hierarchical RAG',   'Source docs >10 pages, precision + context both needed'),
        ('Multi-source, multi-tool',      'Agentic RAG',        'Requires live data, SQL, API calls alongside vector retrieval'),
        ('Very long docs / summarisation','RAPTOR RAG',         'Document exceeds 100K tokens, needs abstractive understanding'),
    ],
    col_widths=[2.2, 1.8, 2.5]
)

heading2(doc, '6.2 Pattern Specifications')

patterns = [
    ('Naive RAG',
     'Query → Embed (RETRIEVAL_QUERY) → Vector Search → Top-K → Prompt → Generate',
     'Simple factual lookup, high-confidence corpus, latency-sensitive'),
    ('Advanced RAG',
     'Query → Analyser → Transformer (step-back + multi-query) → Parallel Retrieval → RRF Fusion → Re-ranker → Compressor → Prompt → Generate → Validator',
     'Complex queries, mixed retrieval needs, quality-critical responses'),
    ('Corrective RAG (CRAG)',
     'Query → Retrieve → Document Grader (RELEVANT/IRRELEVANT/AMBIGUOUS) → If poor: web search fallback + query rewrite → Generate with graded context',
     'Corpus may be incomplete, factual accuracy critical, hallucination-sensitive domain'),
    ('Self-RAG',
     'Query → LLM decides retrieval need (RETRIEVE token) → Retrieve → LLM critiques each doc (SUPPORT/PARTIAL/NO) → Generate → LLM critiques own answer → Revise if NOT_SUPPORTED',
     'Response quality paramount, willing to pay extra latency, high-stakes answers'),
    ('Fusion RAG',
     'Query → Generate N sub-queries (LLM) → Parallel retrieval per sub-query → RRF merge all result sets → Re-rank → Generate unified answer',
     'Broad topics, multiple perspectives needed, ambiguous single query'),
    ('Graph RAG',
     'Query → Entity extraction → Graph traversal (Neo4j) → Community detection → Community summaries → Dense retrieval on summaries → Generate',
     'Relational data, regulatory linkages, "how does X relate to Y" queries'),
    ('Hierarchical RAG',
     'Query → Embed → Retrieve child chunks (precision, 512 tokens) → Fetch parent chunks (context, 2048 tokens) → De-duplicate → Generate',
     'Long documents, need both retrieval precision and surrounding context'),
    ('Agentic RAG',
     'Query → Supervisor plans steps → Router selects tools (RAG/SQL/API/Calculator) → Execute → Reflect: complete? → If no: re-plan → Synthesise final answer',
     'Multi-source, multi-step, live data needed alongside document retrieval'),
    ('RAPTOR RAG',
     'Ingestion: Cluster leaf chunks (UMAP+GMM) → Summarise clusters → Embed summaries → Re-cluster → Repeat to root. Query: Collapsed tree search across all levels → Select abstraction level → Generate',
     'Very long documents, need both detail and high-level understanding'),
]

for name, flow, when in patterns:
    heading3(doc, name)
    body(doc, f'Flow:  {flow}')
    body(doc, f'Use when:  {when}')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MULTI-AGENT ARCHITECTURE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '7. Multi-Agent Architecture')

heading2(doc, '7.1 Agent Roles')
styled_table(doc,
    ['Agent', 'Responsibility', 'Inputs', 'Outputs'],
    [
        ('Supervisor',   'Decomposes complex queries into a plan; delegates to specialist agents; owns final state machine', 'User query + conversation history', 'Plan + delegated tasks'),
        ('Router',       'Classifies intent; selects RAG pattern; decides which agents and tools to activate', 'Query + intent signals', 'Pattern selection + routing decision'),
        ('Retriever',    'Executes the selected RAG pattern; manages tool calls (RAG, SQL, API); returns ranked evidence', 'Query + filters + pattern', 'Ranked context + sources'),
        ('Critic',       'Evaluates draft answer for faithfulness, groundedness, hallucination; requests revision if below threshold', 'Draft answer + context', 'Pass/Fail + revision instructions'),
        ('Synthesiser',  'Combines evidence from multiple tools/agents; builds coherent final answer with citations', 'Evidence set + sources', 'Final answer + citation list'),
    ],
    col_widths=[1.3, 2.0, 1.7, 1.5]
)

heading2(doc, '7.2 Agent State Machine')
code_block(doc, """
IDLE ──► PLANNING ──► EXECUTING ──► REFLECTING ──► DONE
                          │               │
                          └───────────────┘
                        (loop until confidence ≥ threshold
                         or max_iterations reached)

HITL Gates (configurable insertion points):
  After PLANNING   → human can approve/reject plan before execution
  After draft answer → human review before delivery to user
  Triggered when:
    confidence_score < configured threshold
    query classified as compliance-sensitive
    answer contains regulatory product recommendations
    critic agent flags potential hallucination
""")

heading2(doc, '7.3 Tool Registry')
styled_table(doc,
    ['Tool', 'Description', 'Backed By'],
    [
        ('rag_tool',       'Vector + hybrid retrieval from document corpus',  'AlloyDB pgvector + Vertex AI Search'),
        ('sql_tool',       'Structured data queries for rates, limits, rules', 'AlloyDB (structured tables)'),
        ('api_tool',       'Live data: balances, product availability, rates',  'Internal LBG APIs (via VPC)'),
        ('calculator_tool','Numeric computations: APR, affordability, interest', 'Python safe eval'),
        ('search_tool',    'Web search for regulatory updates (CRAG fallback)',  'Vertex AI Search / Programmable Search'),
    ],
    col_widths=[1.5, 2.5, 2.5]
)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — INGESTION PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '8. Ingestion Platform (Cloud Composer DAG)')

heading2(doc, '8.1 Pipeline Trigger')
body(doc, 'Documents are uploaded to a GCS bucket (rag-documents-raw). A GCS event notification '
     'triggers a Pub/Sub message on the rag.ingestion.pending topic. Cloud Composer subscribes '
     'to this topic and triggers the ingestion DAG.')

heading2(doc, '8.2 Pipeline Stages')
styled_table(doc,
    ['Stage', 'Task Name', 'Action', 'GCP Service'],
    [
        ('1',  'load_document',      'Read raw file from GCS into pipeline memory',                    'Cloud Storage'),
        ('2',  'parse_document',     'Extract text, tables, images, metadata by file type',           'PyMuPDF / python-docx / BeautifulSoup'),
        ('3',  'clean_document',     'Normalize unicode, strip headers/footers, detect language',      'NLP utilities'),
        ('4',  'dlp_scan',           'Detect and redact UK PII (NI, sort code, account numbers)',     'Cloud DLP API'),
        ('5',  'classify_data',      'Assign: PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED',          'Rule engine + ML classifier'),
        ('6',  'enrich_document',    'NER entity extraction, topic classification, keyword extraction','Vertex AI NLP'),
        ('7',  'deduplicate',        'Hash-based exact dedup + semantic near-dedup (cosine > 0.97)',   'AlloyDB hash lookup + embedding'),
        ('8',  'chunk_document',     'Apply chunking strategy from config (hierarchical default)',     'Chunking engine (pluggable)'),
        ('9',  'embed_chunks',       'Embed all chunks: text-embedding-004, task=RETRIEVAL_DOCUMENT',  'Vertex AI Embeddings API'),
        ('10', 'store_vectors',      'Upsert chunk vectors + metadata to AlloyDB pgvector',           'AlloyDB'),
        ('11', 'store_documents',    'Store full chunk text + metadata to document store',            'AlloyDB'),
        ('12', 'build_graph',        'Extract entities and relations; upsert to Neo4j',               'Neo4j on GKE'),
        ('13', 'record_lineage',     'Write full provenance chain to lineage tables',                 'AlloyDB'),
        ('14', 'emit_events',        'Publish rag.document.indexed to Pub/Sub',                       'Cloud Pub/Sub'),
        ('15', 'invalidate_cache',   'Flush affected semantic cache keys in Redis',                   'Memorystore for Redis'),
    ],
    col_widths=[0.4, 1.7, 2.5, 1.9]
)

heading2(doc, '8.3 Dead Letter Queue (DLQ)')
body(doc, 'If any task fails after 3 retries with exponential backoff, the message is published to '
     'the dead-letter topic (rag.ingestion.dlq). A Cloud Function notifies the operations team, '
     'writes a structured error log to Cloud Logging, and appends a record to the DLQ analytics '
     'table in BigQuery for failure pattern analysis.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — CHUNKING LAYER
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '9. Chunking Layer — All Strategies')

styled_table(doc,
    ['Strategy', 'Mechanism', 'Config Parameters', 'Best For', 'Recommended'],
    [
        ('Fixed Size',      'Split by token/char/word count with overlap window',
                            'chunk_size=512, overlap=64, unit=tokens',
                            'Uniform documents, baseline approach', ''),
        ('Sentence-based',  'spaCy sentence boundary detection; group N sentences per chunk',
                            'min_sentences=3, max_sentences=8',
                            'Prose documents, preserving grammatical context', ''),
        ('Semantic',        'Embed sentences; split where cosine delta exceeds percentile threshold',
                            'breakpoint_type=percentile, threshold=95',
                            'Heterogeneous documents with clear topic shifts', ''),
        ('Hierarchical',    'Large parent chunks (2048t) contain small child chunks (512t). Retrieve child for precision, return parent for context.',
                            'parent_size=2048, child_size=512, overlap=64',
                            'Most LBG documents — best precision/context balance', '✓ DEFAULT'),
        ('Recursive',       'Split by separator hierarchy (\\n\\n → \\n → . → space) until target size',
                            'separators=[...], chunk_size=512',
                            'Structured documents with natural hierarchy', ''),
        ('Agentic',         'LLM proposes chunk boundaries by generating questions each chunk answers. Chunk = unit of answerable intent.',
                            'llm_model=gemini-2.0-flash',
                            'Complex unstructured banking documents, highest quality', '✓ FUTURE'),
        ('AST-based',       'Parse source code AST; split at function/class boundaries',
                            'language=python|java|...',
                            'Code documentation, technical policies referencing code', ''),
        ('Late Chunking',   'Embed full document first; apply chunking in embedding space, preserving long-range context',
                            'embed_first=true',
                            'Documents with strong long-range dependencies', ''),
        ('RAPTOR',          'Cluster leaf chunks → LLM summarise → embed summaries → re-cluster → repeat to root',
                            'cluster_method=UMAP+GMM, summary_model=gemini-2.0-flash',
                            'Very long documents requiring multi-level abstraction', ''),
    ],
    col_widths=[1.4, 2.2, 1.8, 1.5, 1.0]
)

body(doc, 'Every chunk carries a full metadata envelope including: chunk_id, document_id, '
     'chunk_index, chunk_hash (SHA256), parent_chunk_id, char_start, char_end, token_count, '
     'page_number, section_header, chunking_strategy, data_classification, pii_present, '
     'department_access, source_uri, document_version, and ingested_at.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — OBSERVABILITY
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '10. Observability Architecture (Full Stack)')

heading2(doc, '10.1 Three Pillars: Traces, Metrics, Logs')
styled_table(doc,
    ['Pillar', 'Technology', 'GCP Service', 'Granularity'],
    [
        ('Distributed Tracing', 'OpenTelemetry SDK (Python)', 'Cloud Trace',          'Every request: full span tree from API gateway to LLM response'),
        ('Metrics',             'OpenTelemetry + Prometheus', 'Cloud Monitoring',      '40+ custom metrics; 15-second scrape interval'),
        ('Structured Logs',     'Python structlog → JSON',   'Cloud Logging',          'Every operation: JSON log line with full context envelope'),
        ('Evaluation Scores',   'RAGAS + Vertex AI Eval',    'Vertex AI Experiments',  'Per-request async; nightly batch on golden QA sets'),
    ],
    col_widths=[1.8, 2.0, 1.8, 2.2]
)

heading2(doc, '10.2 OTel Span Tree — Anatomy of a Single Request')
body(doc, 'Every request generates a complete span tree exported to Cloud Trace. Key spans:')

spans = [
    ('api.gateway.request',      'user.id, tenant.id, correlation_id, request_size_bytes',  'auth.verified, pii.scan.complete, rate_limit.checked'),
    ('rag.query.analyse',        'query.intent, query.entities[], query.complexity_score',   'intent.classified {confidence=0.94}, entities.extracted {count=3}'),
    ('rag.query.transform',      'transform.strategy, transformed_queries[], hyde.enabled',  'sub_queries.generated {count=3}'),
    ('rag.embed.query',          'embedding.model, task_type=RETRIEVAL_QUERY, dimensions=768, cache.hit', 'embedding.complete {vector_norm=0.9987}'),
    ('rag.retrieve.dense',       'top_k=20, score_range, alloydb.latency_ms',               'docs.returned {count=20}'),
    ('rag.retrieve.sparse',      'top_k=20, score_range, search.latency_ms',                'docs.returned {count=20}'),
    ('rag.fusion.rrf',           'docs.before_fusion, docs.after_fusion, rrf.k_constant=60','fusion.complete'),
    ('rag.rerank',               'reranker.provider=cohere, docs.in, docs.out, top_score',  'rerank.complete {latency_ms=87}'),
    ('rag.context.compress',     'chars_before, chars_after, compression_ratio',            'compress.complete'),
    ('rag.generate',             'llm.model, prompt.version, tokens_in, tokens_out, cost_usd', 'first_token_received {latency_ms=320}, stream.complete'),
    ('rag.evaluate.online',      'faithfulness, answer_relevancy, context_precision',       'eval.complete {async=true}'),
]

styled_table(doc,
    ['Span Name', 'Key Attributes', 'Span Events'],
    spans,
    col_widths=[2.0, 2.5, 2.0]
)

heading2(doc, '10.3 Structured Log Schema')
body(doc, 'Every log line is JSON. No free-text logs. Fully indexed in Cloud Logging.')
code_block(doc, """
{
  "timestamp":   "2025-05-26T14:32:10.847Z",
  "level":       "INFO",
  "service":     "lbg-rag-platform",
  "component":   "retriever.hybrid",
  "environment": "production",
  "region":      "europe-west2",

  "trace": {
    "trace_id":       "a3f7c2b1d4e5f6a7b8c9d0e1f2a3b4c5",
    "span_id":        "d4e5f6a7b8c9d0e1",
    "correlation_id": "req-2025-05-26-00847293",
    "session_id":     "sess-abc123",
    "user_id":        "u-hash-7f3a9c",      # hashed — never raw
    "tenant_id":      "lbg-retail-banking"
  },

  "event": "retrieval.complete",

  "rag": {
    "query_id":           "qry-98f3a2c1",
    "query_hash":         "sha256:4f7a...",  # hash — never raw query text in logs
    "query_intent":       "product_lookup",
    "pattern":            "hierarchical",
    "retrieval_strategy": "hybrid",
    "docs_retrieved":     20,
    "docs_after_rerank":  5,
    "top_score":          0.9234,
    "latency_ms":         143,
    "cache_hit":          false
  },

  "llm": {
    "provider":      "vertex_ai",
    "model":         "gemini-2.0-flash-001",
    "prompt_version":"lbg-default-v2.3.1",
    "input_tokens":  2847,
    "output_tokens": 312,
    "cost_usd":      0.000412,
    "latency_ms":    1847,
    "finish_reason": "stop"
  },

  "security": {
    "pii_detected":            false,
    "data_classification":     "INTERNAL",
    "access_control_applied":  true,
    "docs_filtered_by_rbac":   3
  },

  "eval": {
    "faithfulness":      0.94,
    "answer_relevancy":  0.91,
    "context_precision": 0.88
  }
}
""")

heading2(doc, '10.4 Cloud Monitoring Metrics Catalogue')
body(doc, 'All metrics are exported via OpenTelemetry under the custom.googleapis.com/rag/ namespace.')

metrics_groups = [
    ('Ingestion', [
        ('rag/ingestion/documents_total',     'CUMULATIVE', 'INT64',   'status, source_type, tenant'),
        ('rag/ingestion/duration',            'DISTRIBUTION','seconds', 'source_type, tenant'),
        ('rag/ingestion/chunks_produced',     'CUMULATIVE', 'INT64',   'chunking_strategy, tenant'),
        ('rag/ingestion/dlq_depth',           'GAUGE',      'INT64',   '—'),
    ]),
    ('Embedding', [
        ('rag/embedding/requests_total',      'CUMULATIVE', 'INT64',   'provider, model, task_type, status'),
        ('rag/embedding/latency',             'DISTRIBUTION','seconds', 'provider, model, task_type'),
        ('rag/embedding/cost_usd',            'CUMULATIVE', 'DOUBLE',  'provider, model'),
        ('rag/embedding/cache_hit_ratio',     'GAUGE',      'DOUBLE',  'provider'),
    ]),
    ('Retrieval', [
        ('rag/retrieval/requests_total',      'CUMULATIVE', 'INT64',   'strategy, tenant, pattern'),
        ('rag/retrieval/latency',             'DISTRIBUTION','seconds', 'strategy'),
        ('rag/retrieval/top_score',           'DISTRIBUTION','—',       'strategy'),
        ('rag/retrieval/rbac_filtered_docs',  'CUMULATIVE', 'INT64',   'tenant'),
    ]),
    ('Generation', [
        ('rag/generation/latency',            'DISTRIBUTION','seconds', 'provider, model'),
        ('rag/generation/ttft',               'DISTRIBUTION','seconds', 'provider, model'),
        ('rag/generation/tokens_input',       'CUMULATIVE', 'INT64',   'provider, model'),
        ('rag/generation/tokens_output',      'CUMULATIVE', 'INT64',   'provider, model'),
        ('rag/generation/cost_usd',           'CUMULATIVE', 'DOUBLE',  'provider, model, tenant'),
    ]),
    ('Evaluation', [
        ('rag/eval/faithfulness',             'GAUGE',      'DOUBLE',  'pattern, tenant'),
        ('rag/eval/answer_relevancy',         'GAUGE',      'DOUBLE',  'pattern, tenant'),
        ('rag/eval/context_precision',        'GAUGE',      'DOUBLE',  'pattern, tenant'),
        ('rag/eval/context_recall',           'GAUGE',      'DOUBLE',  'pattern, tenant'),
        ('rag/eval/groundedness',             'GAUGE',      'DOUBLE',  'pattern, tenant'),
    ]),
    ('Resilience', [
        ('rag/circuit_breaker/state',         'GAUGE',      'INT64',   'component  (0=closed 1=open 2=half-open)'),
        ('rag/circuit_breaker/trips_total',   'CUMULATIVE', 'INT64',   'component'),
        ('rag/request/duration',              'DISTRIBUTION','seconds', 'tenant, pattern'),
        ('rag/request/errors_total',          'CUMULATIVE', 'INT64',   'error_class, tenant'),
    ]),
]

for group_name, group_metrics in metrics_groups:
    heading3(doc, group_name)
    styled_table(doc,
        ['Metric', 'Kind', 'Type', 'Labels'],
        group_metrics,
        col_widths=[3.0, 1.2, 0.8, 2.0]
    )

heading2(doc, '10.5 Alert Policies')
styled_table(doc,
    ['Alert Name', 'Condition', 'Threshold', 'Severity', 'Channel'],
    [
        ('RAG P95 Latency',           'request/duration p95',                       '> 3s for 5m',    'Warning',  'PagerDuty'),
        ('RAG High Error Rate',       'request/errors_total / requests_total',       '> 1% for 2m',    'Critical', 'PagerDuty'),
        ('LLM Circuit Breaker Open',  'circuit_breaker/state{component=gemini} == 1','Immediately',    'Critical', 'PagerDuty'),
        ('Faithfulness Degraded',     'eval/faithfulness avg',                       '< 0.80 for 10m', 'Warning',  'Slack'),
        ('Ingestion DLQ Growing',     'pubsub dlq undelivered messages',             '> 50 for 5m',    'Warning',  'Slack'),
        ('Monthly Cost Spike',        'generation/cost_usd daily sum',               '> £500/day',     'Warning',  'Email FinOps'),
        ('Embedding Quota Approach',  'embedding/requests_total rate',               '> 80% quota',    'Warning',  'Slack'),
    ],
    col_widths=[1.9, 2.2, 1.4, 0.9, 1.0]
)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — DATA LINEAGE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '11. Data Lineage Architecture')
body(doc, 'Every document chunk maintains a full provenance chain from source to generated answer. '
     'This is mandatory for FCA compliance — the platform must answer "where did this fact in the '
     'response come from, from which document version, at what time?"')

heading2(doc, '11.1 Lineage Record Schema')

records = [
    ('DocumentLineage', [
        'document_id (UUID)',
        'content_hash: SHA256 — detects tampering or changes',
        'source_uri: e.g. sharepoint://site/lib/doc.pdf',
        'source_type: PDF | DOCX | CONFLUENCE | SHAREPOINT | API',
        'ingested_at: ISO8601',
        'data_classification: PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED',
        'owner_team, retention_policy, version, last_modified (from source)',
    ]),
    ('ChunkLineage', [
        'chunk_id (UUID)',
        'document_id → DocumentLineage.document_id',
        'chunk_index (position in document)',
        'chunk_hash: SHA256',
        'chunking_strategy and full config snapshot',
        'parent_chunk_id (for hierarchical strategy)',
        'char_start, char_end, page_number, section_header',
        'pipeline_run_id (links to ingestion DAG run)',
    ]),
    ('EmbeddingLineage', [
        'embedding_id (UUID)',
        'chunk_id → ChunkLineage.chunk_id',
        'embedding_model: text-embedding-004',
        'task_type: RETRIEVAL_DOCUMENT',
        'dimensions: 768',
        'vector_store_id and index_name',
        'created_at: ISO8601',
    ]),
    ('RetrievalEvent', [
        'retrieval_id (UUID)',
        'query_id, trace_id (links to OTel trace)',
        'chunk_id → ChunkLineage.chunk_id',
        'retrieval_strategy, dense_score, sparse_score, fusion_score, rerank_score',
        'rank_before_rerank, rank_after_rerank',
        'included_in_context: boolean',
        'retrieved_at: ISO8601',
    ]),
    ('GenerationEvent', [
        'generation_id (UUID)',
        'query_id, trace_id',
        'prompt_version: lbg-default-v2.3.1',
        'llm_provider, llm_model, input_tokens, output_tokens',
        'chunk_ids_used: [UUID, ...] — exact chunks in the prompt',
        'response_hash: SHA256',
        'eval_scores: {faithfulness, answer_relevancy, ...}',
    ]),
    ('AnswerLineage', [
        'answer_id (UUID)',
        'generation_id → GenerationEvent.generation_id',
        'document_ids[], chunk_ids[], source_uris[] — full ancestry',
        'user_id (hashed), tenant_id',
        'answered_at: ISO8601',
    ]),
]

for record_name, fields in records:
    heading3(doc, record_name)
    for f in fields:
        bullet(doc, f)

heading2(doc, '11.2 Compliance Query Example')
body(doc, 'Regulators or auditors can ask: "Which source document contributed to the answer given '
     'to user X at 14:32 on 26 May, and what version of that document was it?" This is answered '
     'in a single JOIN chain: AnswerLineage → GenerationEvent → ChunkLineage → DocumentLineage. '
     'No manual reconstruction required.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — SECURITY & COMPLIANCE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '12. Security & Compliance Layer')

heading2(doc, '12.1 Cloud DLP — UK PII Detection')
body(doc, 'Cloud DLP is applied at Stage 4 of the ingestion pipeline. It detects UK-specific '
     'PII types built into the Cloud DLP service and applies configured de-identification '
     'transformations before chunks are stored.')

styled_table(doc,
    ['PII Info Type', 'Action', 'Example'],
    [
        ('NATIONAL_INSURANCE_NUMBER', 'REDACT → [REDACTED]',                  'AB123456C → [REDACTED]'),
        ('UK_BANK_ACCOUNT_NUMBER',    'REPLACE_WITH_INFO_TYPE',               '12345678 → [UK_BANK_ACCOUNT_NUMBER]'),
        ('UK_SORT_CODE',              'REPLACE_WITH_INFO_TYPE',               '12-34-56 → [UK_SORT_CODE]'),
        ('CREDIT_CARD_NUMBER',        'REDACT',                               '4111... → [REDACTED]'),
        ('PERSON_NAME',               'PSEUDONYMISE (consistent token)',       'John Smith → PERSON_A'),
        ('DATE_OF_BIRTH',             'REDACT',                               '01/01/1980 → [REDACTED]'),
        ('EMAIL_ADDRESS',             'REDACT',                               'j@bank.com → [REDACTED]'),
        ('PHONE_NUMBER',              'REDACT',                               '07700... → [REDACTED]'),
        ('IBAN_CODE',                 'REPLACE_WITH_INFO_TYPE',               'GB29... → [IBAN_CODE]'),
        ('SWIFT_CODE',                'REPLACE_WITH_INFO_TYPE',               'LOYDGB2L → [SWIFT_CODE]'),
    ],
    col_widths=[2.5, 2.0, 2.0]
)
body(doc, 'Important: Cloud DLP logs only the TYPE of PII found, never the VALUE. '
     'Chunk metadata is tagged with pii_present=true and pii_types=[...] for downstream filtering.')

heading2(doc, '12.2 Query-Time RBAC (Access Control at Retrieval)')
body(doc, 'Access control is enforced server-side at retrieval time. Users cannot override it. '
     'The system resolves user permissions from the IAM/Identity token and builds mandatory '
     'metadata filters that are injected into every vector store query.')

code_block(doc, """
User JWT validated by Cloud IAP
  → Resolve from IAM:
      user.departments = ["retail", "mortgages"]
      user.clearance_level = CONFIDENTIAL
      user.data_classifications_allowed = [PUBLIC, INTERNAL, CONFIDENTIAL]

Mandatory retrieval filter (injected server-side):
  {
    "data_classification": { "$in": ["PUBLIC", "INTERNAL", "CONFIDENTIAL"] },
    "tenant_id": "lbg-retail",
    "department_access": { "$in": ["retail", "mortgages", "all"] }
  }

Audit log entry written for every query:
  event: query.access_controlled
  docs_requested: 20
  docs_filtered_by_rbac: 5    (RESTRICTED docs silently excluded)
  filters_applied: {...}
""")

heading2(doc, '12.3 Immutable Audit Log (FCA Compliance)')
body(doc, 'A separate audit log service maintains an append-only table in AlloyDB with WAL '
     'archiving to GCS (immutable object storage). The main application cannot UPDATE or '
     'DELETE audit records.')

styled_table(doc,
    ['Field', 'Type', 'Purpose'],
    [
        ('audit_id',    'UUID (server-generated)',  'Primary key'),
        ('event_type',  'Enum',                     'QUERY | DOCUMENT_INGESTED | ACCESS_DENIED | CONFIG_CHANGE | ADMIN_ACTION'),
        ('timestamp',   'ISO8601 (server time)',     'Server-side clock — not client-supplied'),
        ('user_id',     'Hashed identifier',         'Never raw user ID'),
        ('tenant_id',   'String',                    'Business unit isolation'),
        ('resource_id', 'UUID',                      'query_id / document_id / etc.'),
        ('outcome',     'Enum',                      'SUCCESS | DENIED | ERROR'),
        ('details',     'JSONB (sanitised)',          'No raw PII, no raw query content'),
        ('trace_id',    'UUID',                       'Links to OTel trace for full reconstruction'),
        ('checksum',    'HMAC-SHA256',               'Tamper detection — verified on read'),
    ],
    col_widths=[1.5, 1.8, 3.2]
)

heading2(doc, '12.4 Data Residency')
body(doc, 'All GCP services are deployed in europe-west2 (London). VPC Service Controls enforce '
     'a data perimeter around all storage services (AlloyDB, Cloud Storage, Vertex AI, '
     'Secret Manager). Data cannot egress outside this perimeter without explicit policy exception. '
     'This satisfies UK GDPR and FCA data residency requirements.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — RESILIENCE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '13. Resilience Architecture')

heading2(doc, '13.1 Circuit Breaker Configuration')
styled_table(doc,
    ['Component', 'Failure Threshold', 'Open Duration', 'Fallback'],
    [
        ('Vertex AI Gemini (LLM)',         '5 failures / 30s',  '60s', 'Gemini 1.5 Pro → cached response'),
        ('Vertex AI Embeddings',           '5 failures / 30s',  '60s', 'text-multilingual-embedding-002'),
        ('AlloyDB pgvector',               '3 failures / 30s',  '60s', 'Vertex AI Vector Search (if configured)'),
        ('Cohere Reranker',                '5 failures / 60s',  '120s','Cross-encoder reranker → skip reranking'),
        ('Neo4j (Graph store)',            '3 failures / 30s',  '120s','Skip graph retrieval, use dense+sparse only'),
        ('Memorystore Redis (cache)',       '3 failures / 30s',  '60s', 'Skip cache (degrade gracefully)'),
    ],
    col_widths=[2.2, 1.6, 1.2, 2.5]
)

heading2(doc, '13.2 Retry Policies')
styled_table(doc,
    ['Operation', 'Max Attempts', 'Backoff', 'Base Delay', 'Retry On', 'Do Not Retry'],
    [
        ('Embedding API call',  '3', 'Exponential + jitter', '500ms', '429, 500, 502, 503, 504', '400, 401, 403'),
        ('LLM generation',      '3', 'Exponential + jitter', '1000ms','429, 500, 503',            '400, 401, 403'),
        ('Vector store query',  '3', 'Linear',               '200ms', 'ConnectionError, Timeout',  'InvalidQuery'),
        ('Ingestion stage',     '3', 'Exponential',          '2000ms','Any transient error',       'ValidationError → DLQ'),
    ],
    col_widths=[1.8, 1.1, 1.5, 1.0, 1.8, 1.3]
)

heading2(doc, '13.3 SLO Targets')
styled_table(doc,
    ['SLO', 'Target', 'Measurement Window', 'Error Budget'],
    [
        ('P50 end-to-end latency',  '< 500ms',  'Rolling 7 days', '—'),
        ('P95 end-to-end latency',  '< 2s',     'Rolling 7 days', '—'),
        ('P99 end-to-end latency',  '< 5s',     'Rolling 7 days', '—'),
        ('Error rate',              '< 0.1%',   'Rolling 7 days', '0.1% = 4.3min/month'),
        ('Faithfulness score avg',  '> 0.85',   'Rolling 7 days', '—'),
        ('Ingestion success rate',  '> 99.5%',  'Rolling 7 days', '0.5% tolerance'),
        ('Cache hit rate',          '> 20%',    'Rolling 7 days', 'Target, not hard SLO'),
    ],
    col_widths=[2.2, 1.3, 1.8, 2.2]
)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — EVALUATION FRAMEWORK
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '14. Evaluation Framework')

heading2(doc, '14.1 RAGAS Metrics — Definition & Computation')
styled_table(doc,
    ['Metric', 'Definition', 'Computation Method', 'Threshold'],
    [
        ('Faithfulness',        'Does the answer contain only claims supported by the context?',
                                'NLI model: |supported claims| / |total claims in answer|', '≥ 0.85'),
        ('Answer Relevancy',    'Is the answer relevant to the question?',
                                'avg cosine(answer_embed, generated_questions_from_answer)', '≥ 0.80'),
        ('Context Precision',   'Are the retrieved documents relevant?',
                                '|relevant docs in top-k| / |top-k|',                       '≥ 0.80'),
        ('Context Recall',      'Were all relevant documents retrieved?',
                                '|answer sentences in context| / |total answer sentences|',  '≥ 0.75'),
        ('Answer Correctness',  'Is the answer factually correct vs ground truth?',
                                'F1(answer, ground_truth) + semantic_similarity',            '≥ 0.80'),
        ('Groundedness',        'Is the answer grounded in the retrieved evidence?',
                                'Vertex AI Evaluation Service: LLM judge',                  '≥ 0.85'),
    ],
    col_widths=[1.6, 2.0, 2.0, 0.9]
)

heading2(doc, '14.2 Online Evaluation (Async, Per Request)')
body(doc, 'After every response is delivered to the user, an evaluation event is published to '
     'Pub/Sub (rag.eval.pending). The evaluation worker processes this asynchronously — it does '
     'not block the response. Results are stored in AlloyDB and emitted as Cloud Monitoring metrics.')

heading2(doc, '14.3 Offline Evaluation (CI/CD Gate, Golden QA Sets)')
body(doc, 'Before any deployment, the CI/CD pipeline runs the full RAGAS evaluation suite against '
     'curated golden QA sets stored in GCS. The deployment is blocked if:')
bullet(doc, 'Any metric falls below the absolute threshold defined above')
bullet(doc, 'Any metric regresses more than 5% relative to the current production baseline')
bullet(doc, 'The faithfulness score on compliance-sensitive question categories falls below 0.90')

body(doc, 'Golden QA sets are maintained per business domain (retail banking, mortgages, insurance) '
     'and are version-controlled in GCS alongside their expected answers and source documents.')

heading2(doc, '14.4 Vertex AI Experiments Integration')
body(doc, 'Every evaluation run (online and offline) is logged as a Vertex AI Experiment run, '
     'enabling: metric trending over time, A/B comparison between prompt versions, chunking '
     'strategy comparisons, and embedding model upgrade impact analysis.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 15 — CI/CD FOR RAG
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '15. CI/CD for RAG')

heading2(doc, '15.1 Cloud Build Pipeline Stages')
styled_table(doc,
    ['Stage', 'Step', 'Action', 'Gate: Fail = ?'],
    [
        ('Static', '1', 'Config schema validation (Pydantic)',            'Block merge'),
        ('Static', '2', 'Prompt template linting',                        'Block merge'),
        ('Static', '3', 'Dependency vulnerability scan (pip-audit)',       'Block merge'),
        ('Unit',   '4', 'Chunker unit tests (fixed inputs)',              'Block merge'),
        ('Unit',   '5', 'Embedding engine task_type assertion tests',     'Block merge'),
        ('Unit',   '6', 'Circuit breaker state machine tests',            'Block merge'),
        ('Integ',  '7', 'Ingestion pipeline (test corpus in GCS)',        'Block merge'),
        ('Integ',  '8', 'Retrieval from test AlloyDB index',             'Block merge'),
        ('Integ',  '9', 'End-to-end query (mocked Vertex AI)',           'Block merge'),
        ('Eval',   '10','Golden QA evaluation gate (RAGAS on full suite)','Block deploy'),
        ('Deploy', '11','Canary deployment to 5% traffic',               '—'),
        ('Deploy', '12','Monitor canary for 30 minutes (auto-rollback)',  'Auto-rollback on breach'),
        ('Deploy', '13','Promote to 100% traffic',                        '—'),
    ],
    col_widths=[0.9, 0.5, 3.0, 2.1]
)

heading2(doc, '15.2 Canary Auto-Rollback Triggers')
styled_table(doc,
    ['Metric', 'Rollback Threshold'],
    [
        ('Error rate',           '> 1%'),
        ('P95 latency',          '> 3s'),
        ('Faithfulness score',   '< 0.80'),
        ('Circuit breaker trips','> 3 in 5 minutes'),
    ],
    col_widths=[2.5, 4.0]
)

heading2(doc, '15.3 Blue-Green Index Migration (Embedding Model Changes)')
body(doc, 'When the embedding model changes (e.g. upgrading text-embedding-004 to a newer version), '
     'a full re-index is required. This is handled without downtime:')
bullet(doc, 'Re-embed the entire corpus into a "green" AlloyDB index (new model, RETRIEVAL_DOCUMENT)')
bullet(doc, 'Run RAGAS evaluation: green index vs current blue index on golden QA set')
bullet(doc, 'If green ≥ blue on all metrics: cut traffic atomically (config change, no redeploy)')
bullet(doc, 'Keep blue index for 48 hours for fast rollback if issues emerge')
bullet(doc, 'Drop blue index after 48-hour stability window')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 16 — IAM & IDENTITY
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '16. GCP IAM & Identity Design')
body(doc, 'All service accounts follow the principle of least privilege. '
     'No long-lived service account keys are used anywhere. '
     'GKE workloads use Workload Identity. Cloud Run uses IAM-bound service accounts.')

styled_table(doc,
    ['Service Account', 'Used By', 'Key IAM Bindings'],
    [
        ('rag-api@PROJECT',       'Cloud Run / GKE API pods',
         'aiplatform.user, pubsub.publisher, secretmanager.secretAccessor, cloudtrace.agent, monitoring.metricWriter, logging.logWriter, alloydb.client'),
        ('rag-ingestion@PROJECT', 'Cloud Composer DAG tasks',
         'aiplatform.user, storage.objectViewer, dlp.user, pubsub.subscriber, pubsub.publisher, alloydb.client'),
        ('rag-eval@PROJECT',      'Evaluation worker (Cloud Run)',
         'aiplatform.user, aiplatform.experimentAdmin, alloydb.client'),
        ('rag-cicd@PROJECT',      'Cloud Build pipeline',
         'run.admin, container.developer, storage.objectAdmin, aiplatform.user (eval gate)'),
    ],
    col_widths=[1.8, 1.5, 3.2]
)

body(doc, 'VPC Service Controls perimeter encloses: Vertex AI, AlloyDB, Cloud Storage, '
     'Secret Manager. Access is restricted to rag-* service accounts from within the LBG VPC '
     'only. All public internet egress to data services is blocked at the perimeter level.')

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 17 — FULL TECHNOLOGY STACK
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '17. Complete GCP Technology Stack')

styled_table(doc,
    ['Component', 'GCP Service', 'GCP Region', 'Notes'],
    [
        ('Primary LLM',             'Vertex AI Gemini 2.0 Flash',         'europe-west2', 'Default; low latency, cost-effective'),
        ('LLM fallback',            'Vertex AI Gemini 1.5 Pro',           'europe-west2', 'Complex reasoning; higher cost'),
        ('Embeddings (primary)',     'text-embedding-004',                 'europe-west2', 'task_type enforced per stage'),
        ('Embeddings (fallback/ML)','text-multilingual-embedding-002',    'europe-west2', 'Non-EN content, quota failover'),
        ('Vector store (primary)',   'AlloyDB + pgvector (HNSW)',          'europe-west2', '≤ 50M vectors; hybrid SQL+vector'),
        ('Vector store (scale-out)', 'Vertex AI Vector Search',            'europe-west2', '>50M vectors; streaming updates'),
        ('Document store',           'AlloyDB (same cluster)',             'europe-west2', 'Full chunk text + metadata'),
        ('Lineage store',            'AlloyDB (lineage schema)',           'europe-west2', 'JOIN-able with doc + vector tables'),
        ('Graph store',              'Neo4j Community on GKE Autopilot',  'europe-west2', 'Entity graph for Graph RAG'),
        ('Semantic cache',           'Memorystore for Redis (HA)',         'europe-west2', 'Embedding-based query cache'),
        ('Message queue',            'Cloud Pub/Sub',                      'Global',       'Dead-letter topics native'),
        ('Ingestion orchestration',  'Cloud Composer 2 (managed Airflow)','europe-west2', 'DAG-based ingestion pipeline'),
        ('PII detection',            'Cloud DLP',                          'Global API',   'UK info types built-in'),
        ('API runtime',              'Cloud Run',                          'europe-west2', 'min-instances=2 for warmth'),
        ('Worker runtime',           'GKE Autopilot',                     'europe-west2', 'Neo4j, Grafana, eval workers'),
        ('Object storage',           'Cloud Storage',                      'europe-west2', 'Raw docs, prompts, golden QA'),
        ('Distributed tracing',      'Cloud Trace (OTel-native)',          'Global',       'OTel Collector on GKE'),
        ('Metrics',                  'Cloud Monitoring + Managed Prometheus','Global',     'Custom metric namespace: rag/'),
        ('Structured logging',       'Cloud Logging (JSON)',               'europe-west2', 'Log-based metrics from RAG fields'),
        ('Dashboards',               'Grafana on GKE (Cloud Monitoring src)','europe-west2','Full RAG operations dashboard'),
        ('Alerting',                 'Cloud Monitoring Alerting → PagerDuty','Global',    'Notification channels configured'),
        ('Evaluation (online)',       'RAGAS + Vertex AI Evaluation Service','europe-west2','Async per-request evaluation'),
        ('Evaluation (offline)',      'RAGAS + Vertex AI Experiments',     'europe-west2', 'CI/CD gate on golden QA sets'),
        ('CI/CD',                    'Cloud Build + Artifact Registry',    'europe-west2', 'Eval gate + canary deploy'),
        ('Secrets',                  'Secret Manager',                     'europe-west2', 'Versioned; no keys in code/env'),
        ('Identity',                 'Workload Identity + Cloud IAM',      'Global',       'No long-lived service account keys'),
        ('Network security',         'VPC Service Controls',               'Global policy','Data perimeter around all storage'),
        ('Infrastructure as Code',   'Terraform (google provider)',         '—',            'All resources in code'),
    ],
    col_widths=[1.9, 2.2, 1.3, 2.1]
)

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 18 — PROJECT STRUCTURE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '18. Complete Project Structure')

code_block(doc, """
lbg-rag-platform/
│
├── config/
│   ├── rag_config.yaml              # master configuration (schema-validated)
│   ├── rag_config.schema.json       # Pydantic / JSON Schema
│   ├── environments/
│   │   ├── development.yaml         # local pgvector, mocked Vertex AI
│   │   ├── staging.yaml             # europe-west2, real Vertex AI, test quota
│   │   └── production.yaml          # europe-west2, full quota, VPC SC
│   └── prompts/
│       ├── registry.yaml            # prompt version registry
│       └── templates/
│           ├── lbg-default/
│           │   ├── v2.3.1.jinja2
│           │   └── v2.3.0.jinja2
│           ├── rag_system.jinja2
│           ├── groundedness_eval.jinja2
│           └── query_transform.jinja2
│
├── rag/
│   ├── core/
│   │   ├── config.py                # loader, validator, Secret Manager injection
│   │   ├── registry.py              # plugin registry (all providers)
│   │   ├── pipeline.py              # top-level query orchestrator
│   │   ├── context.py               # request context (trace, user, tenant, RBAC)
│   │   └── exceptions.py            # typed exception hierarchy
│   │
│   ├── ingestion/
│   │   ├── pipeline.py
│   │   ├── loaders/                 # pdf, docx, confluence, sharepoint, s3, gcs
│   │   ├── parsers/                 # text, table, image_ocr
│   │   ├── cleaners/                # text_normaliser, structure_extractor
│   │   ├── enrichers/               # ner, topic_classifier, keyword_extractor
│   │   └── deduplicator.py
│   │
│   ├── security/
│   │   ├── cloud_dlp.py             # Cloud DLP wrapper (UK PII types)
│   │   ├── data_classifier.py       # PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED
│   │   ├── access_control.py        # RBAC filter builder (Cloud IAM-aware)
│   │   └── audit_logger.py          # Immutable AlloyDB audit log writer
│   │
│   ├── chunking/
│   │   ├── base.py                  # ChunkingStrategy protocol
│   │   ├── engine.py                # routes to strategy; enforces metadata
│   │   ├── fixed.py
│   │   ├── sentence.py
│   │   ├── semantic.py
│   │   ├── hierarchical.py          # DEFAULT strategy
│   │   ├── recursive.py
│   │   ├── agentic.py               # Gemini 2.0 Flash boundary detection
│   │   ├── ast_based.py
│   │   ├── late_chunking.py
│   │   └── raptor.py
│   │
│   ├── embedding/
│   │   ├── base.py                  # EmbeddingProvider protocol
│   │   ├── engine.py                # enforces task_type; batch manager; fallback
│   │   ├── cache.py                 # embedding result cache (Memorystore)
│   │   ├── matryoshka.py            # dimension truncation utilities
│   │   └── providers/
│   │       ├── vertex_ai.py         # text-embedding-004 + multilingual-002
│   │       └── cohere.py            # secondary fallback
│   │
│   ├── storage/
│   │   ├── vector/
│   │   │   ├── base.py              # VectorStore protocol
│   │   │   ├── alloydb_pgvector.py  # primary (HNSW)
│   │   │   └── vertex_vector_search.py  # scale-out
│   │   ├── document/
│   │   │   ├── alloydb.py           # chunk text + metadata
│   │   │   └── gcs.py               # raw document blobs
│   │   ├── graph/
│   │   │   └── neo4j.py
│   │   ├── cache/
│   │   │   ├── semantic_cache.py    # embedding cosine cache (Redis)
│   │   │   └── exact_cache.py       # hash-based (Redis)
│   │   └── lineage/
│   │       └── alloydb_lineage.py   # full provenance recording
│   │
│   ├── retrieval/
│   │   ├── base.py                  # Retriever protocol
│   │   ├── engine.py                # strategy selector
│   │   ├── dense.py                 # AlloyDB pgvector ANN
│   │   ├── sparse/
│   │   │   ├── vertex_ai_search.py  # BM25 via Vertex AI Search
│   │   │   └── bm25_local.py        # local fallback
│   │   ├── hybrid.py                # RRF fusion
│   │   ├── graph.py                 # Neo4j entity traversal
│   │   ├── colbert.py               # late interaction
│   │   ├── flare.py                 # forward-looking active retrieval
│   │   └── filters.py               # RBAC-aware metadata filter builder
│   │
│   ├── augmentation/
│   │   ├── query_transformers/
│   │   │   ├── hyde.py              # hypothetical document embedding
│   │   │   ├── step_back.py
│   │   │   ├── multi_query.py
│   │   │   └── sub_query.py
│   │   ├── rerankers/
│   │   │   ├── base.py
│   │   │   ├── cohere.py
│   │   │   ├── cross_encoder.py
│   │   │   └── llm_reranker.py      # Gemini 2.0 Flash as reranker
│   │   ├── compressors/
│   │   │   ├── llm_extract.py
│   │   │   ├── sentence_window.py
│   │   │   └── map_reduce.py
│   │   └── document_grader.py       # CRAG: RELEVANT/IRRELEVANT/AMBIGUOUS
│   │
│   ├── generation/
│   │   ├── base.py                  # LLMProvider protocol
│   │   ├── engine.py                # fallback chain; streaming
│   │   ├── prompt_builder.py        # Jinja2 template renderer
│   │   ├── prompt_registry.py       # GCS-backed versioned prompts
│   │   ├── citation_injector.py
│   │   ├── response_validator.py    # guardrails + hallucination detection
│   │   └── providers/
│   │       ├── vertex_ai_gemini.py  # Gemini 2.0 Flash + 1.5 Pro
│   │       └── anthropic.py         # emergency fallback
│   │
│   ├── patterns/
│   │   ├── base.py                  # RAGPattern protocol
│   │   ├── router.py                # adaptive pattern selector
│   │   ├── naive.py
│   │   ├── advanced.py
│   │   ├── crag.py
│   │   ├── self_rag.py
│   │   ├── fusion.py
│   │   ├── graph_rag.py
│   │   ├── hierarchical_rag.py
│   │   ├── agentic.py
│   │   ├── speculative.py
│   │   └── raptor.py
│   │
│   ├── agents/
│   │   ├── base.py
│   │   ├── supervisor.py
│   │   ├── router_agent.py
│   │   ├── retriever_agent.py
│   │   ├── critic_agent.py
│   │   ├── synthesiser_agent.py
│   │   ├── state_machine.py
│   │   └── tools/
│   │       ├── rag_tool.py
│   │       ├── sql_tool.py
│   │       ├── api_tool.py
│   │       └── calculator_tool.py
│   │
│   └── observability/
│       ├── tracing.py               # OTel → Cloud Trace
│       ├── logging.py               # structlog → JSON → Cloud Logging
│       ├── metrics.py               # OTel metrics → Cloud Monitoring
│       └── evaluation/
│           ├── online_evaluator.py
│           ├── offline_evaluator.py
│           ├── ragas_adapter.py
│           ├── vertex_eval.py       # Vertex AI Evaluation Service
│           └── metrics_store.py
│
├── api/
│   ├── main.py                      # FastAPI application
│   ├── routers/
│   │   ├── query.py                 # POST /v1/query
│   │   ├── ingest.py                # POST /v1/ingest
│   │   ├── health.py                # GET /health, /ready, /metrics
│   │   └── admin.py                 # config reload, cache clear, index status
│   ├── middleware/
│   │   ├── correlation_id.py
│   │   ├── auth.py                  # Cloud IAP JWT validation
│   │   └── rate_limiter.py
│   └── schemas/                     # Pydantic request/response models
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── evaluation/
│   │   ├── golden_qa/
│   │   │   ├── retail_banking.json
│   │   │   ├── mortgages.json
│   │   │   └── insurance.json
│   │   └── run_eval.py
│   └── load/
│       └── locustfile.py
│
├── dags/                            # Cloud Composer DAGs
│   ├── rag_ingestion.py
│   ├── rag_reindex.py               # re-embed after model change
│   └── rag_eval_batch.py            # nightly offline evaluation
│
└── infrastructure/
    ├── terraform/
    │   └── gcp/
    │       ├── main.tf
    │       ├── alloydb.tf
    │       ├── vertex_ai.tf
    │       ├── pubsub.tf
    │       ├── cloud_run.tf
    │       ├── gke.tf
    │       ├── cloud_composer.tf
    │       ├── memorystore.tf
    │       ├── secret_manager.tf
    │       ├── iam.tf
    │       ├── vpc_sc.tf
    │       └── monitoring.tf
    ├── cloud-build/
    │   └── cloudbuild.yaml
    └── otel-collector/
        └── config.yaml
""")

page_break(doc)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 19 — CONFIGURATION REFERENCE
# ══════════════════════════════════════════════════════════════════════════════
heading1(doc, '19. Master Configuration Reference')
body(doc, 'The master YAML configuration is schema-validated at startup. Environment variables '
     'are injected via ${VAR_NAME} syntax, resolved from Secret Manager at boot. '
     'All behavioural decisions are driven by this config — no behavioural logic lives in code.')

code_block(doc, """
# rag_config.yaml — Master Configuration
# All ${VAR} references resolved from Secret Manager at startup

pipeline:
  name: "lbg-rag-platform"
  version: "1.0.0"
  pattern: "adaptive"          # naive|advanced|crag|self_rag|fusion|graph|
                               # hierarchical|agentic|raptor|adaptive

ingestion:
  loaders:
    - type: pdf
    - type: docx
    - type: confluence
      base_url: ${CONFLUENCE_URL}
    - type: sharepoint
      tenant_id: ${SHAREPOINT_TENANT_ID}
    - type: gcs
      bucket: rag-documents-raw
  cleaner:
    remove_headers_footers: true
    normalize_whitespace: true
    detect_language: true
  deduplication:
    strategy: semantic
    threshold: 0.97

chunking:
  strategy: hierarchical       # DEFAULT — swap with one line
  fixed:
    chunk_size: 512
    overlap: 64
    unit: tokens
  semantic:
    breakpoint_type: percentile
    breakpoint_threshold: 95
  hierarchical:
    parent_chunk_size: 2048
    child_chunk_size: 512
    overlap: 64
  recursive:
    separators: ["\\n\\n", "\\n", ". ", " "]
    chunk_size: 512
  agentic:
    model: gemini-2.0-flash-001
    task: "Generate the question this passage answers"

embedding:
  provider: vertex_ai
  model: text-embedding-004
  project_id: ${GCP_PROJECT_ID}
  location: europe-west2
  task_types:
    ingestion: RETRIEVAL_DOCUMENT      # ENFORCED — not caller-configurable
    query: RETRIEVAL_QUERY             # ENFORCED — not caller-configurable
    cache_lookup: SEMANTIC_SIMILARITY
    evaluation: SEMANTIC_SIMILARITY
    clustering: CLUSTERING
    classification: CLASSIFICATION
  dimensions:
    default: 768
    fast_path: 256
  batching:
    max_batch_size: 250
    max_concurrent_batches: 10
  fallback:
    model: text-multilingual-embedding-002

storage:
  vector_store:
    provider: alloydb_pgvector
    connection_string: ${ALLOYDB_CONNECTION}
    database: rag_platform
    index:
      type: hnsw
      hnsw: {m: 16, ef_construction: 64, ef_search: 40}
    dimensions: 768
    distance_metric: cosine
  document_store:
    provider: alloydb
    connection_string: ${ALLOYDB_CONNECTION}
  graph_store:
    provider: neo4j
    uri: ${NEO4J_URI}
  cache:
    provider: redis
    url: ${REDIS_URL}
    ttl_seconds: 3600
    semantic_cache: true
    semantic_threshold: 0.97
    semantic_dimensions: 256

retrieval:
  strategy: hybrid
  top_k: 20
  dense:
    weight: 0.7
  sparse:
    provider: vertex_ai_search
    weight: 0.3
  hybrid_fusion: rrf
  rrf_k_constant: 60
  metadata_filters: true
  mmr:
    enabled: true
    lambda: 0.5

augmentation:
  reranker:
    enabled: true
    provider: cohere
    model: rerank-english-v3.0
    top_n: 5
    fallback_provider: cross_encoder
  context_compression:
    enabled: true
    strategy: llm_extract
    model: gemini-2.0-flash-001
  query_transformation:
    hyde: false
    step_back: true
    multi_query: true
    multi_query_count: 3

generation:
  provider: vertex_ai
  model: gemini-2.0-flash-001
  location: europe-west2
  temperature: 0.1
  max_output_tokens: 2048
  system_prompt_template: "lbg-default"
  prompt_version: "v2.3.1"
  citation_mode: inline
  fallback:
    provider: vertex_ai
    model: gemini-1.5-pro-002
  stream: true

agents:
  pattern: react
  max_iterations: 10
  confidence_threshold: 0.85
  hitl_gates:
    after_planning: false
    after_draft: false
    compliance_topics: true       # always HITL for regulated topics
  tools:
    - rag_tool
    - sql_tool
    - api_tool
    - calculator_tool

security:
  pii_detection:
    provider: cloud_dlp
    project_id: ${GCP_PROJECT_ID}
    inspection_template: lbg-rag-uk-pii-template
    deidentification_template: lbg-rag-deident-template
  data_classification:
    enabled: true
    default: INTERNAL
  rbac:
    enabled: true
    enforce_at_retrieval: true
  audit_log:
    enabled: true
    immutable: true
    wal_archive_bucket: lbg-rag-audit-archive

observability:
  tracing:
    provider: opentelemetry
    exporter: cloud_trace
    sampling_rate: 0.1            # 100% staging, 10% production
    always_sample_errors: true
    always_sample_slow_requests_ms: 3000
  logging:
    level: INFO
    structured: true
    exporter: cloud_logging
  metrics:
    provider: opentelemetry
    exporter: cloud_monitoring
    namespace: custom.googleapis.com/rag
  evaluation:
    online:
      enabled: true
      async: true
      sample_rate: 0.1
    offline:
      golden_qa_bucket: lbg-rag-eval
      run_on_deploy: true
      thresholds:
        faithfulness: 0.85
        answer_relevancy: 0.80
        context_precision: 0.80

resilience:
  circuit_breaker:
    enabled: true
    failure_threshold: 5
    window_seconds: 30
    open_duration_seconds: 60
    success_threshold_to_close: 2
  retry:
    embedding:
      max_attempts: 3
      base_delay_ms: 500
      backoff: exponential
      jitter: true
    llm:
      max_attempts: 3
      base_delay_ms: 1000
      backoff: exponential
      jitter: true
""")

# ══════════════════════════════════════════════════════════════════════════════
# FINAL PAGE — IMPLEMENTATION ROADMAP
# ══════════════════════════════════════════════════════════════════════════════
page_break(doc)
heading1(doc, 'Implementation Roadmap')
body(doc, 'Recommended build order — each phase delivers a working, testable increment.')

styled_table(doc,
    ['Phase', 'Deliverable', 'Key Components', 'Exit Criteria'],
    [
        ('1 — Foundation',
         'GCP infrastructure + config layer',
         'Terraform: AlloyDB, Vertex AI, Pub/Sub, Secret Manager, IAM, VPC SC\nConfig loader, plugin registry, Pydantic schema',
         'terraform apply succeeds in staging. Config loads and validates.'),
        ('2 — Ingest & Embed',
         'Ingestion pipeline with Gemini Embeddings',
         'Cloud Composer DAG (all 15 stages)\nCloud DLP integration\ntext-embedding-004 (RETRIEVAL_DOCUMENT)\nAlloyDB pgvector storage + lineage',
         'Documents indexed end-to-end. Lineage records created. DLP scan active. task_type=RETRIEVAL_DOCUMENT confirmed in tests.'),
        ('3 — Retrieve',
         'Hybrid retrieval with observability',
         'Dense (AlloyDB HNSW)\nSparse (Vertex AI Search)\nRRF fusion\nSemantic cache (Memorystore)\nOTel spans from day one',
         'Retrieval latency p95 < 150ms. Hybrid fusion working. Cache hit rate > 0%. All spans visible in Cloud Trace.'),
        ('4 — Generate',
         'End-to-end RAG with Advanced pattern',
         'Vertex AI Gemini 2.0 Flash\nVersioned prompt registry\nCohere reranker\nContext compressor\nResponse validator + citation injector',
         'End-to-end query returns cited answer. Faithfulness > 0.85 on golden QA set. Full trace visible.'),
        ('5 — Observability',
         'Full observability stack operational',
         'Cloud Monitoring 40+ metrics\nGrafana dashboard\nAlert policies wired to PagerDuty\nEvaluation worker (async RAGAS)\nCloud Build eval gate',
         'Dashboard live. Alerts tested. CI/CD eval gate blocking on regression.'),
        ('6 — All Patterns',
         'All 9 RAG patterns operational',
         'CRAG, Self-RAG, Fusion, Graph RAG, Hierarchical, Agentic, RAPTOR\nAdaptive router\nNeo4j graph store',
         'Each pattern tested on domain-specific golden QA set. Adaptive router routes correctly.'),
        ('7 — Agent Layer',
         'Full multi-agent system',
         'Supervisor, Router, Retriever, Critic, Synthesiser agents\nTool registry (RAG, SQL, API, Calculator)\nHITL gates for compliance topics',
         'Multi-hop agent queries resolved correctly. HITL gates trigger on compliance topics. Critic catches hallucinations.'),
        ('8 — Production Hardening',
         'Production-ready platform',
         'Load testing (Locust)\nChaos testing (circuit breaker validation)\nCanary deployment pipeline\nBlue-green index migration tested\nFCA audit log review',
         'SLOs met under load. Chaos tests pass. Canary auto-rollback demonstrated. Audit log reviewed by compliance team.'),
    ],
    col_widths=[1.3, 1.6, 2.4, 2.2]
)

# Save
out = '/home/user/rag/LBG_RAG_Platform_Architecture.docx'
doc.save(out)
print(f'Document saved: {out}')
