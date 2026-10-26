from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import env_bool, env_int, env_list, env_str, load_env_file


def test_env_file_is_parsed_without_overriding_real_environment(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\n\nFINLUME_T_PLAIN=plain\nFINLUME_T_QUOTED="two words"\n'
        "FINLUME_T_EXISTING=from-file\n",
        encoding="utf-8",
    )
    for name in ("FINLUME_T_PLAIN", "FINLUME_T_QUOTED"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FINLUME_T_EXISTING", "from-environment")

    load_env_file(env_file)

    assert env_str("FINLUME_T_PLAIN") == "plain"
    assert env_str("FINLUME_T_QUOTED") == "two words"
    assert env_str("FINLUME_T_EXISTING") == "from-environment"
    for name in ("FINLUME_T_PLAIN", "FINLUME_T_QUOTED"):
        monkeypatch.delenv(name)


def test_missing_env_file_is_ignored(tmp_path):
    load_env_file(tmp_path / "does-not-exist")


def test_required_variable_fails_loudly(monkeypatch):
    monkeypatch.delenv("FINLUME_T_REQUIRED", raising=False)

    with pytest.raises(ImproperlyConfigured, match="FINLUME_T_REQUIRED"):
        env_str("FINLUME_T_REQUIRED")


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("0", False), ("YES", True)])
def test_env_bool_parses_common_spellings(monkeypatch, raw, expected):
    monkeypatch.setenv("FINLUME_T_BOOL", raw)

    assert env_bool("FINLUME_T_BOOL", default=not expected) is expected


def test_env_bool_rejects_ambiguous_values(monkeypatch):
    monkeypatch.setenv("FINLUME_T_BOOL", "maybe")

    with pytest.raises(ImproperlyConfigured):
        env_bool("FINLUME_T_BOOL", default=False)


def test_env_int_rejects_non_integers(monkeypatch):
    monkeypatch.setenv("FINLUME_T_INT", "5432x")

    with pytest.raises(ImproperlyConfigured):
        env_int("FINLUME_T_INT", default=1)


def test_env_list_splits_and_trims(monkeypatch):
    monkeypatch.setenv("FINLUME_T_LIST", " a.example , b.example,, ")

    assert env_list("FINLUME_T_LIST") == ["a.example", "b.example"]
