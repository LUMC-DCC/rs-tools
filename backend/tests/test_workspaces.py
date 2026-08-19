from __future__ import annotations

import asyncio
import zipfile
from io import BytesIO

from conftest import TestContext

from rs_tools.config import Settings


async def test_create_empty_workspace(context: TestContext) -> None:
    response = await context.client.post("/api/workspaces/empty")

    assert response.status_code == 201
    body = response.json()
    assert body["data"] == {"project_slug": "project"}
    assert response.headers["location"] == f"http://test/w/{body['id']}"


async def test_create_populated_workspace(context: TestContext) -> None:
    rsm = {
        "project_slug": "transparent-pipelines",
        "project_name": "Transparent pipelines",
        "project_short_description": "A reproducible analysis toolkit.",
    }

    response = await context.client.post("/api/workspaces", json=rsm)

    assert response.status_code == 201
    assert response.json()["data"] == rsm


async def test_invalid_schema_is_rejected_with_useful_errors(context: TestContext) -> None:
    response = await context.client.post("/api/workspaces", json={"project_slug": 123})

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "The document does not conform to the RSM Schema."
    assert body["errors"][0]["path"] == "/project_slug"
    assert "string" in body["errors"][0]["message"]


async def test_retrieve_workspace(context: TestContext) -> None:
    created = (
        await context.client.post("/api/workspaces", json={"project_slug": "retrieve-me"})
    ).json()

    response = await context.client.get(f"/api/workspaces/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


async def test_update_workspace_replaces_complete_data(context: TestContext) -> None:
    created = (
        await context.client.post(
            "/api/workspaces", json={"project_slug": "example", "project_name": "Before"}
        )
    ).json()

    response = await context.client.put(
        f"/api/workspaces/{created['id']}",
        json={"project_slug": "example", "project_name": "After"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"project_slug": "example", "project_name": "After"}
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] > created["updated_at"]


async def test_expired_workspace_is_unavailable(context: TestContext) -> None:
    created = (await context.client.post("/api/workspaces/empty")).json()
    key = context.store.key_for(created["id"])
    await context.redis.expire(key, 1)
    await asyncio.sleep(1.05)

    response = await context.client.get(f"/api/workspaces/{created['id']}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found or expired."


async def test_retrieve_refreshes_workspace_ttl(context: TestContext) -> None:
    created = (await context.client.post("/api/workspaces/empty")).json()
    key = context.store.key_for(created["id"])
    await context.redis.expire(key, 5)

    response = await context.client.get(f"/api/workspaces/{created['id']}")

    assert response.status_code == 200
    assert await context.redis.ttl(key) > 50


async def test_location_header_can_use_public_base_url(context: TestContext) -> None:
    context.app.state.settings = Settings(
        redis_url="redis://unused/0",
        workspace_ttl_seconds=60,
        max_request_bytes=1_048_576,
        public_base_url="https://rs-tools.example.org/",
        frontend_dist=context.app.state.settings.frontend_dist,
        cors_origins=(),
    )

    response = await context.client.post("/api/workspaces", json={"project_slug": "example"})

    assert response.status_code == 201
    assert response.headers["location"].startswith("https://rs-tools.example.org/w/")


async def test_download_returns_only_current_smp_data(context: TestContext) -> None:
    rsm = {"project_slug": "download-me", "project_name": "Download me"}
    created = (await context.client.post("/api/workspaces", json=rsm)).json()

    response = await context.client.get(f"/api/workspaces/{created['id']}/download")

    assert response.status_code == 200
    assert response.json() == rsm
    assert response.headers["content-disposition"] == 'attachment; filename="rsm.json"'


async def test_generator_catalogue_exposes_schema_derived_input_fields(
    context: TestContext,
) -> None:
    response = await context.client.get("/api/generators")

    assert response.status_code == 200
    citation = next(generator for generator in response.json() if generator["id"] == "citation-cff")
    assert citation["category"] == "metadata"
    assert citation["label"] == "CITATION.cff"
    assert citation["description"]
    assert citation["fields"][0]["path"] == "/project_name"
    assert citation["fields"][0]["description"]
    citation_paths = [field["path"] for field in citation["fields"]]
    assert "/contributors/entries/0/name" in citation_paths
    assert "/contributors/entries/0/affiliations/0/name" in citation_paths
    assert citation_paths.index("/keywords") < citation_paths.index("/contributors")
    assert all(not path.endswith("/startswith") for path in citation_paths)
    codemeta = next(generator for generator in response.json() if generator["id"] == "codemeta")
    codemeta_paths = [field["path"] for field in codemeta["fields"]]
    assert "/access/type" in codemeta_paths
    assert "/access/details" in codemeta_paths
    assert "/funding/entries/0/funder_identifier" in codemeta_paths
    assert "/funding/entries/0/grant_url" in codemeta_paths
    assert "/topics/entries/0/term" in codemeta_paths
    assert "/topics/entries/0/uri" in codemeta_paths
    assert "/software_functions/entries/0/operations/0/term" in codemeta_paths
    assert "/software_functions/entries/0/topics/0/term" not in codemeta_paths
    assert "/software_functions/entries/0/inputs/0/data/term" in codemeta_paths
    assert "/software_functions/entries/0/outputs/0/data/term" in codemeta_paths
    assert all(
        singular not in codemeta_paths
        for singular in (
            "/software_functions/entries/0/operation",
            "/software_functions/entries/0/input",
            "/software_functions/entries/0/output",
        )
    )
    biotools = next(generator for generator in response.json() if generator["id"] == "biotools")
    biotools_paths = [field["path"] for field in biotools["fields"]]
    assert "/registries/entries/0/name" in biotools_paths
    assert "/topics/entries/0/uri" in biotools_paths
    assert "/software_functions/entries/0/operations/0/uri" in biotools_paths
    contributing = next(
        generator for generator in response.json() if generator["id"] == "contributing"
    )
    assert "/code_review_policy" in [field["path"] for field in contributing["fields"]]
    readme = next(generator for generator in response.json() if generator["id"] == "readme")
    assert readme["category"] == "documentation"
    assert readme["filename"] == "README.md"
    legal = next(
        generator for generator in response.json() if generator["id"] == "documentation-legal"
    )
    assert legal["category"] == "documentation"
    assert "/access/type" in [field["path"] for field in legal["fields"]]
    repository = next(generator for generator in response.json() if generator["id"] == "repository")
    assert repository["category"] == "repository"
    assert [template["id"] for template in repository["templates"]] == [
        "generic",
        "python",
        "r",
    ]
    assert len(repository["fields"]) > 40


async def test_github_status_is_safe_when_integration_is_unconfigured(
    context: TestContext,
) -> None:
    created = (await context.client.post("/api/workspaces/empty")).json()

    response = await context.client.get(f"/api/workspaces/{created['id']}/github")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "connected": False,
        "accounts": [],
    }


async def test_dummy_citation_generator_returns_an_artifact(context: TestContext) -> None:
    created = (
        await context.client.post(
            "/api/workspaces",
            json={
                "project_slug": "useful-research-software",
                "project_name": "Useful research software",
                "project_short_description": "A small test project.",
                "contributors": {
                    "entries": [
                        {
                            "name": "Ada Lovelace",
                            "given_names": "Ada",
                            "family_names": "Lovelace",
                            "roles": ["Original author"],
                        }
                    ]
                },
            },
        )
    ).json()

    response = await context.client.get(f"/api/workspaces/{created['id']}/generators/citation-cff")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="CITATION.cff"'
    assert 'title: "Useful research software"' in response.text
    assert 'given-names: "Ada"' in response.text


async def test_published_file_generators_are_available(context: TestContext) -> None:
    created = (await context.client.post("/api/workspaces/empty")).json()

    response = await context.client.get(f"/api/workspaces/{created['id']}/generators/license")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="LICENSE"'

    catalogue = (await context.client.get("/api/generators")).json()
    assert {
        "license",
        "citation-cff",
        "biotools",
        "codemeta",
        "zenodo",
        "changelog",
        "code-of-conduct",
        "contributing",
        "governance",
        "security",
        "support",
        "issue-templates",
        "pull-request-template",
        "readme",
        "documentation-overview",
        "documentation-user",
        "documentation-deployment",
        "documentation-developer",
        "documentation-reference",
        "documentation-legal",
    }.issubset({generator["id"] for generator in catalogue})

    biotools = await context.client.get(f"/api/workspaces/{created['id']}/generators/biotools")
    assert biotools.status_code == 200
    assert biotools.headers["content-disposition"] == ('attachment; filename="biotools.json"')
    assert isinstance(biotools.json(), list)

    generated = await context.client.get(
        f"/api/workspaces/{created['id']}/generators/code-of-conduct"
    )
    assert generated.status_code == 200
    assert generated.headers["content-disposition"] == ('attachment; filename="CODE_OF_CONDUCT.md"')

    issue_templates = await context.client.get(
        f"/api/workspaces/{created['id']}/generators/issue-templates"
    )
    assert issue_templates.status_code == 200
    assert issue_templates.headers["content-type"] == "application/zip"
    assert issue_templates.headers["content-disposition"] == (
        'attachment; filename="ISSUE_TEMPLATE.zip"'
    )
    with zipfile.ZipFile(BytesIO(issue_templates.content)) as archive:
        assert archive.namelist() == ["config.yml", "bug_report.yml", "feature_request.yml"]

    pull_request = await context.client.get(
        f"/api/workspaces/{created['id']}/generators/pull-request-template"
    )
    assert pull_request.status_code == 200
    assert pull_request.headers["content-disposition"] == (
        'attachment; filename="pull_request_template.md"'
    )


async def test_documentation_generators_return_separate_markdown_files(
    context: TestContext,
) -> None:
    created = (
        await context.client.post(
            "/api/workspaces",
            json={
                "project_slug": "documented-tool",
                "project_name": "Documented tool",
                "project_short_description": "A tool with reusable documentation.",
                "access": {
                    "type": "free-with-restrictions",
                    "details": "Free for academic use.",
                },
                "code_review_policy": "Every change needs one independent approval.",
            },
        )
    ).json()

    expected = {
        "readme": "README.md",
        "documentation-overview": "overview.md",
        "documentation-user": "usage.md",
        "documentation-deployment": "deployment.md",
        "documentation-developer": "developer.md",
        "documentation-reference": "reference.md",
        "documentation-legal": "legal.md",
    }
    for generator_id, filename in expected.items():
        response = await context.client.get(
            f"/api/workspaces/{created['id']}/generators/{generator_id}"
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'

    developer = await context.client.get(
        f"/api/workspaces/{created['id']}/generators/documentation-developer"
    )
    assert "Every change needs one independent approval." in developer.text
    legal = await context.client.get(
        f"/api/workspaces/{created['id']}/generators/documentation-legal"
    )
    assert "Free for academic use." in legal.text


async def test_large_request_is_rejected(context: TestContext) -> None:
    response = await context.client.post(
        "/api/workspaces",
        content=b"x" * 1_048_577,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body is too large."
