"""Load, validate, and derive defaults from the published RSM JSON Schema.

The packaged schema is the application's only contract. Everything a client
needs to render a form, order fields, or explain a validation failure is derived
from it here, so no hand-written Python or TypeScript copy of the schema exists
to fall out of step with it.
"""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError
from jsonschema.validators import validator_for

from rs_tools.models import ValidationIssue


class RSMValidationError(ValueError):
    """Raised when a document does not conform to the RSM schema.

    Attributes
    ----------
    issues : list of ValidationIssue
        Every failure found, sorted by document position so the first one is the
        first a reader would meet in the form.
    """

    def __init__(self, issues: list[ValidationIssue]) -> None:
        super().__init__("The document does not conform to the RSM Schema.")
        self.issues = issues


class SchemaService:
    """Owns the application contract without duplicating it in Python models."""

    def __init__(self, schema_path: Path | None = None) -> None:
        """Load and compile a JSON Schema.

        Parameters
        ----------
        schema_path : pathlib.Path, optional
            Schema file to load. The schema packaged with the installed
            ``rsm-schema`` dependency is used when omitted, so validation never
            depends on fetching a remote URL at startup.
        """
        if schema_path is None:
            schema_text = (
                files("rsm_schema").joinpath("schema/rsm.schema.json").read_text(encoding="utf-8")
            )
        else:
            schema_text = schema_path.read_text(encoding="utf-8")
        self._schema: dict[str, Any] = json.loads(schema_text)
        validator_class = validator_for(self._schema)
        validator_class.check_schema(self._schema)
        self._validator = validator_class(self._schema, format_checker=FormatChecker())

    @property
    def schema(self) -> dict[str, Any]:
        """Return an isolated copy so callers cannot mutate the contract.

        Returns
        -------
        dict
            A deep copy of the loaded JSON Schema.
        """
        return copy.deepcopy(self._schema)

    def validate(self, document: object) -> dict[str, Any]:
        """Check a document against the schema and return a private copy of it.

        Parameters
        ----------
        document : object
            Candidate RSM document.

        Returns
        -------
        dict
            A deep copy of the document, so later mutation by a caller cannot
            change what was validated.

        Raises
        ------
        RSMValidationError
            If the document does not conform, carrying every failure found.
        """
        errors = sorted(self._validator.iter_errors(document), key=_error_sort_key)
        if errors:
            raise RSMValidationError([_to_issue(error) for error in errors])
        return copy.deepcopy(document)  # type: ignore[return-value]

    def empty_document(self) -> dict[str, Any]:
        """Build the smallest valid document using required fields and schema defaults.

        Returns
        -------
        dict
            A document containing only what the schema requires.
        """
        document = _required_defaults(self._schema, self._schema)
        return self.validate(document)

    def complete_present_objects(self, document: dict[str, Any]) -> dict[str, Any]:
        """Fill omitted properties inside objects already present in a document.

        The RSM contract permits partial optional objects. Some strict downstream
        serializers instead expect every property of a supplied object to exist.
        Missing top-level fields remain absent so those consumers can still apply
        their own defaults; only objects explicitly present in ``document`` are
        completed with schema defaults or neutral values.

        Parameters
        ----------
        document : dict
            A previously validated RSM document.

        Returns
        -------
        dict
            A completed deep copy. The original document is never mutated.
        """
        return _complete_present_objects(
            document,
            self._schema,
            self._schema,
            self._validator,
            complete=False,
        )

    def describe_field(self, path: str) -> dict[str, str]:
        """Return display metadata for a JSON Pointer from the schema contract.

        Generators only need to declare the fields they consume. Labels and help
        text are resolved here so the API and the form remain aligned with the
        versioned schema dependency.

        Parameters
        ----------
        path : str
            JSON Pointer into the schema.

        Returns
        -------
        dict of str to str
            The pointer, a display label, and a description. Unknown pointers
            fall back to a humanized form of their last segment rather than
            failing, so an out-of-date declaration degrades quietly.
        """
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]
        node: dict[str, Any] = self._schema
        for part in parts:
            node = _dereference(node, self._schema)
            properties = node.get("properties", {})
            if part in properties:
                node = properties[part]
                continue
            if node.get("type") == "array" and part.isdigit():
                node = node.get("items", {})
                continue
            break

        node = _dereference(node, self._schema)
        fallback_label = parts[-1].replace("_", " ").capitalize() if parts else "Metadata"
        return {
            "path": path,
            "label": str(node.get("title") or fallback_label),
            "description": str(node.get("description") or ""),
        }

    def top_level_paths(self) -> tuple[str, ...]:
        """Return JSON Pointers for every top-level property in schema order.

        Returns
        -------
        tuple of str
            One pointer per top-level property.
        """
        return tuple(f"/{name}" for name in self._schema.get("properties", {}))

    def order_paths(self, paths: tuple[str, ...]) -> tuple[str, ...]:
        """Order JSON Pointers as their fields appear in the RSM form.

        Parameters
        ----------
        paths : tuple of str
            Pointers to order. Duplicates and pointers that name no schema field
            are dropped.

        Returns
        -------
        tuple of str
            The valid pointers, in form order.
        """
        valid_paths = (path for path in dict.fromkeys(paths) if self._is_field_path(path))
        return tuple(sorted(valid_paths, key=self._path_sort_key))

    def required_descendant_paths(self, paths: tuple[str, ...]) -> tuple[str, ...]:
        """Return required nested leaf fields for structured generator inputs.

        A generator that declares ``/authors`` really needs the required fields
        inside each author entry. Expanding them here lets the interface show
        what is actually needed without the generator restating the schema.

        Parameters
        ----------
        paths : tuple of str
            Top-level pointers to expand.

        Returns
        -------
        tuple of str
            Pointers to the required leaf fields below those paths.
        """
        discovered: list[str] = []
        for path in paths:
            if path.count("/") != 1:
                continue
            node = self._field_node(path)
            if node is not None:
                _required_leaf_paths(node, self._schema, path, discovered)
        return tuple(dict.fromkeys(discovered))

    def _is_field_path(self, path: str) -> bool:
        return self._field_node(path) is not None

    def _field_node(self, path: str) -> dict[str, Any] | None:
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]
        node: dict[str, Any] = self._schema
        for part in parts:
            node = _dereference(node, self._schema)
            if node.get("type") == "array" and part.isdigit():
                node = node.get("items", {})
                continue
            properties = node.get("properties", {})
            if part not in properties:
                return None
            node = properties[part]
        return node if parts else None

    def _path_sort_key(self, path: str) -> tuple[int, ...]:
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]
        node: dict[str, Any] = self._schema
        result: list[int] = []
        for part in parts:
            node = _dereference(node, self._schema)
            if node.get("type") == "array" and part.isdigit():
                result.append(int(part))
                node = node.get("items", {})
                continue
            properties = node.get("properties", {})
            names = tuple(properties)
            if part not in properties:
                result.append(len(names) + 1_000)
                break
            result.append(names.index(part))
            node = properties[part]
        return tuple(result)


