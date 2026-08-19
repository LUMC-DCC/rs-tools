"""The contract clients build themselves from: the schema and the generators.

Both documents are byte-identical for every caller, so they are built and
encoded once when the application starts and returned verbatim. Producing them
per request meant an unauthenticated client could spend the service's CPU
simply by asking repeatedly: resolving the catalogue walks the schema for every
generator, and both bodies are large to serialize.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from rs_tools.api.dependencies import enforce_default_rate_limit

router = APIRouter(tags=["catalogue"], dependencies=[Depends(enforce_default_rate_limit)])

JSON_MEDIA_TYPE = "application/json"


def get_schema_document(request: Request) -> bytes:
    """Return the encoded schema document built at startup."""
    document: bytes = request.app.state.schema_document
    return document


def get_generator_catalogue(request: Request) -> bytes:
    """Return the encoded generator catalogue built at startup."""
    catalogue: bytes = request.app.state.generator_catalogue
    return catalogue


SchemaDocument = Annotated[bytes, Depends(get_schema_document)]
GeneratorCatalogue = Annotated[bytes, Depends(get_generator_catalogue)]


@router.get("/schema", response_model=None)
async def get_schema(schema: SchemaDocument) -> Response:
    """Return the exact JSON Schema used for server-side validation.

    The frontend form is generated from this document, so the form and the
    validator can never disagree about what a valid workspace is.

    Parameters
    ----------
    schema : bytes
        The encoded schema document, built at startup.

    Returns
    -------
    fastapi.Response
        The published RSM JSON Schema.
    """
    return Response(content=schema, media_type=JSON_MEDIA_TYPE)


@router.get("/generators", response_model=None)
async def list_generators(catalogue: GeneratorCatalogue) -> Response:
    """Expose the generator catalogue and its schema-derived input fields.

    Parameters
    ----------
    catalogue : bytes
        The encoded catalogue, built at startup.

    Returns
    -------
    fastapi.Response
        One description per registered generator, in catalogue order.
    """
    return Response(content=catalogue, media_type=JSON_MEDIA_TYPE)
