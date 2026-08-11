"""Configuration and metadata safety tests."""

import json
import tomllib
from pathlib import Path

import pytest

from piw.config import default_config_text, parse_config
from piw.errors import ExitCode, PiwError
from piw.models import ThinkingLevel
from piw.service import read_non_secret_json


def test_default_config_text_round_trips() -> None:
    """The documented starter file must always parse."""

    config = parse_config(tomllib.loads(default_config_text()))
    assert config.config_version == 1
    assert config.pi.thinking is ThinkingLevel.HIGH
    assert config.sandbox.read_only_refs == ()


def test_parse_complete_config_expands_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All public settings are decoded into explicit types."""

    monkeypatch.setenv("PIW_TEST_ROOT", str(tmp_path))
    config = parse_config(
        {
            "config_version": 1,
            "sandbox": {
                "profile": "developer",
                "read_only_refs": ["$PIW_TEST_ROOT"],
                "mcp_servers": ["jira"],
                "cpus": 4,
                "memory": "8g",
                "timeout_seconds": 42,
            },
            "pi": {
                "package": "pi@example",
                "model": "provider/model",
                "thinking": "xhigh",
                "extensions": ["npm:extension@1"],
                "skill_paths": ["$PIW_TEST_ROOT"],
            },
            "template": {"prefix": "test-pi", "node_version": "v22.19.0"},
        }
    )
    assert config.sandbox.profile == "developer"
    assert config.sandbox.read_only_refs == (tmp_path,)
    assert config.sandbox.cpus == 4
    assert config.sandbox.memory == "8g"
    assert config.pi.thinking is ThinkingLevel.XHIGH
    assert config.pi.extensions == ("npm:extension@1",)


@pytest.mark.parametrize(
    "value",
    [
        {"unknown": True},
        {"config_version": 99},
        {"sandbox": {"cpus": -1}},
        {"pi": {"thinking": "infinite"}},
        {"pi": {"extensions": ["same", "same"]}},
        {"sandbox": []},
        {"pi": {"model": ""}},
        {"pi": {"package": ""}},
        {"pi": {"extensions": "wrong"}},
        {"pi": {"extensions": [1]}},
        {"template": {"prefix": "Invalid Prefix"}},
        {"template": {"prefix": "invalid-"}},
        {"template": {"node_version": "latest"}},
        [],
        {"config_version": "one"},
    ],
)
def test_invalid_config_is_rejected(value: object) -> None:
    """Typos and unsupported values fail before any sandbox operation."""

    with pytest.raises(PiwError) as captured:
        parse_config(value)
    assert captured.value.code is ExitCode.CONFIG


def test_non_secret_json_accepts_model_metadata(tmp_path: Path) -> None:
    """Ordinary model metadata may be copied into a sandbox."""

    path = tmp_path / "models.json"
    path.write_text(json.dumps({"providers": {"example": {"baseUrl": "https://example.test"}}}))
    assert "providers" in read_non_secret_json(path, "models")


@pytest.mark.parametrize(
    "field",
    ["apiKey", "access_token", "client-secret", "password", "token", "authorization"],
)
def test_non_secret_json_refuses_sensitive_fields(tmp_path: Path, field: str) -> None:
    """Credential-shaped metadata is never copied by piw."""

    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"nested": {field: "secret"}}))
    with pytest.raises(PiwError) as captured:
        read_non_secret_json(path, "metadata")
    assert captured.value.detail.kind == "sensitive_metadata"


def test_non_secret_json_allows_environment_references_and_auth_flags(tmp_path: Path) -> None:
    """Metadata may name sandbox-injected credentials without containing their values."""

    path = tmp_path / "models.json"
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "example": {
                        "apiKey": "$EXAMPLE_API_KEY",
                        "authHeader": True,
                    }
                }
            }
        )
    )
    assert read_non_secret_json(path, "models")["providers"]
