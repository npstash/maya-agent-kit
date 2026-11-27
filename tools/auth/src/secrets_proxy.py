"""Secrets of a service: from the vault, or from environment variables.

Reference code. Copy this file into the source of a project. Do not change a copy. Change this
file, then copy it again. A copy needs only the standard library. It loads the vault tool only
when the configuration names a vault.

The configuration of the service has this section::

    credentials:
      vault: vault-<name>        # optional; without it, the secrets come from the environment
      vaultkeeper: /run/gustaw/vaultkeeper.sock   # optional; the socket of the daemon vaultkeeper
      secrets:
        <name>: {entry: "<vault entry>", key: "<secret key>", env: "<VARIABLE>"}

The vault provider and the vaultkeeper provider need `entry` and `key`. The environment provider
needs `env`.

The provider is selected one time, at the start:

- The configuration names a vault and the socket of vaultkeeper: each secret comes from the daemon
  vaultkeeper (project gustaw_vaultkeeper). The service needs no vault files and no vault tool.
  There is no fallback.
- The configuration names a vault only: each secret comes from the vault. There is no fallback.
- The configuration names no vault: each secret comes from the variable `env`, or from the file that
  the variable `<env>_FILE` gives. The provider removes both variables from `os.environ`.
  Thus the child processes of the service do not get the secrets.

    secrets = open_secrets(config["credentials"], find)   # find: the dependency lookup of the project
    token = secrets.get_secret("api_token")
"""
from __future__ import annotations

import importlib
import json
import os
import socket
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol, cast

# The repository of the vault tool, and the folder of the tool in it.
VAULT_TOOL_REPO = "maya-agent-kit"
VAULT_TOOL_DIR = Path("tools") / "auth"

# The vaultkeeper provider: the time limit of one connection, and the largest response line.
VAULTKEEPER_TIMEOUT_S = 10.0
VAULTKEEPER_RESPONSE_MAX = 1024 * 1024


class SecretError(RuntimeError):
    """A secret is not available. The message never holds a secret value."""


class Secrets(ABC):
    """The secrets of a service, by their names in the configuration."""

    @abstractmethod
    def get_secret(self, name: str) -> str:
        """The value of the secret `name`. Raise SecretError if it is not available."""


@dataclass(frozen=True)
class SecretRef:
    """Where a secret is: the vault entry and its key, and the environment variable.

    The vault provider needs `entry` and `key`. The environment provider needs `env`.
    """

    name: str
    entry: str | None
    key: str | None
    env: str | None

    def need(self, field: str) -> str:
        value: str | None = getattr(self, field)
        if value is None:
            raise SecretError(f"credentials.secrets.{self.name} has no '{field}'")
        return value


class Credential(Protocol):
    """What this module reads from a credential of the vault tool."""

    def secrets(self) -> Mapping[str, str]: ...


GetCredential = Callable[[str, Path], Credential]
"""get_credential(system, vault_home) of the vault tool."""


class _Credstore(Protocol):
    """The function of the module credstore that this module uses."""

    def get_credential(self, system: str, vault_home: Path) -> Credential: ...

FindDependency = Callable[[str], Path]
"""The dependency lookup of the project: the folder of a repository, by its name."""


def parse_refs(secrets: object) -> dict[str, SecretRef]:
    """The secret references of the `secrets` mapping of the configuration."""
    if not isinstance(secrets, Mapping):
        raise SecretError("credentials.secrets must be a mapping")
    refs: dict[str, SecretRef] = {}
    for name, ref in secrets.items():
        if not isinstance(name, str) or not isinstance(ref, Mapping):
            raise SecretError(f"credentials.secrets.{name} must be a mapping")
        fields: dict[str, str | None] = {}
        for field in ("entry", "key", "env"):
            value = ref.get(field)
            if value is not None and (not isinstance(value, str) or not value):
                raise SecretError(f"credentials.secrets.{name}.{field} must be a text that is not empty")
            fields[field] = value
        refs[name] = SecretRef(name, fields["entry"], fields["key"], fields["env"])
    return refs


class VaultSecrets(Secrets):
    """Secrets from the vault. The constructor reads each secret. A missing secret is an error."""

    def __init__(self, refs: Mapping[str, SecretRef], vault_home: Path, get_credential: GetCredential):
        self._values: dict[str, str] = {}
        credentials: dict[str, Credential] = {}
        for name, ref in refs.items():
            entry, key = ref.need("entry"), ref.need("key")
            try:
                if entry not in credentials:
                    credentials[entry] = get_credential(entry, vault_home)
                value = credentials[entry].secrets().get(key)
            except RuntimeError as exc:
                raise SecretError(f"vault entry '{entry}': {exc}") from None
            if not value:
                raise SecretError(f"vault entry '{entry}' has no value for '{key}'")
            self._values[name] = value

    def get_secret(self, name: str) -> str:
        try:
            return self._values[name]
        except KeyError:
            raise SecretError(f"the configuration names no secret '{name}'") from None


