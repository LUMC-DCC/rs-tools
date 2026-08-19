from rs_tools.schema.service import SchemaService


def test_empty_document_conforms_to_schema() -> None:
    service = SchemaService()

    assert service.empty_document() == {"project_slug": "project"}


def test_schema_is_returned_as_an_isolated_copy() -> None:
    service = SchemaService()
    first = service.schema
    first["title"] = "changed"

    assert service.schema["title"] != "changed"


def test_present_objects_are_completed_without_adding_absent_top_level_fields() -> None:
    service = SchemaService()
    original = {
        "project_slug": "sample_project",
        "urls": {"repository": "https://github.com/example/sample_project"},
        "quality_tools": {"formatter": "ruff"},
    }

    completed = service.complete_present_objects(original)

    assert completed["urls"] == {
        "repository": "https://github.com/example/sample_project",
        "homepage": "",
        "documentation": "",
    }
    assert completed["quality_tools"] == {
        "formatter": "ruff",
        "linter": "",
        "type_checker": "",
    }
    assert "licensing" not in completed
    assert original["urls"] == {"repository": "https://github.com/example/sample_project"}


def test_completion_does_not_invent_invalid_empty_nested_objects() -> None:
    service = SchemaService()
    original = {
        "project_slug": "sample_project",
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
    }

    completed = service.complete_present_objects(original)

    function_input = completed["software_functions"]["entries"][0]["inputs"][0]
    assert "data" not in function_input
    assert function_input["format"][0]["term"] == "CSV"
    service.validate(completed)
