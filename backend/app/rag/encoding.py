"""Model-specific retrieval prefixes, shared by building and querying vectors."""


def texts_for_model(texts, model_name, *, query=False):
    if "multilingual-e5" in model_name.lower() or "/e5-" in model_name.lower():
        prefix = "query: " if query else "passage: "
        return [prefix + t for t in texts]
    return list(texts)


def encode_documents(encoder, texts, model_name, **kwargs):
    return encoder.encode(texts_for_model(texts, model_name), normalize_embeddings=True, **kwargs)


def encode_query(encoder, query, model_name):
    return encoder.encode(
        texts_for_model([query], model_name, query=True),
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]
