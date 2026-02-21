"""
MSMARCO corpus fetcher.

Loads microsoft/ms_marco v1.1 train split via the HuggingFace datasets library,
extracts individual passages as raw documents, and writes each passage text to
disk under data/corpus/.

Caching behaviour
-----------------
The HuggingFace datasets library caches downloaded shards to the path specified
by ``cache_dir``.  Repeat calls reuse the on-disk cache — no network traffic
after the first fetch.

The per-document text files are written to ``corpus_dir`` (data/corpus/ by
default).  Both directories live inside the gitignored data/ volume.

Configuration override
----------------------
If the dataset name or config changes on HuggingFace, set the environment
variables MSMARCO_DATASET, MSMARCO_CONFIG, and MSMARCO_SPLIT before running.
The loader will fail fast with an actionable message on any loading error.
"""

import hashlib
import logging
import os
from pathlib import Path

from datasets import load_dataset  # type: ignore[import]
from datasets.exceptions import DatasetNotFoundError  # type: ignore[import]

from autoeval_sum.models.documents import RawDocument

log = logging.getLogger(__name__)

# Overridable via env vars for forward compatibility
MSMARCO_DATASET = os.getenv("MSMARCO_DATASET", "microsoft/ms_marco")
MSMARCO_CONFIG = os.getenv("MSMARCO_CONFIG", "v1.1")
MSMARCO_SPLIT = os.getenv("MSMARCO_SPLIT", "train")

# How many top-level MSMARCO examples to scan when building the passage pool.
# Each example contains ~10 passages; 5 000 examples → ~50 000 candidate passages.
SCAN_LIMIT = int(os.getenv("MSMARCO_SCAN_LIMIT", "5000"))


def _passage_doc_id(passage_text: str, query_id: int, idx: int) -> str:
    """Stable deterministic ID for a passage (does not change between runs)."""
    key = f"{query_id}:{idx}:{passage_text[:64]}"
    return hashlib.sha256(key.encode()).hexdigest()[:24]


def fetch_raw_documents(
    data_dir: str | Path = "data",
) -> list[RawDocument]:
    """
    Load MSMARCO passages and write raw text files to disk.

    Parameters
    ----------
    data_dir:
        Root of the gitignored data volume.  Sub-directories ``hf_cache/`` and
        ``corpus/`` are created automatically.

    Returns
    -------
    list[RawDocument]
        Flat list of all passages extracted from the scanned examples.
        Caller is responsible for filtering and sampling.
    """
    data_path = Path(data_dir)
    cache_dir = data_path / "hf_cache"
    corpus_dir = data_path / "corpus"
    cache_dir.mkdir(parents=True, exist_ok=True)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "Loading %s / %s split=%s  (scan_limit=%d, cache=%s)",
        MSMARCO_DATASET,
        MSMARCO_CONFIG,
        MSMARCO_SPLIT,
        SCAN_LIMIT,
        cache_dir,
    )

    try:
        dataset = load_dataset(
            MSMARCO_DATASET,
            MSMARCO_CONFIG,
            split=MSMARCO_SPLIT,
            cache_dir=str(cache_dir),
            trust_remote_code=False,
        )
    except DatasetNotFoundError as exc:
        raise RuntimeError(
            f"Dataset '{MSMARCO_DATASET}' config='{MSMARCO_CONFIG}' split='{MSMARCO_SPLIT}' "
            f"not found on HuggingFace.  "
            f"Override with env vars MSMARCO_DATASET / MSMARCO_CONFIG / MSMARCO_SPLIT."
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load '{MSMARCO_DATASET}': {exc}.  "
            f"Check your network connection and HuggingFace credentials."
        ) from exc

    total_examples = len(dataset)
    scan_count = min(SCAN_LIMIT, total_examples)
    log.info("Dataset loaded — %d total examples, scanning first %d", total_examples, scan_count)

    raw_docs: list[RawDocument] = []
    written = 0
    skipped_existing = 0

    for example in dataset.select(range(scan_count)):
        query_id: int = int(example["query_id"])
        passages = example.get("passages", {})
        texts: list[str] = passages.get("passage_text", [])
        urls: list[str] = passages.get("url", [""] * len(texts))

        for idx, (text, url) in enumerate(zip(texts, urls)):
            if not text or not text.strip():
                continue

            doc_id = _passage_doc_id(text, query_id, idx)
            file_path = corpus_dir / f"{doc_id}.txt"

            if not file_path.exists():
                file_path.write_text(text, encoding="utf-8")
                written += 1
            else:
                skipped_existing += 1

            raw_docs.append(
                RawDocument(
                    text=text,
                    url=url or "",
                    source_query_id=query_id,
                )
            )

    log.info(
        "Fetched %d raw passages  (wrote %d new files, %d already cached)",
        len(raw_docs),
        written,
        skipped_existing,
    )
    return raw_docs