def _required_defaults(node: dict[str, Any], root: dict[str, Any]) -> Any:
    if "$ref" in node:
        node = _resolve_local_ref(root, node["$ref"])
    if "default" in node:
        return copy.deepcopy(node["default"])
    if "const" in node:
        return copy.deepcopy(node["const"])
    if node.get("enum"):
        return copy.deepcopy(node["enum"][0])

    node_type = node.get("type")
    if node_type == "object" or "properties" in node:
        properties = node.get("properties", {})
        return {
            key: _required_defaults(properties[key], root)
            for key in node.get("required", [])
            if key in properties
        }
    if node_type == "array":
        return []
    if node_type == "string":
        return "research-software" if int(node.get("minLength", 0)) > 0 else ""
    if node_type in {"number", "integer"}:
        return 0
    if node_type == "boolean":
        return False
    return None


def _complete_present_objects(
    value: Any,
    node: dict[str, Any],
    root: dict[str, Any],
    validator: Any,
    *,
    complete: bool,
) -> Any:
    node = _dereference(node, root)
    properties = node.get("properties", {})
    if isinstance(value, dict) and isinstance(properties, dict):
        result = copy.deepcopy(value)
        for name, property_schema in properties.items():
            if not isinstance(property_schema, dict):
                continue
            if name in result:
                result[name] = _complete_present_objects(
                    result[name], property_schema, root, validator, complete=True
                )
            elif complete:
                default = _neutral_default(property_schema, root, validator)
                if default is not _NO_NEUTRAL_DEFAULT:
                    result[name] = default
        return result
    if isinstance(value, list):
        item_schema = node.get("items", {})
        if isinstance(item_schema, dict):
            return [
                _complete_present_objects(item, item_schema, root, validator, complete=True)
                for item in value
            ]
    return copy.deepcopy(value)


