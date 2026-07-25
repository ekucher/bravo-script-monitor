from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import verify_secret
from app.database import get_db_session
from app.models import Agent, AgentStatus

DbSession = Annotated[Session, Depends(get_db_session)]


def get_current_agent(
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_agent_id: Annotated[str | None, Header()] = None,
) -> Agent:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Agent token required")
    if not x_agent_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Agent-ID required")

    try:
        agent_id = UUID(x_agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent identifier") from exc

    agent = session.get(Agent, agent_id)
    token = authorization.removeprefix("Bearer ").strip()
    if agent is None or agent.token_hash is None or not verify_secret(token, agent.token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent credentials")
    if agent.status == AgentStatus.disabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent is disabled")
    return agent


CurrentAgent = Annotated[Agent, Depends(get_current_agent)]
