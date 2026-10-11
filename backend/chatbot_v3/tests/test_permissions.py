import asyncio

from chatbot_v3.contracts import ChatRequest
from chatbot_v3.index import Index
from chatbot_v3.service import Service
from chatbot_v3.settings import settings
from chatbot_v3.store import Store
from chatbot_v3.understanding import understand


def test_cancel_releases_capacity_before_acquisition(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "data_dir", tmp_path)
    store = Store(tmp_path / "knowledge.sqlite3")
    service = Service(store, None, Index(store))

    async def trial():
        stream = service.events(ChatRequest(message="Explain a stack"), "guest", False)
        await anext(stream)
        assert service.waiting == 1
        await stream.aclose()
        assert service.waiting == 0 and service.slot._value == 1

    asyncio.run(trial())


def test_academic_task_cannot_bypass_evidence_as_tutor(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "data_dir", tmp_path)

    class ContradictoryModel:
        async def structured(self, *args):
            return {
                "original": "x",
                "normalized": "registration question",
                "language": "english",
                "mode": "tutor",
                "tasks": [
                    {
                        "question": "Can I take a later course?",
                        "search_query": "registration semester rules",
                        "topic": "academic_policy",
                    }
                ],
            }

    plan = asyncio.run(
        understand(
            ContradictoryModel(),
            ChatRequest(message="Can I take a seventh-semester course in fifth?"),
            [],
            {},
        )
    )
    assert plan.mode == "university"
    store = Store(tmp_path / "knowledge.sqlite3")
    assert Index(store).eligible(plan.tasks[0]) == []


def test_interpretation_cannot_silently_change_a_literal_course_prefix():
    class RenamingModel:
        async def structured(self, *args):
            return {
                "original": "x",
                "normalized": "CSC-104 credits",
                "language": "roman_urdu",
                "mode": "university",
                "course_codes": ["CSC-104"],
                "tasks": [
                    {
                        "question": "credits",
                        "search_query": "CSC-104 credits",
                        "topic": "curriculum",
                        "course_codes": ["CSC-104"],
                    }
                ],
            }

    plan = asyncio.run(
        understand(RenamingModel(), ChatRequest(message="sir cs104 k credit hours?"), [], {})
    )
    assert plan.course_codes == ["CS-104"]
    assert plan.tasks[0].course_codes == ["CS-104"]
