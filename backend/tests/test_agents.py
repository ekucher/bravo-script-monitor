from uuid import uuid4

from app.agents.router import router
from app.agents.schemas import AgentJobResultRequest, AgentRegistrationRequest
from app.models import JobStatus


def test_agent_router_exposes_lifecycle_endpoints() -> None:
    paths = {route.path for route in router.routes}

    assert "/agents/register" in paths
    assert "/agents/self/heartbeat" in paths
    assert "/agents/self/inventory" in paths
    assert "/agents/self/jobs/claim" in paths
    assert "/agents/self/jobs/{job_id}/result" in paths


def test_registration_schema_defaults() -> None:
    payload = AgentRegistrationRequest(
        installation_id=uuid4(),
        hostname="bravo-app-01",
    )

    assert payload.agent_name == "default"
    assert payload.capabilities == {}
    assert payload.inventory == {}


def test_job_result_accepts_terminal_status() -> None:
    payload = AgentJobResultRequest(status=JobStatus.succeeded, exit_code=0)

    assert payload.status is JobStatus.succeeded
    assert payload.exit_code == 0
