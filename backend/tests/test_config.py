from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from rs_tools import config
from rs_tools.config import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("revision", [None, "", " \t "])
def test_repository_template_revision_falls_back_to_application_default(
    monkeypatch: pytest.MonkeyPatch, revision: str | None
) -> None:
    monkeypatch.setattr(config, "DEFAULT_REPOSITORY_TEMPLATE_REVISION", "reviewed-release")
    if revision is None:
        monkeypatch.delenv("RS_TOOLS_REPOSITORY_TEMPLATE_REVISION", raising=False)
    else:
        monkeypatch.setenv("RS_TOOLS_REPOSITORY_TEMPLATE_REVISION", revision)

    assert Settings().repository_template_revision == "reviewed-release"


def test_repository_template_default_is_a_release_tag() -> None:
    assert re.fullmatch(r"v\d+\.\d+\.\d+", config.DEFAULT_REPOSITORY_TEMPLATE_REVISION)


def test_deployment_examples_leave_revision_default_to_application() -> None:
    example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
    compose = (REPOSITORY_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert not re.search(r"^RS_TOOLS_REPOSITORY_TEMPLATE_REVISION=", example, re.MULTILINE)
    assert "# RS_TOOLS_REPOSITORY_TEMPLATE_REVISION=\n" in example
    assert "${RS_TOOLS_REPOSITORY_TEMPLATE_REVISION:-}" in compose


def test_repository_template_revision_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RS_TOOLS_REPOSITORY_TEMPLATE_REVISION", "  custom-release  ")

    assert Settings().repository_template_revision == "custom-release"
    assert Settings().repository_template_source.revision == "custom-release"


def test_github_secrets_can_be_loaded_from_files(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    client_secret = tmp_path / "client-secret"
    cookie_secret = tmp_path / "cookie-secret"
    client_secret.write_text("client-secret\n")
    cookie_secret.write_text("cookie-secret\n")
    monkeypatch.setenv("RS_TOOLS_GITHUB_CLIENT_SECRET_FILE", str(client_secret))
    monkeypatch.setenv("RS_TOOLS_GITHUB_COOKIE_SECRET_FILE", str(cookie_secret))

    settings = Settings()

    assert settings.github_client_secret == "client-secret"
    assert settings.github_cookie_secret == "cookie-secret"


def test_github_secret_rejects_ambiguous_inline_and_file_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    secret_file = tmp_path / "secret"
    secret_file.write_text("from-file")
    monkeypatch.setenv("RS_TOOLS_GITHUB_CLIENT_SECRET", "inline")
    monkeypatch.setenv("RS_TOOLS_GITHUB_CLIENT_SECRET_FILE", str(secret_file))

    with pytest.raises(ValueError, match="either RS_TOOLS_GITHUB_CLIENT_SECRET"):
        Settings()


def test_every_setting_is_described_and_present_in_the_environment_example() -> None:
    setting_fields = fields(Settings)
    assert all(field.metadata.get("description") for field in setting_fields)

    expected = {f"RS_TOOLS_{field.name.upper()}" for field in setting_fields}
    expected.update(
        f"RS_TOOLS_{field.name.upper()}_FILE"
        for field in setting_fields
        if field.metadata.get("file_variant")
    )
    example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*(RS_TOOLS_[A-Z0-9_]+)=", example, flags=re.MULTILINE))

    assert documented == expected
