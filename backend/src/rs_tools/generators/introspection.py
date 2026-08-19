"""Discover top-level RSM inputs from framework-neutral generator functions.

Used only for generators that do not declare their fields explicitly. Reading the
generator's own source keeps the field list shown in the interface honest without
a parallel declaration that can fall out of date.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from typing import Any

from rs_tools.schema.service import SchemaService


def discover_generator_fields(
    generator: Callable[..., object],
    schema: SchemaService,
) -> tuple[str, ...]:
    """Find literal top-level fields read from a generator's RSM argument.

    ``smp.get("field")`` and ``smp["field"]`` are discovered directly. If the
    whole RSM object is passed into another function (for example Copier's
    answer data), every top-level schema field is considered relevant.

    Parameters
    ----------
    generator : callable
        Generator function whose first parameter is the RSM document.
    schema : SchemaService
        Used to enumerate top-level paths when the whole document is consumed.

    Returns
    -------
    tuple of str
        JSON Pointers for the discovered top-level fields. Empty when the source
        is unavailable, for example for a C-implemented callable.
    """
    parameters = tuple(inspect.signature(generator).parameters)
    if not parameters:
        return ()

    try:
        source = textwrap.dedent(inspect.getsource(generator))
    except OSError, TypeError:
        return ()

    visitor = _RSMFieldVisitor(parameters[0])
    visitor.visit(ast.parse(source))
    if visitor.uses_complete_document:
        return schema.top_level_paths()
    return tuple(f"/{name}" for name in visitor.fields)


class _RSMFieldVisitor(ast.NodeVisitor):
    def __init__(self, smp_name: str) -> None:
        self.smp_name = smp_name
        self.fields: list[str] = []
        self.uses_complete_document = False

    def visit_Call(self, node: ast.Call) -> Any:
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and _is_name(node.func.value, self.smp_name)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self._record(node.args[0].value)

        direct_arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        if any(_is_name(argument, self.smp_name) for argument in direct_arguments):
            self.uses_complete_document = True
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        if (
            _is_name(node.value, self.smp_name)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            self._record(node.slice.value)
        self.generic_visit(node)

    def _record(self, field: str) -> None:
        if field not in self.fields:
            self.fields.append(field)


def _is_name(node: ast.AST, expected: str) -> bool:
    return isinstance(node, ast.Name) and node.id == expected
