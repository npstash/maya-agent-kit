"""Tests of secrets_proxy: the selection of the provider, the vault provider and the environment provider."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

import credstore_fake
import secrets_proxy
from secrets_proxy import EnvSecrets, SecretError, VaultSecrets, open_secrets, parse_refs

TOOL_DIR = Path(__file__).resolve().parent.parent

SECRETS: Mapping[str, object] = {
    "api_token": {"entry": "API 01", "key": "token", "env": "SVC_API_TOKEN"},
    "db_password": {"entry": "DB 01", "key": "password", "env": "SVC_DB_PASSWORD"},
}


def test_env_provider_reads_the_variables_and_removes_them() -> None:
    environ = {"SVC_API_TOKEN": "t1", "SVC_DB_PASSWORD": "p1", "OTHER": "x"}
    secrets = EnvSecrets(parse_refs(SECRETS), environ)
    assert secrets.get_secret("api_token") == "t1"
    assert secrets.get_secret("db_password") == "p1"
    assert environ == {"OTHER": "x"}


def test_env_provider_reads_a_file_variable(tmp_path: Path) -> None:
    file = tmp_path / "token"
    file.write_text("t2\n", encoding="utf-8")
    environ = {"SVC_API_TOKEN_FILE": str(file), "SVC_DB_PASSWORD": "p1"}
    secrets = EnvSecrets(parse_refs(SECRETS), environ)
    assert secrets.get_secret("api_token") == "t2"
    assert "SVC_API_TOKEN_FILE" not in environ


def test_env_provider_refuses_a_value_and_a_file() -> None:
    environ = {"SVC_API_TOKEN": "t1", "SVC_API_TOKEN_FILE": "/x", "SVC_DB_PASSWORD": "p1"}
    with pytest.raises(SecretError, match="not both"):
        EnvSecrets(parse_refs(SECRETS), environ)


def test_env_provider_refuses_a_missing_or_empty_secret() -> None:
    with pytest.raises(SecretError, match="SVC_DB_PASSWORD"):
        EnvSecrets(parse_refs(SECRETS), {"SVC_API_TOKEN": "t1", "SVC_DB_PASSWORD": ""})


def test_env_provider_needs_the_variable_name() -> None:
    with pytest.raises(SecretError, match="has no 'env'"):
        EnvSecrets(parse_refs({"a": {"entry": "E", "key": "k"}}), {})


def test_error_messages_hold_no_secret_value(tmp_path: Path) -> None:
    with pytest.raises(SecretError) as error:
        EnvSecrets(parse_refs(SECRETS), {"SVC_API_TOKEN": "secret-value", "SVC_API_TOKEN_FILE": "/x"})
    assert "secret-value" not in str(error.value)


def test_vault_provider_reads_each_entry(tmp_path: Path) -> None:
    store = credstore_fake.Store(tmp_path)
    store.set_system("API 01", secrets={"token": "t3"})
    store.set_system("DB 01", secrets={"password": "p3"})
    secrets = VaultSecrets(parse_refs(SECRETS), tmp_path, credstore_fake.get_credential)
    assert secrets.get_secret("api_token") == "t3"
    assert secrets.get_secret("db_password") == "p3"


def test_vault_provider_has_no_fallback_to_the_environment(tmp_path: Path) -> None:
    credstore_fake.Store(tmp_path).set_system("API 01", secrets={"token": "t3"})
    with pytest.raises(SecretError, match="DB 01"):
        VaultSecrets(parse_refs(SECRETS), tmp_path, credstore_fake.get_credential)


def test_unknown_name_is_an_error() -> None:
    secrets = EnvSecrets(parse_refs({"a": {"env": "SVC_A"}}), {"SVC_A": "v"})
    with pytest.raises(SecretError, match="no secret 'b'"):
        secrets.get_secret("b")


def test_open_secrets_without_a_vault_uses_the_environment() -> None:
    environ = {"SVC_API_TOKEN": "t1", "SVC_DB_PASSWORD": "p1"}

    def find(name: str) -> Path:
        raise AssertionError(f"no lookup expected: {name}")

    secrets = open_secrets({"secrets": SECRETS}, find, environ)
    assert isinstance(secrets, EnvSecrets)
    assert secrets.get_secret("api_token") == "t1"


def test_open_secrets_with_a_vault_uses_the_vault_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets_proxy, "load_get_credential", lambda tool: credstore_fake.get_credential)
    store = credstore_fake.Store(tmp_path / "vault-svc")
    store.set_system("API 01", secrets={"token": "t4"})
    store.set_system("DB 01", secrets={"password": "p4"})
    found: list[str] = []

    def find(name: str) -> Path:
        found.append(name)
        return tmp_path / name

    secrets = open_secrets({"vault": "vault-svc", "secrets": SECRETS}, find, {"SVC_API_TOKEN": "env"})
    assert isinstance(secrets, VaultSecrets)
    assert secrets.get_secret("api_token") == "t4"
    assert found == ["vault-svc", "maya-agent-kit"]


def test_load_get_credential_finds_the_tool() -> None:
    assert callable(secrets_proxy.load_get_credential(TOOL_DIR))


def test_load_get_credential_refuses_a_folder_without_the_tool(tmp_path: Path) -> None:
    with pytest.raises(SecretError, match="not found"):
        secrets_proxy.load_get_credential(tmp_path)


def test_parse_refs_refuses_a_bad_section() -> None:
    with pytest.raises(SecretError):
        parse_refs(["a"])
    with pytest.raises(SecretError):
        parse_refs({"a": {"env": ""}})
