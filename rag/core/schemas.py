"""
Pydantic v2 schema for the entire RAG platform configuration.

Design rules:
  - Every model is frozen=True — config is immutable after load.
  - Sensitive fields (connection strings, API keys) use SecretStr.
  - All enums use str mixins so YAML string values deserialise correctly.
  - Cross-field invariants are enforced with model_validator(mode='after').
  - extra='ignore' on RAGConfig for forward-compatibility with new YAML keys.
  - All fields have explicit descriptions for documentation generation.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


# ── Enums ─────────────────────────────────────────────────────────────────────


class RAGPattern(str, Enum):
    NAIVE = "naive"
    ADVANCED = "advanced"
    CRAG = "crag"
    SELF_RAG = "self_rag"
    FUSION = "fusion"
    GRAPH = "graph"
    HIERARCHICAL = "hierarchical"
    AGENTIC = "agentic"
    SPECULATIVE = "speculative"
    RAPTOR = "raptor"
    ADAPTIVE = "adaptive"


class ChunkingStrategy(str, Enum):
    FIXED = "fixed"
    SENTENCE = "sentence"
    SEMANTIC = "semantic"
    HIERARCHICAL = "hierarchical"
    RECURSIVE = "recursive"
    AGENTIC = "agentic"
    AST = "ast"
    LATE = "late_chunking"
    RAPTOR = "raptor"


class EmbeddingProvider(str, Enum):
    VERTEX_AI = "vertex_ai"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    BEDROCK = "bedrock"


class EmbeddingTaskType(str, Enum):
    RETRIEVAL_DOCUMENT = "RETRIEVAL_DOCUMENT"
    RETRIEVAL_QUERY = "RETRIEVAL_QUERY"
    SEMANTIC_SIMILARITY = "SEMANTIC_SIMILARITY"
    CLASSIFICATION = "CLASSIFICATION"
    CLUSTERING = "CLUSTERING"
    QUESTION_ANSWERING = "QUESTION_ANSWERING"
    FACT_VERIFICATION = "FACT_VERIFICATION"


class VectorStoreProvider(str, Enum):
    ALLOYDB_PGVECTOR = "alloydb_pgvector"
    VERTEX_VECTOR_SEARCH = "vertex_ai_vector_search"
    PGVECTOR = "pgvector"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"
    CHROMA = "chroma"
    FAISS = "faiss"


class DocumentStoreProvider(str, Enum):
    ALLOYDB = "alloydb"
    POSTGRES = "postgres"
    FIRESTORE = "firestore"


class GraphStoreProvider(str, Enum):
    NEO4J = "neo4j"
    NEPTUNE = "neptune"


class CacheProvider(str, Enum):
    REDIS = "redis"
    IN_MEMORY = "in_memory"


class DistanceMetric(str, Enum):
    COSINE = "cosine"
    L2 = "l2"
    INNER_PRODUCT = "inner_product"
    DOT_PRODUCT = "dot_product"


class RetrievalStrategy(str, Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    GRAPH = "graph"
    SQL = "sql"
    ENSEMBLE = "ensemble"


class HybridFusion(str, Enum):
    RRF = "rrf"
    LINEAR = "linear"
    CASCADE = "cascade"


class SparseProvider(str, Enum):
    VERTEX_AI_SEARCH = "vertex_ai_search"
    BM25 = "bm25"
    ELASTICSEARCH = "elasticsearch"


class RerankerProvider(str, Enum):
    COHERE = "cohere"
    CROSS_ENCODER = "cross_encoder"
    LLM = "llm"


class CompressionStrategy(str, Enum):
    LLM_EXTRACT = "llm_extract"
    SENTENCE_WINDOW = "sentence_window"
    MAP_REDUCE = "map_reduce"


class LLMProvider(str, Enum):
    VERTEX_AI = "vertex_ai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    BEDROCK = "bedrock"
    OPENAI = "openai"


class CitationMode(str, Enum):
    INLINE = "inline"
    FOOTNOTE = "footnote"
    NONE = "none"


class AgentPattern(str, Enum):
    REACT = "react"
    PLAN_EXECUTE = "plan_execute"
    REFLECTION = "reflection"
    SUPERVISOR = "supervisor"


class DataClassificationLevel(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"


class PIIAction(str, Enum):
    REDACT = "REDACT"
    REPLACE_WITH_INFO_TYPE = "REPLACE_WITH_INFO_TYPE"
    PSEUDONYMIZE = "PSEUDONYMIZE"
    MASK = "MASK"
    ENCRYPT = "ENCRYPT"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RetryBackoff(str, Enum):
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


# ── Pipeline ──────────────────────────────────────────────────────────────────


class PipelineConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(default="lbg-rag-platform", description="Platform instance name")
    version: str = Field(default="1.0.0", description="Platform version string")
    pattern: RAGPattern = Field(
        default=RAGPattern.ADAPTIVE,
        description="Default RAG pattern. 'adaptive' lets the router choose per query.",
    )


# ── Ingestion ─────────────────────────────────────────────────────────────────


class PDFLoaderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["pdf"] = "pdf"


class DocxLoaderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["docx"] = "docx"


class ConfluenceLoaderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["confluence"] = "confluence"
    base_url: str = Field(description="Confluence base URL, e.g. https://lbg.atlassian.net")
    space_keys: list[str] | None = Field(default=None, description="Limit to specific spaces")


class SharepointLoaderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["sharepoint"] = "sharepoint"
    tenant_id: str = Field(description="Azure AD tenant ID")
    site_url: str | None = None


class GCSLoaderConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["gcs"] = "gcs"
    bucket: str
    prefix: str | None = None


# Discriminated union — Pydantic uses `type` to pick the correct model.
LoaderConfig = Annotated[
    PDFLoaderConfig | DocxLoaderConfig | ConfluenceLoaderConfig | SharepointLoaderConfig | GCSLoaderConfig,
    Field(discriminator="type"),
]


class CleanerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    remove_headers_footers: bool = True
    normalize_whitespace: bool = True
    detect_language: bool = True
    min_content_length: int = Field(
        default=50,
        ge=0,
        description="Discard text segments shorter than this (avoids indexing boilerplate).",
    )


class DeduplicationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    strategy: Literal["exact", "semantic", "none"] = "semantic"
    threshold: float = Field(
        default=0.97,
        ge=0.0,
        le=1.0,
        description="Cosine similarity above which a document is considered duplicate.",
    )


class IngestionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    loaders: list[LoaderConfig] = Field(
        default_factory=lambda: [PDFLoaderConfig(), DocxLoaderConfig()],
        description="Ordered list of document loaders to enable.",
    )
    cleaner: CleanerConfig = Field(default_factory=CleanerConfig)
    deduplication: DeduplicationConfig = Field(default_factory=DeduplicationConfig)


# ── Chunking ──────────────────────────────────────────────────────────────────


class FixedChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    chunk_size: int = Field(default=512, ge=1, le=8192)
    overlap: int = Field(default=64, ge=0)
    unit: Literal["tokens", "chars", "words"] = "tokens"

    @model_validator(mode="after")
    def overlap_smaller_than_chunk(self) -> "FixedChunkingConfig":
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap ({self.overlap}) must be strictly less than chunk_size ({self.chunk_size})"
            )
        return self


class SentenceChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    min_sentences: int = Field(default=3, ge=1)
    max_sentences: int = Field(default=8, ge=1)

    @model_validator(mode="after")
    def min_less_than_max(self) -> "SentenceChunkingConfig":
        if self.min_sentences >= self.max_sentences:
            raise ValueError(
                f"min_sentences ({self.min_sentences}) must be less than "
                f"max_sentences ({self.max_sentences})"
            )
        return self


class SemanticChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    breakpoint_type: Literal["percentile", "standard_deviation", "interquartile"] = "percentile"
    breakpoint_threshold: float = Field(
        default=95.0,
        ge=0.0,
        le=100.0,
        description="Percentile of cosine-delta at which to split (for breakpoint_type=percentile).",
    )
    buffer_size: int = Field(
        default=1,
        ge=0,
        description="Number of surrounding sentences to include for context when computing similarity.",
    )


class HierarchicalChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    parent_chunk_size: int = Field(default=2048, ge=128, description="Token size of parent chunks.")
    child_chunk_size: int = Field(default=512, ge=64, description="Token size of child chunks.")
    overlap: int = Field(default=64, ge=0, description="Token overlap between adjacent child chunks.")

    @model_validator(mode="after")
    def sizes_consistent(self) -> "HierarchicalChunkingConfig":
        if self.child_chunk_size >= self.parent_chunk_size:
            raise ValueError(
                f"child_chunk_size ({self.child_chunk_size}) must be less than "
                f"parent_chunk_size ({self.parent_chunk_size})"
            )
        if self.overlap >= self.child_chunk_size:
            raise ValueError(
                f"overlap ({self.overlap}) must be less than "
                f"child_chunk_size ({self.child_chunk_size})"
            )
        return self


class RecursiveChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    separators: list[str] = Field(default=["\n\n", "\n", ". ", " "])
    chunk_size: int = Field(default=512, ge=1, le=8192)
    overlap: int = Field(default=64, ge=0)

    @model_validator(mode="after")
    def overlap_smaller_than_chunk(self) -> "RecursiveChunkingConfig":
        if self.overlap >= self.chunk_size:
            raise ValueError(
                f"overlap ({self.overlap}) must be less than chunk_size ({self.chunk_size})"
            )
        return self


class AgenticChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str = Field(default="gemini-2.0-flash-001")
    task_prompt: str = Field(
        default="Generate the single question this passage best answers.",
        description="Prompt used to elicit chunk-level question for boundary detection.",
    )
    max_chunk_size: int = Field(default=1024, ge=128)


class ASTChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    language: str = Field(
        default="python",
        description="Source language for AST parsing (python, java, typescript, go, etc.).",
    )
    max_chunk_size: int = Field(default=1024, ge=128)
    include_docstrings: bool = True


class RAPTORChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    leaf_chunk_size: int = Field(default=512, ge=64)
    cluster_method: Literal["umap_gmm", "kmeans"] = "umap_gmm"
    summary_model: str = Field(default="gemini-2.0-flash-001")
    max_levels: int = Field(default=3, ge=1, le=10)
    min_cluster_size: int = Field(default=5, ge=2)


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: ChunkingStrategy = Field(
        default=ChunkingStrategy.HIERARCHICAL,
        description="Active chunking strategy. All sub-configs are present; only the active one is used.",
    )
    fixed: FixedChunkingConfig = Field(default_factory=FixedChunkingConfig)
    sentence: SentenceChunkingConfig = Field(default_factory=SentenceChunkingConfig)
    semantic: SemanticChunkingConfig = Field(default_factory=SemanticChunkingConfig)
    hierarchical: HierarchicalChunkingConfig = Field(default_factory=HierarchicalChunkingConfig)
    recursive: RecursiveChunkingConfig = Field(default_factory=RecursiveChunkingConfig)
    agentic: AgenticChunkingConfig | None = None
    ast: ASTChunkingConfig | None = None
    raptor: RAPTORChunkingConfig | None = None

    @model_validator(mode="after")
    def required_sub_config_present(self) -> "ChunkingConfig":
        optional_strategies = {
            ChunkingStrategy.AGENTIC: (self.agentic, "agentic"),
            ChunkingStrategy.AST: (self.ast, "ast"),
            ChunkingStrategy.RAPTOR: (self.raptor, "raptor"),
        }
        sub_cfg, field_name = optional_strategies.get(self.strategy, (True, ""))
        if sub_cfg is None:
            raise ValueError(
                f"chunking.{field_name} config block is required when "
                f"chunking.strategy='{self.strategy.value}' but was not provided."
            )
        return self


# ── Embedding ─────────────────────────────────────────────────────────────────


class EmbeddingTaskTypes(BaseModel):
    """Maps each pipeline stage to its Gemini task_type.

    These defaults reflect the correct asymmetric usage of text-embedding-004.
    Overriding them is possible but strongly discouraged — the defaults are
    the correct values for retrieval tasks.
    """

    model_config = ConfigDict(frozen=True)

    ingestion: EmbeddingTaskType = Field(
        default=EmbeddingTaskType.RETRIEVAL_DOCUMENT,
        description="MUST be RETRIEVAL_DOCUMENT. Documents to be retrieved.",
    )
    query: EmbeddingTaskType = Field(
        default=EmbeddingTaskType.RETRIEVAL_QUERY,
        description="MUST be RETRIEVAL_QUERY. Queries issued against the index.",
    )
    cache_lookup: EmbeddingTaskType = Field(
        default=EmbeddingTaskType.SEMANTIC_SIMILARITY,
        description="Symmetric similarity for semantic cache lookups.",
    )
    evaluation: EmbeddingTaskType = Field(
        default=EmbeddingTaskType.SEMANTIC_SIMILARITY,
    )
    clustering: EmbeddingTaskType = Field(
        default=EmbeddingTaskType.CLUSTERING,
        description="Used by RAPTOR's cluster-then-summarise ingestion stage.",
    )
    classification: EmbeddingTaskType = Field(
        default=EmbeddingTaskType.CLASSIFICATION,
        description="Used by the query intent classifier.",
    )

    @model_validator(mode="after")
    def asymmetric_constraint(self) -> "EmbeddingTaskTypes":
        # The most critical invariant: ingestion and query must be asymmetric.
        if self.ingestion == self.query:
            raise ValueError(
                f"embedding.task_types.ingestion ({self.ingestion.value}) and "
                f"embedding.task_types.query ({self.query.value}) must differ. "
                f"Using the same task type for both defeats asymmetric retrieval."
            )
        return self


class EmbeddingDimensions(BaseModel):
    model_config = ConfigDict(frozen=True)
    default: int = Field(
        default=768,
        ge=64,
        le=3072,
        description="Full-fidelity embedding size used for index storage and retrieval.",
    )
    fast_path: int = Field(
        default=256,
        ge=64,
        description="Truncated size for latency-sensitive paths (semantic cache). "
        "Must be < default. Matryoshka truncation — no re-embedding needed.",
    )

    @model_validator(mode="after")
    def fast_path_smaller_than_default(self) -> "EmbeddingDimensions":
        if self.fast_path >= self.default:
            raise ValueError(
                f"embedding.dimensions.fast_path ({self.fast_path}) must be strictly less than "
                f"embedding.dimensions.default ({self.default})."
            )
        return self


class EmbeddingBatchingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_batch_size: int = Field(
        default=250,
        ge=1,
        le=2048,
        description="Max texts per Vertex AI embedding request. Hard limit is 250 for text-embedding-004.",
    )
    max_concurrent_batches: int = Field(default=10, ge=1, le=100)
    batch_timeout_ms: int = Field(default=5000, ge=100)


class EmbeddingRateLimits(BaseModel):
    model_config = ConfigDict(frozen=True)
    requests_per_minute: int = Field(default=1500, ge=1)
    tokens_per_minute: int = Field(default=4_000_000, ge=1000)
    retry_on_429: bool = True
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)


class EmbeddingFallbackConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    provider: EmbeddingProvider = EmbeddingProvider.VERTEX_AI
    model: str = Field(
        default="text-multilingual-embedding-002",
        description="Fallback model — used when primary model is unavailable or quota is exhausted.",
    )


class EmbeddingCostTrackingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    metric_name: str = "rag/embedding/cost_usd"
    price_per_1k_chars: float = Field(
        default=0.000025,
        ge=0.0,
        description="Update this when Vertex AI pricing changes. Used for cost metrics only.",
    )


class EmbeddingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: EmbeddingProvider = EmbeddingProvider.VERTEX_AI
    model: str = Field(default="text-embedding-004")
    project_id: str | None = Field(
        default=None,
        description="GCP project. Resolved from ${GCP_PROJECT_ID} at load time.",
    )
    location: str = Field(default="europe-west2", description="Vertex AI region.")
    task_types: EmbeddingTaskTypes = Field(default_factory=EmbeddingTaskTypes)
    dimensions: EmbeddingDimensions = Field(default_factory=EmbeddingDimensions)
    batching: EmbeddingBatchingConfig = Field(default_factory=EmbeddingBatchingConfig)
    rate_limits: EmbeddingRateLimits = Field(default_factory=EmbeddingRateLimits)
    fallback: EmbeddingFallbackConfig | None = Field(default_factory=EmbeddingFallbackConfig)
    cost_tracking: EmbeddingCostTrackingConfig = Field(default_factory=EmbeddingCostTrackingConfig)


# ── Storage ───────────────────────────────────────────────────────────────────


class HNSWIndexConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    m: int = Field(
        default=16,
        ge=2,
        le=100,
        description="Number of bi-directional connections per node. Higher = better recall, more RAM.",
    )
    ef_construction: int = Field(
        default=64,
        ge=4,
        description="Size of the candidate list during index construction. Higher = better quality.",
    )
    ef_search: int = Field(
        default=40,
        ge=4,
        description="Size of the candidate list during search. Must be >= retrieval.top_k.",
    )


class IVFFlatIndexConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    lists: int = Field(
        default=1000,
        ge=1,
        description="Number of inverted lists. Rule of thumb: sqrt(n_vectors).",
    )
    probes: int = Field(
        default=10,
        ge=1,
        description="Number of lists to probe at query time. Trade-off: recall vs latency.",
    )

    @model_validator(mode="after")
    def probes_within_lists(self) -> "IVFFlatIndexConfig":
        if self.probes > self.lists:
            raise ValueError(
                f"probes ({self.probes}) cannot exceed lists ({self.lists})"
            )
        return self


class VectorIndexConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["hnsw", "ivfflat"] = Field(
        default="hnsw",
        description="hnsw: better query recall, higher build cost. ivfflat: faster build, lower RAM.",
    )
    hnsw: HNSWIndexConfig = Field(default_factory=HNSWIndexConfig)
    ivfflat: IVFFlatIndexConfig = Field(default_factory=IVFFlatIndexConfig)


class VectorStoreConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: VectorStoreProvider = VectorStoreProvider.ALLOYDB_PGVECTOR
    connection_string: SecretStr | None = Field(
        default=None,
        description="Database DSN. Use ${ALLOYDB_CONNECTION}. Never commit plaintext.",
    )
    database: str = "rag_platform"
    pool_size: int = Field(default=20, ge=1, le=200)
    max_overflow: int = Field(default=40, ge=0)
    index: VectorIndexConfig = Field(default_factory=VectorIndexConfig)
    dimensions: int = Field(default=768, ge=64)
    distance_metric: DistanceMetric = DistanceMetric.COSINE
    # Vertex AI Vector Search fields (ignored if provider != vertex_ai_vector_search)
    index_id: str | None = None
    endpoint_id: str | None = None
    update_mode: Literal["streaming", "batch"] | None = None

    @model_validator(mode="after")
    def vertex_fields_required_if_vertex_provider(self) -> "VectorStoreConfig":
        if self.provider == VectorStoreProvider.VERTEX_VECTOR_SEARCH:
            missing = [f for f in ("index_id", "endpoint_id") if not getattr(self, f)]
            if missing:
                raise ValueError(
                    f"Fields {missing} are required when "
                    f"storage.vector_store.provider='vertex_ai_vector_search'."
                )
        return self


class DocumentStoreConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: DocumentStoreProvider = DocumentStoreProvider.ALLOYDB
    connection_string: SecretStr | None = None
    database: str = "rag_platform"
    pool_size: int = Field(default=10, ge=1, le=100)


class GraphStoreConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: GraphStoreProvider = GraphStoreProvider.NEO4J
    uri: SecretStr | None = None
    username: str | None = None
    password: SecretStr | None = None
    database: str = "neo4j"
    max_connection_pool_size: int = Field(default=50, ge=1)


class SemanticCacheConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    threshold: float = Field(
        default=0.97,
        ge=0.0,
        le=1.0,
        description="Cosine similarity above which a cached response is returned.",
    )
    dimensions: int = Field(
        default=256,
        ge=64,
        description="Embedding dimension for cache lookups. Use fast_path dimension.",
    )


class CacheConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: CacheProvider = CacheProvider.REDIS
    url: SecretStr | None = None
    ttl_seconds: int = Field(default=3600, ge=60)
    semantic_cache: SemanticCacheConfig = Field(default_factory=SemanticCacheConfig)
    key_prefix: str = Field(default="lbg_rag", description="Prefix for all Redis keys.")


class StorageConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    document_store: DocumentStoreConfig = Field(default_factory=DocumentStoreConfig)
    graph_store: GraphStoreConfig | None = None
    cache: CacheConfig = Field(default_factory=CacheConfig)


# ── Retrieval ─────────────────────────────────────────────────────────────────


class DenseRetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    weight: float = Field(default=0.7, ge=0.0, le=1.0)


class SparseRetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: SparseProvider = SparseProvider.VERTEX_AI_SEARCH
    weight: float = Field(default=0.3, ge=0.0, le=1.0)
    data_store_id: str | None = None
    project_id: str | None = None
    location: str | None = None


class MMRConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    lambda_param: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        alias="lambda",
        description="0 = max diversity, 1 = max relevance.",
    )
    model_config = ConfigDict(frozen=True, populate_by_name=True)


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    top_k: int = Field(default=20, ge=1, le=200, description="Candidates retrieved before re-ranking.")
    dense: DenseRetrievalConfig = Field(default_factory=DenseRetrievalConfig)
    sparse: SparseRetrievalConfig = Field(default_factory=SparseRetrievalConfig)
    hybrid_fusion: HybridFusion = HybridFusion.RRF
    rrf_k_constant: int = Field(
        default=60,
        ge=1,
        description="RRF smoothing constant. 60 is the standard default.",
    )
    metadata_filters: bool = Field(
        default=True,
        description="Enable server-side metadata filtering (RBAC filters are always applied regardless).",
    )
    mmr: MMRConfig = Field(default_factory=MMRConfig)

    @model_validator(mode="after")
    def hybrid_weights_sum_to_one(self) -> "RetrievalConfig":
        if self.strategy == RetrievalStrategy.HYBRID:
            total = self.dense.weight + self.sparse.weight
            if abs(total - 1.0) > 1e-6:
                raise ValueError(
                    f"retrieval.dense.weight ({self.dense.weight}) + "
                    f"retrieval.sparse.weight ({self.sparse.weight}) = {total:.6f}, "
                    f"but must sum to 1.0 for hybrid retrieval."
                )
        return self


# ── Augmentation ──────────────────────────────────────────────────────────────


class RerankerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    provider: RerankerProvider = RerankerProvider.COHERE
    model: str = Field(default="rerank-english-v3.0")
    api_key: SecretStr | None = None
    top_n: int = Field(
        default=5,
        ge=1,
        description="Documents returned after re-ranking. Must be <= retrieval.top_k.",
    )
    fallback_provider: RerankerProvider | None = RerankerProvider.CROSS_ENCODER


class ContextCompressionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    strategy: CompressionStrategy = CompressionStrategy.LLM_EXTRACT
    model: str = Field(default="gemini-2.0-flash-001")
    max_output_tokens: int = Field(default=1024, ge=64)


class QueryTransformationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    hyde: bool = Field(
        default=False,
        description="Hypothetical Document Embeddings. Useful for low-coverage corpora.",
    )
    step_back: bool = Field(
        default=True,
        description="Generate an abstract step-back question before retrieval.",
    )
    multi_query: bool = Field(
        default=True,
        description="Generate N sub-queries in parallel for broader retrieval coverage.",
    )
    multi_query_count: int = Field(default=3, ge=2, le=10)
    sub_query: bool = Field(
        default=False,
        description="Decompose into sequential sub-queries (slower, more thorough).",
    )


class AugmentationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    context_compression: ContextCompressionConfig = Field(default_factory=ContextCompressionConfig)
    query_transformation: QueryTransformationConfig = Field(default_factory=QueryTransformationConfig)


# ── Generation ────────────────────────────────────────────────────────────────


class LLMFallbackConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    provider: LLMProvider = LLMProvider.VERTEX_AI
    model: str = Field(default="gemini-1.5-pro-002")


class GenerationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: LLMProvider = LLMProvider.VERTEX_AI
    model: str = Field(default="gemini-2.0-flash-001")
    location: str = Field(default="europe-west2")
    project_id: str | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    system_prompt_template: str = Field(default="lbg-default")
    prompt_version: str = Field(default="v1.0.0")
    citation_mode: CitationMode = CitationMode.INLINE
    stream: bool = True
    api_key: SecretStr | None = Field(
        default=None,
        description="For non-GCP providers (Anthropic, OpenAI). Not needed for Vertex AI.",
    )
    fallback: LLMFallbackConfig | None = Field(default_factory=LLMFallbackConfig)


# ── Agents ────────────────────────────────────────────────────────────────────


class HITLGatesConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    after_planning: bool = Field(
        default=False,
        description="Pause for human approval after the supervisor generates a plan.",
    )
    after_draft: bool = Field(
        default=False,
        description="Pause for human review of the draft answer before delivery.",
    )
    compliance_topics: bool = Field(
        default=True,
        description="Always insert a HITL gate when the query is classified as compliance-sensitive.",
    )


class AgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    pattern: AgentPattern = AgentPattern.REACT
    max_iterations: int = Field(default=10, ge=1, le=50)
    confidence_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Critic agent passes the answer when this score is met.",
    )
    hitl_gates: HITLGatesConfig = Field(default_factory=HITLGatesConfig)
    tools: list[str] = Field(
        default=["rag_tool", "sql_tool", "api_tool", "calculator_tool"]
    )
    rag_as_tool: bool = True


# ── Security ──────────────────────────────────────────────────────────────────


class PIIDetectionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    provider: Literal["cloud_dlp", "presidio"] = "cloud_dlp"
    project_id: str | None = None
    inspection_template: str = "lbg-rag-uk-pii-template"
    deidentification_template: str = "lbg-rag-deident-template"
    log_finding_types: bool = Field(
        default=True,
        description="Log the TYPE of PII found. Never log the VALUE.",
    )
    tag_chunk_metadata: bool = True
    emit_audit_event: bool = True
    reject_restricted_data: bool = Field(
        default=True,
        description="Reject ingestion of RESTRICTED-classified documents entirely.",
    )


class DataClassificationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    default: DataClassificationLevel = DataClassificationLevel.INTERNAL


class RBACConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    enforce_at_retrieval: bool = Field(
        default=True,
        description="Inject mandatory RBAC filters on every vector store query. Cannot be bypassed.",
    )


class AuditLogConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    immutable: bool = Field(
        default=True,
        description="Use append-only table with WAL archiving. Required for FCA compliance.",
    )
    wal_archive_bucket: str | None = None
    table_name: str = "audit_events"


class SecurityConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    pii_detection: PIIDetectionConfig = Field(default_factory=PIIDetectionConfig)
    data_classification: DataClassificationConfig = Field(default_factory=DataClassificationConfig)
    rbac: RBACConfig = Field(default_factory=RBACConfig)
    audit_log: AuditLogConfig = Field(default_factory=AuditLogConfig)


# ── Observability ─────────────────────────────────────────────────────────────


class TracingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: Literal["opentelemetry"] = "opentelemetry"
    exporter: Literal["cloud_trace", "jaeger", "zipkin", "otlp", "console"] = "cloud_trace"
    sampling_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fraction of traces to sample. 1.0 in dev/staging, 0.1 in production.",
    )
    always_sample_errors: bool = Field(
        default=True,
        description="Override sampling_rate for error spans — always trace them.",
    )
    always_sample_slow_requests_ms: int = Field(
        default=3000,
        ge=100,
        description="Override sampling_rate for requests exceeding this latency threshold.",
    )
    endpoint: str | None = Field(
        default=None,
        description="OTLP / Jaeger endpoint. Not needed for cloud_trace exporter.",
    )


class StructuredLoggingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    level: LogLevel = LogLevel.INFO
    structured: bool = Field(
        default=True,
        description="Emit JSON log lines. Must be True in all non-local environments.",
    )
    exporter: Literal["cloud_logging", "stdout"] = "cloud_logging"
    include_trace_context: bool = Field(
        default=True,
        description="Inject trace_id and span_id into every log line for log-trace correlation.",
    )


class MetricsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    provider: Literal["opentelemetry"] = "opentelemetry"
    exporter: Literal["cloud_monitoring", "prometheus", "console"] = "cloud_monitoring"
    namespace: str = Field(
        default="custom.googleapis.com/rag",
        description="Cloud Monitoring custom metric namespace.",
    )
    export_interval_seconds: int = Field(default=15, ge=5)


class EvalThresholds(BaseModel):
    model_config = ConfigDict(frozen=True)
    faithfulness: float = Field(default=0.85, ge=0.0, le=1.0)
    answer_relevancy: float = Field(default=0.80, ge=0.0, le=1.0)
    context_precision: float = Field(default=0.80, ge=0.0, le=1.0)
    context_recall: float = Field(default=0.75, ge=0.0, le=1.0)
    groundedness: float = Field(default=0.85, ge=0.0, le=1.0)


class OnlineEvalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    async_eval: bool = Field(
        default=True,
        description="Evaluate asynchronously — does not block the response.",
    )
    sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fraction of responses to evaluate. 1.0 in staging, 0.1 in production.",
    )


class OfflineEvalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    golden_qa_bucket: str = "lbg-rag-eval"
    run_on_deploy: bool = True
    thresholds: EvalThresholds = Field(default_factory=EvalThresholds)


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    framework: Literal["ragas", "trulens", "deepeval"] = "ragas"
    online: OnlineEvalConfig = Field(default_factory=OnlineEvalConfig)
    offline: OfflineEvalConfig = Field(default_factory=OfflineEvalConfig)


class ObservabilityConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    logging: StructuredLoggingConfig = Field(default_factory=StructuredLoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)


# ── Resilience ────────────────────────────────────────────────────────────────


class CircuitBreakerConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    enabled: bool = True
    failure_threshold: int = Field(
        default=5,
        ge=1,
        description="Consecutive failures before the breaker opens.",
    )
    window_seconds: int = Field(default=30, ge=5, description="Rolling window for failure counting.")
    open_duration_seconds: int = Field(
        default=60,
        ge=10,
        description="How long the breaker stays open before allowing a probe request.",
    )
    success_threshold_to_close: int = Field(
        default=2,
        ge=1,
        description="Consecutive successes in HALF-OPEN state before closing.",
    )


class RetryPolicyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay_ms: int = Field(default=500, ge=50)
    max_delay_ms: int = Field(default=16_000, ge=500)
    backoff: RetryBackoff = RetryBackoff.EXPONENTIAL
    jitter: bool = Field(
        default=True,
        description="Add random jitter to avoid thundering-herd on retries.",
    )
    retry_on_status_codes: list[int] = Field(default=[429, 500, 502, 503, 504])

    @model_validator(mode="after")
    def max_delay_gte_base(self) -> "RetryPolicyConfig":
        if self.max_delay_ms < self.base_delay_ms:
            raise ValueError(
                f"max_delay_ms ({self.max_delay_ms}) must be >= base_delay_ms ({self.base_delay_ms})"
            )
        return self


class RetryConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    embedding: RetryPolicyConfig = Field(
        default_factory=lambda: RetryPolicyConfig(base_delay_ms=500, max_delay_ms=8_000)
    )
    llm: RetryPolicyConfig = Field(
        default_factory=lambda: RetryPolicyConfig(base_delay_ms=1_000, max_delay_ms=16_000)
    )
    vector_store: RetryPolicyConfig = Field(
        default_factory=lambda: RetryPolicyConfig(
            base_delay_ms=200,
            max_delay_ms=3_000,
            backoff=RetryBackoff.LINEAR,
            jitter=False,
            retry_on_status_codes=[],
        )
    )


class ResilienceConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)


# ── Root ──────────────────────────────────────────────────────────────────────


class RAGConfig(BaseModel):
    """Top-level configuration object for the LBG RAG Platform.

    Immutable after construction. Load via `rag.core.config.load_config()`.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",  # forward-compatible: unknown YAML keys are ignored with a warning
    )

    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    augmentation: AugmentationConfig = Field(default_factory=AugmentationConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    agents: AgentConfig = Field(default_factory=AgentConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    resilience: ResilienceConfig = Field(default_factory=ResilienceConfig)

    @model_validator(mode="after")
    def cross_section_constraints(self) -> "RAGConfig":
        errors: list[str] = []

        # ef_search must be >= top_k for HNSW indexes to return the right number of results.
        if self.storage.vector_store.index.type == "hnsw":
            ef_search = self.storage.vector_store.index.hnsw.ef_search
            top_k = self.retrieval.top_k
            if ef_search < top_k:
                errors.append(
                    f"storage.vector_store.index.hnsw.ef_search ({ef_search}) must be >= "
                    f"retrieval.top_k ({top_k}). HNSW cannot return more candidates than ef_search."
                )

        # Reranker top_n must not exceed what is retrieved.
        if self.augmentation.reranker.enabled:
            top_n = self.augmentation.reranker.top_n
            top_k = self.retrieval.top_k
            if top_n > top_k:
                errors.append(
                    f"augmentation.reranker.top_n ({top_n}) must be <= "
                    f"retrieval.top_k ({top_k}). Cannot re-rank more documents than retrieved."
                )

        # Semantic cache dimension must match embedding fast_path dimension.
        cache_dims = self.storage.cache.semantic_cache.dimensions
        fast_path_dims = self.embedding.dimensions.fast_path
        if self.storage.cache.semantic_cache.enabled and cache_dims != fast_path_dims:
            errors.append(
                f"storage.cache.semantic_cache.dimensions ({cache_dims}) must equal "
                f"embedding.dimensions.fast_path ({fast_path_dims}). "
                f"Cache lookups use the fast_path embedding."
            )

        if errors:
            raise ValueError(
                "Cross-section config validation failed:\n  " + "\n  ".join(errors)
            )
        return self