_NO_NEUTRAL_DEFAULT = object()


def _neutral_default(node: dict[str, Any], root: dict[str, Any], validator: Any) -> Any:
    """Return a template-safe neutral value, or a sentinel when none is valid.

    Empty strings are retained as Copier intermediary values because repository
    finalization removes them before validating the public RSM payload. Empty
    containers cannot be removed without changing list structure, so they are
    added only when the corresponding schema accepts them.
    """
    node = _dereference(node, root)
    if "const" in node:
        return copy.deepcopy(node["const"])

    node_type = node.get("type")
    if node_type == "object" or "properties" in node:
        default = copy.deepcopy(node.get("default", {}))
        if not isinstance(default, dict):
            default = {}
        candidate = _complete_present_objects(default, node, root, validator, complete=True)
        if validator.evolve(schema=node).is_valid(candidate):
            return candidate
        return _NO_NEUTRAL_DEFAULT
    if "default" in node:
        return copy.deepcopy(node["default"])
    if node_type == "array":
        candidate: list[Any] = []
        if validator.evolve(schema=node).is_valid(candidate):
            return candidate
        return _NO_NEUTRAL_DEFAULT
    if node_type == "boolean":
        return False
    if node_type in {"number", "integer"}:
        return 0
    if node_type == "string":
        return ""
    return None


def _resolve_local_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"Cannot derive a default for external schema reference {reference!r}")
    value: Any = root
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def _dereference(
    node: dict[str, Any],
    root: dict[str, Any],
    seen_refs: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Resolve local references and combine ``allOf`` inheritance."""
    local = node
    reference = node.get("$ref")
    if isinstance(reference, str):
        if reference in seen_refs:
            return node
        resolved = _dereference(
            _resolve_local_ref(root, reference),
            root,
            seen_refs | {reference},
        )
        local = _merge_schema(
            resolved, {key: value for key, value in node.items() if key != "$ref"}
        )

    inherited: dict[str, Any] = {}
    for branch in local.get("allOf", []):
        if isinstance(branch, dict):
            inherited = _merge_schema(inherited, _dereference(branch, root, seen_refs))
    if not inherited:
        return local
    return _merge_schema(inherited, {key: value for key, value in local.items() if key != "allOf"})


def _merge_schema(base: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    """Merge the structural keywords needed while traversing schema fields."""
    merged = {**base, **extension}
    base_properties = base.get("properties")
    extension_properties = extension.get("properties")
    if isinstance(base_properties, dict) or isinstance(extension_properties, dict):
        properties: dict[str, Any] = {}
        for source in (base_properties, extension_properties):
            if not isinstance(source, dict):
                continue
            for name, value in source.items():
                if isinstance(properties.get(name), dict) and isinstance(value, dict):
                    properties[name] = _merge_schema(properties[name], value)
                else:
                    properties[name] = value
        merged["properties"] = properties
    required = [
        name
        for source in (base.get("required"), extension.get("required"))
        if isinstance(source, list)
        for name in source
    ]
    if required:
        merged["required"] = list(dict.fromkeys(required))
    if isinstance(base.get("items"), dict) and isinstance(extension.get("items"), dict):
        merged["items"] = _merge_schema(base["items"], extension["items"])
    return merged


def _error_sort_key(error: ValidationError) -> tuple[str, str]:
    return ("/".join(str(part) for part in error.absolute_path), error.message)


def _required_leaf_paths(
    node: dict[str, Any],
    root: dict[str, Any],
    path: str,
    discovered: list[str],
) -> None:
    node = _dereference(node, root)
    if node.get("type") == "array":
        item = _dereference(node.get("items", {}), root)
        if item.get("type") == "object" or "properties" in item:
            _required_leaf_paths(item, root, f"{path}/0", discovered)
        return
    properties = node.get("properties", {})
    if node.get("type") == "object" or properties:
        for name in node.get("required", []):
            if name in properties:
                _required_leaf_paths(properties[name], root, f"{path}/{name}", discovered)
        return
    discovered.append(path)


def _to_issue(error: ValidationError) -> ValidationIssue:
    path = "/" + "/".join(str(part) for part in error.absolute_path)
    return ValidationIssue(
        path=path if path != "/" else "$",
        message=error.message,
        validator=str(error.validator) if error.validator is not None else None,
    )
