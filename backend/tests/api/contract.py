"""Check real responses against the committed OpenAPI contract (docs/api/openapi-v1.yaml).

The views build their responses by hand; the schema declares them separately.
``assert_matches_contract`` validates an actual response against its
operation's documented schema, with every object closed to undocumented
keys, so the two cannot drift apart unnoticed.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path
from typing import Any

import jsonschema  # type: ignore[import-untyped]  # stubs are not worth a new dependency
import yaml
from django.urls import resolve

SCHEMA_FILE = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi-v1.yaml"


@functools.cache
def contract() -> dict[str, Any]:
    return yaml.safe_load(SCHEMA_FILE.read_text(encoding="utf-8"))


def path_template(path: str) -> str:
    """``/api/v1/workspaces/<id>/`` → ``/api/v1/workspaces/{workspace_id}/``."""
    route = resolve(path.split("?")[0]).route
    route = route.replace("^", "").replace("(?P<version>v1)", "v1")
    return "/" + re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", route)


def response_schema(method: str, path: str, status: int) -> dict[str, Any] | None:
    """The JSON Schema documented for this response, or ``None`` for an empty body."""
    operation = contract()["paths"][path_template(path)][method.lower()]
    responses = operation["responses"]
    documented = responses.get(str(status)) or responses.get(f"{str(status)[0]}XX")
    assert documented is not None, f"{method} {path} does not document status {status}"
    content = documented.get("content")
    if not content:
        return None
    return _strict(content["application/json"]["schema"])


def assert_matches_contract(response: Any, method: str, path: str) -> None:
    schema = response_schema(method, path, response.status_code)
    if schema is None:
        assert not response.content, f"{method} {path} documents no body but returned one"
        return
    try:
        jsonschema.validate(response.json(), schema)
    except jsonschema.ValidationError as error:
        location = "/".join(str(part) for part in error.absolute_path)
        raise AssertionError(
            f"{method} {path} ({response.status_code}) breaks the contract at "
            f"'{location}': {error.message}"
        ) from None


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAPI 3.0 schema → JSON Schema: refs inlined, nullable resolved, objects closed."""
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return _strict(contract()["components"]["schemas"][name])
    converted: dict[str, Any] = {}
    for key, value in schema.items():
        if key in ("properties",):
            converted[key] = {name: _strict(item) for name, item in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            converted[key] = _strict(value)
        elif key in ("allOf", "oneOf", "anyOf"):
            converted[key] = [_strict(item) for item in value]
        elif key not in ("nullable", "description", "example", "readOnly", "writeOnly", "format"):
            converted[key] = value
    if schema.get("type") == "object" and "properties" in schema:
        converted.setdefault("additionalProperties", False)
    if schema.get("nullable"):
        converted = {"anyOf": [converted, {"type": "null"}]}
    return converted
