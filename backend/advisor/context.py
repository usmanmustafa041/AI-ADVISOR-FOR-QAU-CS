"""Composition root: builds the long-lived objects shared by the API, CLI and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from advisor.config import Settings, get_settings
from advisor.db import Database
from advisor.llm.router import ProviderRouter
from advisor.rag.knowledge import KnowledgeBase
from advisor.rag.service import AdvisorService
from advisor.runtime_settings import RuntimeSettings
from advisor.security import SecretBox


@dataclass
class Context:
    settings: Settings
    db: Database
    box: SecretBox
    runtime: RuntimeSettings
    router: ProviderRouter
    kb: KnowledgeBase
    service: AdvisorService


def build_context(settings: Settings | None = None, *, load_kb: bool = True) -> Context:
    s = settings or get_settings()
    db = Database(s.db_path)
    box = SecretBox(s.data_dir, s.secret_key)
    runtime = RuntimeSettings(db, box, s)
    router = ProviderRouter(s, runtime)
    kb = KnowledgeBase(s)
    if load_kb:
        kb.load()
    return Context(s, db, box, runtime, router, kb, AdvisorService(s, db, runtime, router, kb))
