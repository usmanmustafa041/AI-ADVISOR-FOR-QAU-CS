"""Resumable public model downloads; never changes the preview model or active index."""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from chatbot_v3.settings import ROOT

MODELS = ["Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Reranker-0.6B"]


def download(name, attempts):
    # Set before importing HF constants. Slow links need more than the 10-second default.
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from huggingface_hub import snapshot_download

    for attempt in range(1, attempts + 1):
        try:
            path = snapshot_download(
                name, cache_dir=ROOT / "backend/.model-cache/hub", max_workers=2
            )
            print(json.dumps({"model": name, "status": "downloaded", "snapshot": path}), flush=True)
            return True
        except Exception as e:
            print(
                json.dumps(
                    {
                        "model": name,
                        "attempt": attempt,
                        "status": "retry_pending" if attempt < attempts else "failed",
                        "error_type": type(e).__name__,
                    }
                ),
                flush=True,
            )
            if attempt < attempts:
                time.sleep(min(30, attempt * 5))
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    p.add_argument("--attempts", type=int, default=4, choices=range(1, 9))
    a = p.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda name: download(name, a.attempts), a.models))
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