class EnvSecrets(Secrets):
    """Secrets from environment variables. The constructor reads each secret, then removes its variables."""

    def __init__(self, refs: Mapping[str, SecretRef], environ: MutableMapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        self._values: dict[str, str] = {}
        variables = {name: ref.need("env") for name, ref in refs.items()}
        for name, variable in variables.items():
            self._values[name] = _read_env(variable, env)
        for variable in variables.values():
            env.pop(variable, None)
            env.pop(f"{variable}_FILE", None)

    def get_secret(self, name: str) -> str:
        try:
            return self._values[name]
        except KeyError:
            raise SecretError(f"the configuration names no secret '{name}'") from None


class VaultkeeperSecrets(Secrets):
    """Secrets from the daemon vaultkeeper. The constructor reads each secret. A missing secret is an error.

    For each vault entry, it sends one JSON line {"op": "get", "vault": ..., "system": ...} to the socket
    and reads one JSON line: {"ok": true, "result": {"url", "authority_info", "secrets"}}, or
    {"ok": false, "error": "not-granted | invalid-request | failed"}.
    """

    def __init__(self, refs: Mapping[str, SecretRef], vault: str, socket_path: Path,
                 timeout_s: float = VAULTKEEPER_TIMEOUT_S):
        self._values: dict[str, str] = {}
        secrets: dict[str, Mapping[str, object]] = {}
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(timeout_s)
                conn.connect(str(socket_path))
                lines = conn.makefile("rb")
                for name, ref in refs.items():
                    entry, key = ref.need("entry"), ref.need("key")
                    if entry not in secrets:
                        secrets[entry] = _vaultkeeper_get(conn, lines, vault, entry)
                    value = secrets[entry].get(key)
                    if not isinstance(value, str) or not value:
                        raise SecretError(f"vault entry '{entry}' has no value for '{key}'")
                    self._values[name] = value
        except OSError as exc:
            raise SecretError(f"vaultkeeper at {socket_path} cannot be used: {exc.strerror or exc}") from None

    def get_secret(self, name: str) -> str:
        try:
            return self._values[name]
        except KeyError:
            raise SecretError(f"the configuration names no secret '{name}'") from None


def _vaultkeeper_get(conn: socket.socket, lines: BinaryIO, vault: str, entry: str) -> Mapping[str, object]:
    """The secrets of `entry`: one request line, one response line."""
    request = {"op": "get", "vault": vault, "system": entry}
    conn.sendall(json.dumps(request).encode() + b"\n")
    line = lines.readline(VAULTKEEPER_RESPONSE_MAX + 1)
    if not line.endswith(b"\n"):
        raise SecretError(f"vaultkeeper gave no complete response for vault entry '{entry}'")
    try:
        response = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SecretError(f"vaultkeeper gave a response that is not JSON for vault entry '{entry}'") from None
    if not isinstance(response, Mapping):
        raise SecretError(f"vaultkeeper gave a response that is not an object for vault entry '{entry}'")
    if response.get("ok") is not True:
        error = response.get("error")
        raise SecretError(f"vaultkeeper refused vault entry '{entry}': {error if isinstance(error, str) else 'error'}")
    result = response.get("result")
    found = result.get("secrets") if isinstance(result, Mapping) else None
    if not isinstance(found, Mapping):
        raise SecretError(f"vaultkeeper gave no secrets for vault entry '{entry}'")
    return found


def _read_env(variable: str, env: Mapping[str, str]) -> str:
    """The value of `variable`, or the content of the file that `<variable>_FILE` gives."""
    value = env.get(variable)
    file = env.get(f"{variable}_FILE")
    if value and file:
        raise SecretError(f"set {variable} or {variable}_FILE, not both")
    if file:
        try:
            value = Path(file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SecretError(f"{variable}_FILE: the file cannot be read: {exc.strerror}") from None
    if not value:
        raise SecretError(f"the environment variable {variable} or {variable}_FILE is not set or empty")
    return value


def load_get_credential(tool_dir: Path) -> GetCredential:
    """get_credential of the vault tool in `tool_dir`."""
    src = tool_dir / "src"
    if not (src / "credstore.py").is_file():
        raise SecretError(f"the vault tool is not found in {tool_dir}")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    module = importlib.import_module("credstore")
    if not callable(getattr(module, "get_credential", None)):
        raise SecretError(f"the vault tool in {tool_dir} has no get_credential")
    return cast(_Credstore, module).get_credential


def open_secrets(credentials: Mapping[str, object], find: FindDependency,
                 environ: MutableMapping[str, str] | None = None) -> Secrets:
    """The secrets of the `credentials` section. Select vaultkeeper, the vault or the environment, then read each secret."""
    refs = parse_refs(credentials.get("secrets", {}))
    vault = credentials.get("vault")
    vaultkeeper = credentials.get("vaultkeeper")
    if vaultkeeper is not None and (not isinstance(vaultkeeper, str) or not vaultkeeper):
        raise SecretError("credentials.vaultkeeper must be a socket path")
    if vault is None or vault == "":
        if vaultkeeper is not None:
            raise SecretError("credentials.vaultkeeper needs credentials.vault")
        return EnvSecrets(refs, environ)
    if not isinstance(vault, str):
        raise SecretError("credentials.vault must be a text")
    if vaultkeeper is not None:
        return VaultkeeperSecrets(refs, vault, Path(vaultkeeper))
    try:
        vault_home = find(vault)
        tool_dir = find(VAULT_TOOL_REPO) / VAULT_TOOL_DIR
    except (OSError, RuntimeError) as exc:
        raise SecretError(str(exc)) from None
    return VaultSecrets(refs, vault_home, load_get_credential(tool_dir))
