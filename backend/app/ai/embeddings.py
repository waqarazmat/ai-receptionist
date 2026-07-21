import os

# Cap native thread pools BEFORE importing torch / sentence-transformers, so
# OpenMP/MKL/OpenBLAS read the caps at C-library init time (they only honor
# these once, at first-touch — setting them later is a no-op).
#
# WHY: on Railway's CPU-limited containers, `os.cpu_count()` returns the host
# node's core count (e.g. 48), not the container's cgroup CPU quota (~8 vCPUs).
# Torch's default OMP intra-op pool thus spawns 48 workers to embed a ~15-token
# voice query. The coordination overhead dominates the actual compute — we
# measured ~2800 ms/embed on Railway vs ~30 ms achievable single-threaded.
# Setting all native pools to 1 is optimal for this specific workload: tiny
# model (MiniLM-L6-v2, 384-dim), short inputs (a phone-call utterance).
#
# `setdefault` respects an operator override — if someone sets a higher value
# in the Railway variables tab (e.g. to speed up embed_batch on many chunks),
# that wins. Only apply the default if the operator hasn't configured it.
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_var, "1")
# Silences the HuggingFace tokenizer's own thread pool, which prints a scary
# fork-warning under uvicorn workers and doesn't help throughput here either.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import structlog
import torch

from sentence_transformers import SentenceTransformer

logger = structlog.get_logger()

EMBEDDING_DIMENSIONS = 384

_model: SentenceTransformer | None = None


def load_model() -> None:
    """Load the embedding model once. Call from the FastAPI lifespan on startup —
    never per-request, since instantiation (not inference) is the expensive part.
    """
    global _model
    if _model is None:
        # Belt-and-suspenders after the env-var setter above: even if the OMP
        # cap somehow didn't take, this caps torch's own pool directly. Called
        # before SentenceTransformer construction so the model sees the cap
        # from its first forward pass.
        torch.set_num_threads(1)
        if hasattr(torch, "set_num_interop_threads"):
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                # set_num_interop_threads must be called before any parallel
                # work; if another import already used torch, this raises.
                # Non-fatal — the intra-op cap above is what matters most.
                pass
        logger.info(
            "embedding_threads_capped",
            torch_num_threads=torch.get_num_threads(),
            omp_num_threads=os.environ.get("OMP_NUM_THREADS"),
            mkl_num_threads=os.environ.get("MKL_NUM_THREADS"),
        )
        _model = SentenceTransformer("all-MiniLM-L6-v2")


def _get_model() -> SentenceTransformer:
    if _model is None:
        raise RuntimeError(
            "Embedding model not loaded. Call app.ai.embeddings.load_model() during app startup."
        )
    return _model


def embed_text(text: str) -> list[float]:
    return _get_model().encode(text).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    return _get_model().encode(texts).tolist()
