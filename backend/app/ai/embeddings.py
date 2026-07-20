from sentence_transformers import SentenceTransformer

EMBEDDING_DIMENSIONS = 384

_model: SentenceTransformer | None = None


def load_model() -> None:
    """Load the embedding model once. Call from the FastAPI lifespan on startup —
    never per-request, since instantiation (not inference) is the expensive part.
    """
    global _model
    if _model is None:
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
