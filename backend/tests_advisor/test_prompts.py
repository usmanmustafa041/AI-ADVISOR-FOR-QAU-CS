

def test_resolved_follow_up_is_shown_to_the_model_and_a_different_topic_rule_exists():
    import datetime as dt
    from advisor.rag import prompts

    msgs = prompts.build_messages(
        "what is the deadline?", [("user", "What are the FYP submission rules?")], [],
        today=dt.date(2026, 10, 1), resolved="What is the deadline for submitting the Final Year Project (FYP)?",
    )
    assert "the student means: What is the deadline for submitting the Final Year Project" in msgs[-1].content
    assert "different topic" in msgs[0].content
    plain = prompts.build_messages("fees?", [], [], today=dt.date(2026, 10, 1), resolved="fees?")
    assert "the student means" not in plain[-1].content


def test_smalltalk_kinds_and_conversational_detection():
    from advisor.rag.query import is_conversational, smalltalk_kind

    for q in ("how are you", "How are you?", "hi, how are you doing today?", "how r u", "kaise ho", "kya haal hai", "what's up", "آپ کیسے ہیں"):
        assert smalltalk_kind(q) == "how", q
    for q in ("thanks", "thank you so much", "shukriya"):
        assert smalltalk_kind(q) == "thanks", q
    for q in ("ok", "great", "you are awesome", "i am fine"):
        assert smalltalk_kind(q) == "ack", q
    for q in ("hi", "hello", "who are you?", "what can you do", "help"):
        assert smalltalk_kind(q) == "hello", q
    # real questions must never be mistaken for chit-chat
    for q in ("how are the fees calculated?", "how are you graded in DSA?", "help me choose courses", "what is the fee"):
        assert smalltalk_kind(q) is None, q
    assert is_conversational("you are very helpful bro") and is_conversational("lol nice")
    assert not is_conversational("who is the dean") and not is_conversational("fee kitni hai")
