"""Administrator-editable settings, stored in the database.

Each setting is declared once (type, default, description, secrecy) so the API, the admin
console and validation all derive from the same table. Secrets are encrypted at rest and are
never returned by the API — only a masked hint.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any

from advisor.config import Settings
from advisor.db import Database
from advisor.security import SecretBox, mask_secret


@dataclass(frozen=True)
class Spec:
    key: str
    type: str  # str | int | float | bool | choice | text
    default: Any
    label: str
    help: str = ""
    secret: bool = False
    choices: tuple[str, ...] = ()
    group: str = "general"
    min: float | None = None
    max: float | None = None


SPECS: dict[str, Spec] = {
    s.key: s
    for s in [
        Spec("llm.primary", "choice", "auto", "Preferred AI provider",
             "auto = Gemini when an API key is set, otherwise the local Ollama model.",
             choices=("auto", "gemini", "ollama"), group="ai"),
        Spec("gemini.api_key", "str", "", "Gemini API key",
             "Paste a key from Google AI Studio. Stored encrypted; never shown again.",
             secret=True, group="ai"),
        Spec("gemini.model", "str", "gemini-2.5-flash", "Gemini model",
             "Any model that supports generateContent (use 'Load models' to list them).", group="ai"),
        Spec("gemini.enabled", "bool", True, "Use Gemini when a key is configured", group="ai"),
        Spec("gemini.thinking_budget", "int", 0, "Gemini thinking budget (tokens)",
             "0 disables hidden reasoning for fast replies; raise for harder questions. "
             "Ignored by models that cannot disable thinking.", group="ai", min=0, max=24576),
        Spec("ollama.base_url", "str", "http://127.0.0.1:11434", "Ollama URL", group="ai"),
        Spec("ollama.model", "str", "qwen3:8b", "Ollama model",
             "Local fallback model. Must already be pulled (ollama pull <name>).", group="ai"),
        Spec("ollama.enabled", "bool", True, "Allow Ollama fallback", group="ai"),
        Spec("llm.temperature", "float", 0.2, "Answer temperature",
             "Lower = more literal answers.", group="ai", min=0, max=1),
        Spec("llm.max_tokens", "int", 1400, "Maximum answer length (tokens)", group="ai", min=200, max=4000),
        Spec("rag.context_chunks", "int", 10, "Evidence passages per answer", group="retrieval", min=3, max=20),
        Spec("rag.rerank", "bool", True, "Use the re-ranking model", group="retrieval"),
        Spec("rag.abstain_below", "float", 0.12, "Minimum relevance to answer",
             "Below this evidence score the assistant says it could not find the answer.",
             group="retrieval", min=0, max=1),
        Spec("assistant.notice", "text", "", "Current notice for students",
             "Shown at the top of the chat and treated as official information (e.g. closures, "
             "deadline changes). Leave blank for none.", group="content"),
        Spec("assistant.extra_rules", "text", "", "Extra instructions for the assistant",
             "Optional style or policy guidance appended to the system prompt.", group="content"),
        Spec("chat.enabled", "bool", True, "Chat enabled",
             "Turn off to show a maintenance message to students.", group="operations"),
        Spec("chat.log_questions", "bool", True, "Keep a log of questions",
             "Used for the 'unanswered questions' report. Questions are kept for the retention period.",
             group="operations"),
    ]
}


class RuntimeSettings:
    def __init__(self, db: Database, box: SecretBox, defaults: Settings):
        self.db = db
        self.box = box
        self._bootstrap = {
            "gemini.api_key": defaults.gemini_api_key,
            "gemini.model": defaults.gemini_model,
            "ollama.base_url": defaults.ollama_base_url,
            "ollama.model": defaults.ollama_model,
        }
        self._cache: dict[str, Any] = {}
        self._loaded_at = 0.0
        self._lock = threading.Lock()
        self.version = 0

    # -- reading -------------------------------------------------------------------
    def _load(self) -> None:
        with self._lock:
            if time.monotonic() - self._loaded_at < 2.0:
                return
            rows = self.db.all("SELECT key, value, is_secret FROM settings")
            cache = {}
            for r in rows:
                raw = r["value"]
                if r["is_secret"]:
                    raw = self.box.decrypt(raw) or ""
                    cache[r["key"]] = raw
                else:
                    try:
                        cache[r["key"]] = json.loads(raw)
                    except json.JSONDecodeError:
                        cache[r["key"]] = raw
            self._cache = cache
            self._loaded_at = time.monotonic()

    def get(self, key: str) -> Any:
        self._load()
        if key in self._cache and self._cache[key] not in (None, ""):
            return self._cache[key]
        if key in self._cache and SPECS[key].type in ("text", "bool", "int", "float"):
            return self._cache[key]  # explicit empty text / false
        boot = self._bootstrap.get(key)
        if boot not in (None, ""):
            return boot
        return SPECS[key].default

    # -- writing -------------------------------------------------------------------
    def coerce(self, spec: Spec, value: Any) -> Any:
        if spec.type == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if spec.type in ("int", "float"):
            num = int(value) if spec.type == "int" else float(value)
            if spec.min is not None and num < spec.min:
                raise ValueError(f"{spec.label} must be at least {spec.min}")
            if spec.max is not None and num > spec.max:
                raise ValueError(f"{spec.label} must be at most {spec.max}")
            return num
        text = str(value).strip() if spec.type != "text" else str(value)
        if spec.type == "choice" and text not in spec.choices:
            raise ValueError(f"{spec.label} must be one of {', '.join(spec.choices)}")
        if spec.key == "ollama.base_url" and not text.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must start with http:// or https://")
        if len(text) > 8000:
            raise ValueError(f"{spec.label} is too long")
        return text

    def set(self, key: str, value: Any, actor: str = "admin") -> None:
        spec = SPECS.get(key)
        if spec is None:
            raise KeyError(key)
        value = self.coerce(spec, value)
        if spec.secret:
            if value == "":
                self.db.execute("DELETE FROM settings WHERE key=?", (key,))
            else:
                self.db.execute(
                    "INSERT INTO settings(key,value,is_secret,updated_by) VALUES(?,?,1,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, is_secret=1, "
                    "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), updated_by=excluded.updated_by",
                    (key, self.box.encrypt(value), actor),
                )
        else:
            self.db.execute(
                "INSERT INTO settings(key,value,is_secret,updated_by) VALUES(?,?,0,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), updated_by=excluded.updated_by",
                (key, json.dumps(value), actor),
            )
        self._loaded_at = 0.0
        self.version += 1

    # -- presentation --------------------------------------------------------------
    def public_view(self) -> list[dict]:
        out = []
        for spec in SPECS.values():
            value = self.get(spec.key)
            item = {
                "key": spec.key, "type": spec.type, "label": spec.label, "help": spec.help,
                "group": spec.group, "choices": list(spec.choices), "secret": spec.secret,
                "min": spec.min, "max": spec.max,
            }
            if spec.secret:
                item["configured"] = bool(value)
                item["hint"] = mask_secret(value) if value else ""
                item["value"] = ""
            else:
                item["value"] = value
            out.append(item)
        return out
