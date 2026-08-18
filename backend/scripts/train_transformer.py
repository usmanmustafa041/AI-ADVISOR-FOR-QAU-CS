"""Fine-tune multilingual DistilBERT for the advisor's documented intent set."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_rows(path: Path) -> list[dict[str, str]]:
    rows = [
        {"text": row["text"].strip(), "intent": row["intent"].strip()}
        for row in csv.DictReader(path.open(encoding="utf-8", newline=""))
        if row.get("text", "").strip() and row.get("intent", "").strip()
    ]
    if not rows:
        raise ValueError(f"No labeled examples found in {path}")
    return rows


def stratified_split(
    rows: list[dict[str, str]], validation_per_intent: int, seed: int
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["intent"]].append(row)
    rng = random.Random(seed)
    train: list[dict[str, str]] = []
    validation: list[dict[str, str]] = []
    for label_rows in grouped.values():
        rng.shuffle(label_rows)
        count = min(validation_per_intent, max(0, len(label_rows) - 2))
        validation.extend(label_rows[:count])
        train.extend(label_rows[count:])
    rng.shuffle(train)
    rng.shuffle(validation)
    return train, validation


def scores(actual: list[int], predicted: list[int], labels: list[str]) -> dict:
    accuracy = sum(a == b for a, b in zip(actual, predicted, strict=True)) / len(actual)
    per_intent = {}
    for index, label in enumerate(labels):
        tp = sum(a == index and p == index for a, p in zip(actual, predicted, strict=True))
        fp = sum(a != index and p == index for a, p in zip(actual, predicted, strict=True))
        fn = sum(a == index and p != index for a, p in zip(actual, predicted, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_intent[label] = {"precision": precision, "recall": recall, "f1": f1}
    return {
        "accuracy": accuracy,
        "macro_f1": sum(item["f1"] for item in per_intent.values()) / len(labels),
        "per_intent": per_intent,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/intent_dataset.csv"))
    parser.add_argument("--output", type=Path, default=Path("models/qau-intent-distilmbert"))
    parser.add_argument("--model", default="distilbert-base-multilingual-cased")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--validation-per-intent", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    import torch
    from torch.optim import AdamW
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from transformers.optimization import get_linear_schedule_with_warmup

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    rows = load_rows(args.input)
    labels = sorted({row["intent"] for row in rows})
    label2id = {label: index for index, label in enumerate(labels)}
    id2label = {index: label for label, index in label2id.items()}
    train_rows, validation_rows = stratified_split(rows, args.validation_per_intent, args.seed)
    tokenizer = AutoTokenizer.from_pretrained(args.model)

    class IntentDataset(Dataset):
        def __init__(self, examples: list[dict[str, str]]) -> None:
            self.examples = examples

        def __len__(self) -> int:
            return len(self.examples)

        def __getitem__(self, index: int) -> dict:
            row = self.examples[index]
            encoded = tokenizer(
                row["text"], truncation=True, max_length=args.max_length
            )
            encoded["labels"] = label2id[row["intent"]]
            return encoded

    def collate(batch: list[dict]) -> dict:
        labels_tensor = torch.tensor([item.pop("labels") for item in batch], dtype=torch.long)
        padded = tokenizer.pad(batch, padding=True, return_tensors="pt")
        padded["labels"] = labels_tensor
        return padded

    train_loader = DataLoader(
        IntentDataset(train_rows), batch_size=args.batch_size, shuffle=True, collate_fn=collate
    )
    validation_loader = DataLoader(
        IntentDataset(validation_rows), batch_size=args.batch_size, shuffle=False, collate_fn=collate
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(labels), label2id=label2id, id2label=id2label
    ).to(device)
    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    total_steps = max(1, len(train_loader) * args.epochs)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=max(1, total_steps // 10), num_training_steps=total_steps
    )
    epoch_losses: list[float] = []
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            output = model(**batch)
            output.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += float(output.loss.item())
        loss = total_loss / max(1, len(train_loader))
        epoch_losses.append(loss)
        print(f"epoch={epoch + 1}/{args.epochs} loss={loss:.4f}", flush=True)

    model.eval()
    actual: list[int] = []
    predicted: list[int] = []
    with torch.inference_mode():
        for batch in validation_loader:
            labels_tensor = batch.pop("labels")
            output = model(**{key: value.to(device) for key, value in batch.items()})
            actual.extend(labels_tensor.tolist())
            predicted.extend(output.logits.argmax(dim=-1).cpu().tolist())
    metrics = scores(actual, predicted, labels)
    args.output.mkdir(parents=True, exist_ok=True)
    model.cpu().save_pretrained(args.output, safe_serialization=True)
    tokenizer.save_pretrained(args.output)
    metadata = {
        "architecture": "DistilBertForSequenceClassification",
        "base_model": args.model,
        "trained_at": datetime.now(UTC).isoformat(),
        "training_examples": len(train_rows),
        "validation_examples": len(validation_rows),
        "labels": labels,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "max_length": args.max_length,
        "seed": args.seed,
        "device": str(device),
        "epoch_losses": epoch_losses,
        "validation": metrics,
    }
    (args.output / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
