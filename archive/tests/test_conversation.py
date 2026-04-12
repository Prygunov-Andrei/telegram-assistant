from __future__ import annotations

from src.brain.conversation import Conversation, ConversationStore


def test_add_messages(conversation: Conversation):
    conversation.add_user_message("hello")
    msgs = conversation.get_messages()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "hello"


def test_conversation_store(conversation_store: ConversationStore):
    conv1 = conversation_store.get_or_create(111)
    conv2 = conversation_store.get_or_create(222)
    conv1_again = conversation_store.get_or_create(111)
    assert conv1 is conv1_again
    assert conv1 is not conv2
    assert conversation_store.active_count() == 2


def test_trim_old_messages():
    conv = Conversation(chat_id=1)
    for i in range(200):
        conv.add_user_message(f"msg {i}")
        conv.add_assistant_response([{"type": "text", "text": f"reply {i}"}])
    msgs = conv.get_messages()
    assert len(msgs) < 400
