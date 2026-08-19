"""Sphinx directives generated from application-owned contracts.

The documentation should explain decisions, not maintain copies of route,
generator, or configuration inventories. These directives turn those live
Python objects into tables during every documentation build.
"""

from __future__ import annotations

import os
from dataclasses import fields
from pathlib import Path
from typing import Any
from unittest.mock import patch

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

Cell = tuple[str, bool]


def _cell(value: str, *, literal: bool = False) -> Cell:
    return value, literal


def _table(
    headers: tuple[str, ...], rows: list[tuple[Cell, ...]], widths: tuple[int, ...]
) -> nodes.table:
    """Build a docutils table with optional inline-code cells."""
    table = nodes.table()
    group = nodes.tgroup(cols=len(headers))
    table += group
    for width in widths:
        group += nodes.colspec(colwidth=width)

    head = nodes.thead()
    group += head
    head += _row(tuple(_cell(header) for header in headers))

    body = nodes.tbody()
    group += body
    for row in rows:
        body += _row(row)
    return table


def _row(values: tuple[Cell, ...]) -> nodes.row:
    row = nodes.row()
    for value, literal in values:
        entry = nodes.entry()
        paragraph = nodes.paragraph()
        paragraph += nodes.literal(value, value) if literal else nodes.Text(value)
        entry += paragraph
        row += entry
    return row


class OpenAPIReferenceDirective(SphinxDirective):
    """Render every public FastAPI operation from the generated OpenAPI schema."""

    has_content = False

    def run(self) -> list[nodes.Node]:
        """Build the route reference table."""
        from rs_tools.main import app

        operations = []
        method_order = ("get", "post", "put", "patch", "delete", "head", "options")
        for path, path_item in app.openapi()["paths"].items():
            for method in method_order:
                operation = path_item.get(method)
                if not operation:
                    continue
                operations.append(
                    (
                        _cell(method.upper(), literal=True),
                        _cell(path, literal=True),
                        _cell(operation.get("summary", "")),
                        _cell(", ".join(operation.get("tags", ()))),
                    )
                )
        return [_table(("Method", "Path", "Operation", "Area"), operations, (9, 38, 33, 20))]


class GeneratorReferenceDirective(SphinxDirective):
    """Render the generator catalogue from the backend registry."""

    has_content = False

    def run(self) -> list[nodes.Node]:
        """Build the generator catalogue table."""
        from rs_tools.generators.registry import GENERATORS

        category_order = {"repository": 0, "metadata": 1, "documentation": 2, "project": 3}
        category_names = {
            "repository": "Entire repositories",
            "metadata": "Metadata files",
            "documentation": "Documentation files",
            "project": "Community files",
        }
        generators = sorted(GENERATORS, key=lambda item: category_order[item.category])
        rows = [
            (
                _cell(category_names[generator.category]),
                _cell(generator.id, literal=True),
                _cell(generator.filename, literal=True),
                _cell(generator.description),
            )
            for generator in generators
        ]
        return [_table(("Group", "Identifier", "Output", "Purpose"), rows, (20, 18, 22, 40))]


class ConfigurationReferenceDirective(SphinxDirective):
    """Render environment variables and defaults from ``Settings``."""

    has_content = False

    def run(self) -> list[nodes.Node]:
        """Build the environment configuration table."""
        from rs_tools.config import Settings

        # Documentation must describe defaults, never values injected into the
        # build environment (which could include production secrets).
        clean_environment = {
            name: value for name, value in os.environ.items() if not name.startswith("RS_TOOLS_")
        }
        with patch.dict(os.environ, clean_environment, clear=True):
            defaults = Settings()

        rows = []
        for setting in fields(Settings):
            variable = f"RS_TOOLS_{setting.name.upper()}"
            if setting.metadata.get("file_variant"):
                variable = f"{variable} / {variable}_FILE"
            default = setting.metadata.get(
                "documented_default", _format_default(getattr(defaults, setting.name))
            )
            rows.append(
                (
                    _cell(variable, literal=True),
                    _cell(str(default), literal=True),
                    _cell(str(setting.metadata["description"])),
                )
            )
        return [_table(("Environment variable", "Default", "Purpose"), rows, (36, 22, 42))]


def _format_default(value: Any) -> str:
    if value is None or value == ():
        return "unset"
    if isinstance(value, tuple):
        return ", ".join(value)
    if isinstance(value, Path):
        return str(value)
    return str(value)


def setup(app: Sphinx) -> dict[str, bool]:
    """Register the generated-reference directives."""
    app.add_directive("openapi-reference", OpenAPIReferenceDirective)
    app.add_directive("generator-reference", GeneratorReferenceDirective)
    app.add_directive("configuration-reference", ConfigurationReferenceDirective)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
