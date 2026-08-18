import hashlib
import math
import re


EMBEDDING_DIMENSION = 384


def embed_text(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Portable deterministic embedding fallback for development and tests.

    Production can replace this function with a pinned multilingual
    sentence-transformer while keeping the 384-dimensional pgvector contract.
    """
    vector = [0.0] * dimension
    tokens = re.findall(r"[\w-]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"

