from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.scripts.router import router
from app.scripts.schemas import ScriptCreate, ScriptVersionCreate, validate_semver


def test_script_router_exposes_repository_endpoints() -> None:
    paths = {route.path for route in router.routes}

    assert "/scripts" in paths
    assert "/scripts/{script_id}" in paths
    assert "/scripts/{script_id}/versions" in paths
    assert "/scripts/{script_id}/versions/{version}" in paths
    assert "/scripts/{script_id}/versions/{version}/publish" in paths


def test_script_create_schema() -> None:
    payload = ScriptCreate(
        organization_id=uuid4(),
        name="Archive BRAVO database",
        description="Creates a verified BRAVO database archive.",
    )

    assert payload.name == "Archive BRAVO database"


@pytest.mark.parametrize("version", ["0.1.0", "1.0.0", "2.4.1-alpha.1", "3.0.0+build.7"])
def test_semver_accepts_valid_versions(version: str) -> None:
    assert validate_semver(version) == version


@pytest.mark.parametrize("version", ["1", "1.0", "v1.0.0", "01.0.0", "1.0.0-"])
def test_semver_rejects_invalid_versions(version: str) -> None:
    with pytest.raises(ValueError):
        validate_semver(version)


def test_script_version_defaults_and_language() -> None:
    payload = ScriptVersionCreate(
        version="1.2.0",
        language="powershell",
        content="Write-Output 'ok'",
    )

    assert payload.parameter_schema == {}
    assert payload.language == "powershell"


def test_script_version_rejects_unsupported_language() -> None:
    with pytest.raises(ValidationError):
        ScriptVersionCreate(
            version="1.0.0",
            language="ruby",  # type: ignore[arg-type]
            content="puts 'ok'",
        )
