from __future__ import annotations

from src.transport.telegram_policy import TelegramPolicy, GroupRule


def test_owner_dm_allowed(policy_owner_only: TelegramPolicy):
    assert policy_owner_only.allows(435926703, 435926703, True, "", None)


def test_stranger_dm_denied(policy_owner_only: TelegramPolicy):
    assert not policy_owner_only.allows(999, 999999, True, "", None)


def test_unknown_group_denied(policy_owner_only: TelegramPolicy):
    assert not policy_owner_only.allows(-99999, 435926703, False, "hello", None)


def test_group_with_mention(policy_with_group: TelegramPolicy):
    assert policy_with_group.allows(-12345, 435926703, False, "hey @testbot help", "testbot")


def test_group_without_mention_denied(policy_with_group: TelegramPolicy):
    assert not policy_with_group.allows(-12345, 435926703, False, "hey help", "testbot")


def test_group_unauthorized_user_denied(policy_with_group: TelegramPolicy):
    assert not policy_with_group.allows(-12345, 777777, False, "@testbot help", "testbot")


def test_is_owner(policy_owner_only: TelegramPolicy):
    assert policy_owner_only.is_owner(435926703)
    assert not policy_owner_only.is_owner(999)
