from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from copier.errors import TaskError
from jinja2 import UndefinedError
from plumbum.commands.processes import ProcessExecutionError

from rs_tools.generators.base import (
    GeneratorInputError,
    GeneratorOptions,
    GeneratorUnavailable,
)
from rs_tools.generators.repository import RepositoryFile, generate_repository


def test_repository_generator_uses_selected_configured_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {}

    def fake_run_copy(source: str, destination: Path, **options: Any) -> None:
        received["source"] = source
        received["destination"] = destination
        received.update(options)
        destination.mkdir(parents=True)
        (destination / "README.md").write_text("# Generated\n", encoding="utf-8")
        (destination / ".git").mkdir()
        (destination / ".git" / "config").write_text("ignored", encoding="utf-8")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", fake_run_copy)

    artifact = generate_repository(
        {"project_slug": "sample.project"}, GeneratorOptions(template_id="r")
    )

    assert received["source"] == "https://github.com/LUMC-DCC/rs-repo-templates.git"
    assert received["data"] == {"project_slug": "sample.project", "template_type": "r"}
    assert received["vcs_ref"]
    assert received["defaults"] is True
    assert received["unsafe"] is True
    with zipfile.ZipFile(BytesIO(artifact.content)) as archive:
        assert archive.namelist() == ["sample.project/README.md"]


def test_repository_generator_completes_partial_structured_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, Any] = {}

    def fake_run_copy(_source: str, destination: Path, **options: Any) -> None:
        received.update(options)
        destination.mkdir(parents=True)
        (destination / "README.md").write_text("# Generated\n", encoding="utf-8")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", fake_run_copy)

    generate_repository(
        {
            "project_slug": "sample_project",
            "urls": {"repository": "https://github.com/example/sample_project"},
            "software_functions": {
                "entries": [
                    {
                        "inputs": [
                            {
                                "format": [
                                    {
                                        "term": "CSV",
                                        "uri": "http://edamontology.org/format_3752",
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
        },
        GeneratorOptions(),
    )

    assert received["data"]["urls"] == {
        "repository": "https://github.com/example/sample_project",
        "homepage": "",
        "documentation": "",
    }
    function_input = received["data"]["software_functions"]["entries"][0]["inputs"][0]
    assert "data" not in function_input
    assert received["data"]["template_type"] == "generic"


def test_repository_generator_rejects_unknown_template() -> None:
    with pytest.raises(GeneratorInputError, match="Unsupported repository template"):
        generate_repository(
            {"project_slug": "sample-project"}, GeneratorOptions(template_id="rust")
        )


def test_generated_output_with_a_secret_is_refused_before_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_copy(_source: str, destination: Path, **_options: Any) -> None:
        destination.mkdir(parents=True)
        (destination / "deploy.key").write_text(
            "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n", encoding="utf-8"
        )

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", fake_run_copy)

    # The same check guards the GitHub publisher, so a template that starts
    # emitting credentials cannot leak them through either route.
    with pytest.raises(GeneratorInputError, match="may contain a secret"):
        generate_repository({"project_slug": "sample-project"}, GeneratorOptions())


def test_generated_environment_example_is_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_copy(_source: str, destination: Path, **_options: Any) -> None:
        destination.mkdir(parents=True)
        (destination / ".env.example").write_text("API_TOKEN=replace-me\n", encoding="utf-8")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", fake_run_copy)

    artifact = generate_repository({"project_slug": "sample-project"}, GeneratorOptions())

    with zipfile.ZipFile(BytesIO(artifact.content)) as archive:
        assert archive.namelist() == ["sample-project/.env.example"]


def test_generated_paths_that_escape_the_project_are_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_copy(_source: str, destination: Path, **_options: Any) -> None:
        (destination / "nested").mkdir(parents=True)
        (destination / "nested" / "README.md").write_text("# ok\n", encoding="utf-8")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", fake_run_copy)
    monkeypatch.setattr(
        "rs_tools.generators.repository._collect_repository_files",
        lambda _directory: [RepositoryFile(path="../escape.txt", content=b"nope")],
    )

    with pytest.raises(GeneratorInputError, match="unsafe path"):
        generate_repository({"project_slug": "sample-project"}, GeneratorOptions())


def test_a_copier_question_that_rejects_the_slug_names_that_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_run_copy(_source: str, _destination: Path, **_options: Any) -> None:
        raise ValueError("Validation error for question 'project_slug': invalid identifier")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", failing_run_copy)

    # The template writes its own explanation to the process log. The response
    # names the field to look at instead of surfacing an internal error.
    with pytest.raises(GeneratorInputError, match="project_slug"):
        generate_repository({"project_slug": "not-an-identifier"}, GeneratorOptions())


def test_a_finalization_task_failure_does_not_guess_that_the_slug_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_run_copy(_source: str, _destination: Path, **_options: Any) -> None:
        raise TaskError(["finalize"], 1, "", "invalid nested metadata")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", failing_run_copy)

    with pytest.raises(GeneratorInputError, match="rejected this metadata") as caught:
        generate_repository({"project_slug": "valid_slug"}, GeneratorOptions())
    assert "project_slug" not in str(caught.value)


def test_an_unreachable_template_source_is_not_blamed_on_the_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_run_copy(_source: str, _destination: Path, **_options: Any) -> None:
        raise ProcessExecutionError(["git", "clone"], 128, "", "could not clone")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", failing_run_copy)

    with pytest.raises(GeneratorUnavailable, match="deployment"):
        generate_repository({"project_slug": "sample-project"}, GeneratorOptions())


def test_a_broken_template_is_reported_as_a_deployment_problem(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_run_copy(_source: str, _destination: Path, **_options: Any) -> None:
        raise UndefinedError("missing template value")

    monkeypatch.setattr("rs_tools.generators.repository.run_copy", failing_run_copy)

    with pytest.raises(GeneratorUnavailable, match="deployment"):
        generate_repository({"project_slug": "sample-project"}, GeneratorOptions())
