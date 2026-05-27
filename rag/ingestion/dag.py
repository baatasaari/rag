"""
Cloud Composer (Apache Airflow 2.x) DAG for the LBG RAG ingestion pipeline.

The DAG is defined only when Airflow is installed; in environments without
Airflow (local dev, unit tests) this module imports cleanly but registers no DAG.

Trigger: manual / event-driven (schedule=None).
Input:   DAG conf keys — ``source_uri`` (str) and ``raw_content_b64`` (str,
         base64-encoded bytes).

Retry policy:
  - Each task retries up to 3 times with 5-minute exponential back-off.
  - execution_timeout = 30 min (covers large PDFs + batched embedding calls).

GCP-specific:
  - Workload Identity is assumed; no service-account key files.
  - All storage services are in europe-west2 for FCA data residency.
  - Cloud Trace exporter is wired via OTEL_EXPORTER_OTLP_ENDPOINT env var.
"""

from __future__ import annotations

import base64
import os
from datetime import timedelta
from typing import Any

from rag.observability.logging import get_logger

log = get_logger(__name__)

try:
    from airflow.decorators import dag, task
    from airflow.utils.dates import days_ago

    _AIRFLOW_AVAILABLE = True
except ImportError:  # pragma: no cover
    _AIRFLOW_AVAILABLE = False


def _build_pipeline(conf: dict[str, Any]) -> Any:
    """Construct an IngestionPipeline from Airflow conf / environment variables.

    Deferred imports keep heavy SDKs out of the Airflow scheduler process.
    """
    from rag.core.config import load_config  # noqa: PLC0415
    from rag.chunking.engine import ChunkingEngine  # noqa: PLC0415
    from rag.embedding.engine import EmbeddingEngine  # noqa: PLC0415
    from rag.embedding.adapters.vertex import VertexEmbeddingAdapter  # noqa: PLC0415
    from rag.ingestion.pipeline import IngestionPipeline  # noqa: PLC0415
    from rag.security.audit import AuditLogger  # noqa: PLC0415
    from rag.storage.vector_store import AlloyDBVectorStore  # noqa: PLC0415
    from rag.storage.document_store import AlloyDBDocumentStore  # noqa: PLC0415

    rag_cfg = load_config()

    adapter = VertexEmbeddingAdapter(rag_cfg.embedding)
    embedding_engine = EmbeddingEngine(rag_cfg.embedding, adapter)
    chunking_engine = ChunkingEngine(rag_cfg.chunking)
    vector_store = AlloyDBVectorStore(rag_cfg.storage.vector_store)
    document_store = AlloyDBDocumentStore(rag_cfg.storage.document_store)
    audit_logger = AuditLogger(rag_cfg.security)

    return IngestionPipeline(
        config=rag_cfg,
        chunking_engine=chunking_engine,
        embedding_engine=embedding_engine,
        vector_store=vector_store,
        document_store=document_store,
        audit_logger=audit_logger,
    )


if _AIRFLOW_AVAILABLE:

    @dag(
        dag_id="lbg_rag_ingestion",
        description="15-stage LBG RAG document ingestion pipeline",
        schedule=None,
        start_date=days_ago(1),
        catchup=False,
        tags=["lbg", "rag", "ingestion", "europe-west2"],
        default_args={
            "retries": 3,
            "retry_delay": timedelta(minutes=5),
            "retry_exponential_backoff": True,
            "execution_timeout": timedelta(minutes=30),
        },
        params={
            "source_uri": "",
            "raw_content_b64": "",
        },
    )
    def ingestion_dag() -> None:
        """Ingest a single document through all 15 pipeline stages."""

        @task(task_id="run_pipeline")
        def run_pipeline(**context: Any) -> dict[str, Any]:
            """Execute the IngestionPipeline and return a summary dict for XCom."""
            import asyncio  # noqa: PLC0415

            conf = context.get("params", {})
            source_uri: str = conf.get("source_uri", "")
            raw_b64: str = conf.get("raw_content_b64", "")

            if not source_uri:
                raise ValueError("DAG conf must include 'source_uri'")
            if not raw_b64:
                raise ValueError("DAG conf must include 'raw_content_b64' (base64)")

            raw_content = base64.b64decode(raw_b64)
            pipeline = _build_pipeline(conf)
            ctx = asyncio.run(pipeline.run(source_uri, raw_content))

            return {
                "doc_id": ctx.doc_id,
                "source_uri": ctx.source_uri,
                "chunk_count": len(ctx.chunks),
                "completed_stages": ctx.completed_stages,
                "aborted": ctx.should_abort,
                "abort_reason": ctx.abort_reason,
                "stage_errors": ctx.stage_errors,
            }

        run_pipeline()

    lbg_rag_ingestion_dag = ingestion_dag()
