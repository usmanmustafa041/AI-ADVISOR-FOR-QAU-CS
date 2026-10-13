"""Model-specific document/query encoding; indexes never mix encoder identities."""

import hashlib

import numpy as np

from chatbot_v3.settings import ROOT


class Encoder:
    def __init__(self, name, device="cpu", local_only=True):
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(4)
        self.name = name
        self.model = SentenceTransformer(
            name,
            device=device,
            local_files_only=local_only,
            cache_folder=str(ROOT / "backend/.model-cache/hub"),
        )
        self.model.max_seq_length = 2048 if "Qwen3" in name else 512
        self.revision = getattr(self.model[0].auto_model.config, "_commit_hash", None)
        self.signature = hashlib.sha256(
            f"{name}|{self.revision}|{self.model.max_seq_length}|prefix-policy-v1".encode()
        ).hexdigest()

    def encode(self, texts, query=False):
        if "e5" in self.name.lower():
            texts = [("query: " if query else "passage: ") + t for t in texts]
        elif "Qwen3-Embedding" in self.name and query:
            texts = [
                "Instruct: Retrieve official university passages relevant to this student question.\nQuery: "
                + t
                for t in texts
            ]
        return np.asarray(
            self.model.encode(
                texts, batch_size=12, normalize_embeddings=True, show_progress_bar=False
            ),
            dtype=np.float32,
        )


class Reranker:
    def __init__(self, name, device="cpu", local_only=True):
        self.name, self.device = name, device
        if "Qwen3-Reranker" in name:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(
                name,
                padding_side="left",
                local_files_only=local_only,
                cache_dir=str(ROOT / "backend/.model-cache/hub"),
            )
            self.model = (
                AutoModelForCausalLM.from_pretrained(
                    name,
                    local_files_only=local_only,
                    torch_dtype=torch.float32,
                    cache_dir=str(ROOT / "backend/.model-cache/hub"),
                )
                .to(device)
                .eval()
            )
            self.yes = self.tokenizer.convert_tokens_to_ids("yes")
            self.no = self.tokenizer.convert_tokens_to_ids("no")
        else:
            from sentence_transformers import CrossEncoder

            self.model = CrossEncoder(
                name,
                device=device,
                local_files_only=local_only,
                cache_folder=str(ROOT / "backend/.model-cache/hub"),
            )

    def scores(self, query, documents):
        if "Qwen3-Reranker" not in self.name:
            return list(map(float, self.model.predict([(query, d) for d in documents])))
        import torch

        prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        result = []
        for start in range(0, len(documents), 4):
            texts = [
                "<Instruct>: Retrieve official university evidence relevant to the student question.\n<Query>: "
                + query
                + "\n<Document>: "
                + d[:7000]
                for d in documents[start : start + 4]
            ]
            prefix_ids = self.tokenizer.encode(prefix, add_special_tokens=False)
            suffix_ids = self.tokenizer.encode(suffix, add_special_tokens=False)
            body = self.tokenizer(
                texts,
                padding=False,
                truncation=True,
                max_length=2300 - len(prefix_ids) - len(suffix_ids),
                add_special_tokens=False,
            )
            # Preserve the required assistant yes/no suffix even for long Urdu documents.
            ids = [prefix_ids + tokens + suffix_ids for tokens in body["input_ids"]]
            batch = self.tokenizer.pad({"input_ids": ids}, padding=True, return_tensors="pt").to(
                self.device
            )
            with torch.no_grad():
                logits = self.model(**batch).logits[:, -1, [self.no, self.yes]]
                result.extend(torch.softmax(logits, dim=1)[:, 1].cpu().tolist())
        return result
