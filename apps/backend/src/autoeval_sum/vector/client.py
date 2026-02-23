"""
Pinecone vector client wrapper.

Handles embedding via text-embedding-004 (Google GenAI) and all Pinecone
operations: upsert, query, and fetch.  Synchronous Pinecone SDK calls are
run in an executor to stay non-blocking in the async graph pipeline.

Namespaces
----------
eval_prompts  — one vector per EvalCase prompt; used for dedup checks
failures      — one vector per failing judge result; used for failure memory
"""

import asyncio
import logging
from typing import Any

from google import genai as google_genai
from pinecone import Pinecone

from autoeval_sum.config.settings import get_settings

log = logging.getLogger(__name__)

# Embedding task types (old SDK names → new SDK uppercase values)
_TASK_RETRIEVAL_DOCUMENT = "retrieval_document"
_TASK_RETRIEVAL_QUERY = "retrieval_query"

_TASK_TYPE_MAP: dict[str, str] = {
    "retrieval_document": "RETRIEVAL_DOCUMENT",
    "retrieval_query": "RETRIEVAL_QUERY",
}

# Pinecone namespaces
NS_EVAL_PROMPTS = "eval_prompts"
NS_FAILURES = "failures"


class PineconeClient:
    """
    Thin async wrapper around the Pinecone SDK.

    Lazy-initialised on first use so the constructor never blocks and
    application startup doesn't fail when Pinecone is unavailable.
    """

    def __init__(self) -> None:
        self._pc: Pinecone | None = None
        self._index: Any = None
        self._genai_client: google_genai.Client | None = None

    def _get_genai_client(self) -> google_genai.Client:
        if self._genai_client is None:
            settings = get_settings()
            self._genai_client = google_genai.Client(api_key=settings.google_api_key)
        return self._genai_client

    def _get_index(self) -> Any:
        if self._index is None:
            settings = get_settings()
            self._pc = Pinecone(api_key=settings.pinecone_api_key)
            self._index = self._pc.Index(settings.pinecone_index_name)
            log.debug("Pinecone index '%s' connected.", settings.pinecone_index_name)
        return self._index

    # ── Embedding ──────────────────────────────────────────────────────────────

    def _embed_sync(self, text: str, task_type: str = _TASK_RETRIEVAL_DOCUMENT) -> list[float]:
        """Synchronous Google embedding call via google-genai SDK."""
        from google.genai import types as genai_types

        settings = get_settings()
        client = self._get_genai_client()
        sdk_task_type = _TASK_TYPE_MAP.get(task_type, task_type.upper())
        result = client.models.embed_content(
            model=settings.embedding_model,
            contents=text,
            config=genai_types.EmbedContentConfig(
                task_type=sdk_task_type,
                output_dimensionality=settings.pinecone_embedding_dimension,
            ),
        )
        return list(result.embeddings[0].values)

    async def embed_text(
        self,
        text: str,
        task_type: str = _TASK_RETRIEVAL_DOCUMENT,
    ) -> list[float]:
        """Async wrapper around the synchronous embedding call."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, text, task_type)

    # ── Upsert ────────────────────────────────────────────────────────────────

    def _upsert_sync(
        self,
        vectors: list[dict[str, Any]],
        namespace: str,
    ) -> None:
        """Synchronous Pinecone upsert."""
        index = self._get_index()
        index.upsert(vectors=vectors, namespace=namespace)

    async def upsert_vectors(
        self,
        vectors: list[dict[str, Any]],
        namespace: str,
    ) -> None:
        """
        Upsert pre-computed vectors to a namespace.

        Each vector dict must have: ``id`` (str), ``values`` (list[float]),
        and optionally ``metadata`` (dict).
        """
        if not vectors:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._upsert_sync, vectors, namespace)
        log.debug("Upserted %d vectors to namespace '%s'.", len(vectors), namespace)

    async def embed_and_upsert(
        self,
        items: list[dict[str, Any]],
        namespace: str,
        id_key: str = "id",
        text_key: str = "text",
        task_type: str = _TASK_RETRIEVAL_DOCUMENT,
    ) -> None:
        """
        Embed each item's text field and upsert to Pinecone.

        Parameters
        ----------
        items:
            List of dicts, each with at least ``id_key`` and ``text_key`` fields.
            Any additional keys are stored as metadata.
        namespace:
            Pinecone namespace to upsert into.
        """
        vectors = []
        for item in items:
            text = item[text_key]
            embedding = await self.embed_text(text, task_type)
            metadata = {k: v for k, v in item.items() if k not in (id_key, text_key)}
            vectors.append({
                "id": item[id_key],
                "values": embedding,
                "metadata": metadata,
            })
        await self.upsert_vectors(vectors, namespace)

    # ── Query ─────────────────────────────────────────────────────────────────

    def _query_sync(
        self,
        vector: list[float],
        namespace: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Synchronous Pinecone query."""
        index = self._get_index()
        response = index.query(
            vector=vector,
            top_k=top_k,
            include_metadata=True,
            namespace=namespace,
        )
        return [
            {
                "id": match["id"],
                "score": float(match["score"]),
                "metadata": match.get("metadata", {}),
            }
            for match in response.get("matches", [])
        ]

    async def query_similar(
        self,
        text: str,
        namespace: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Embed `text` and return the top-k most similar vectors.

        Returns
        -------
        list of dicts with keys: ``id``, ``score`` (cosine similarity), ``metadata``.
        """
        vector = await self.embed_text(text, task_type=_TASK_RETRIEVAL_QUERY)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, self._query_sync, vector, namespace, top_k
        )
        return results


# ── Module-level singleton ─────────────────────────────────────────────────────

_client: PineconeClient | None = None


def get_pinecone_client() -> PineconeClient:
    """Return the process-level PineconeClient singleton."""
    global _client
    if _client is None:
        _client = PineconeClient()
    return _client
