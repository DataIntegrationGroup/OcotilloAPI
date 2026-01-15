"""Health check endpoints for deployment monitoring and container orchestration."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from core.dependencies import session_dependency

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
async def liveness_check() -> dict[str, str]:
    """
    Basic liveness probe - checks if the application is running.

    This endpoint should always return 200 if the app is alive.
    No dependencies checked - just confirms the web server is responding.

    Use this for Kubernetes/Docker liveness probes.
    """
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
async def readiness_check(session: session_dependency) -> dict[str, Any]:
    """
    Readiness probe - checks if the application is ready to serve traffic.

    Verifies:
    - Application is running
    - Database connection is available

    Returns 200 if ready, 503 if not ready.
    Use this for Kubernetes/Docker readiness probes and load balancer health checks.
    """
    try:
        # Test database connectivity with a simple query
        result = await session.execute(text("SELECT 1"))
        result.scalar()

        return {
            "status": "ready",
            "database": "connected",
            "checks": {"db_connection": True},
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "database": "disconnected",
                "error": str(e),
                "checks": {"db_connection": False},
            },
        )


@router.get("/status", summary="Detailed status information")
async def status_check(session: session_dependency) -> dict[str, Any]:
    """
    Detailed status endpoint - provides comprehensive health information.

    Returns:
    - Application status
    - Database connectivity and pool information
    - Timestamp
    - Additional service status

    Use this for monitoring dashboards and detailed health reports.
    """
    timestamp = datetime.utcnow().isoformat()

    # Check database connectivity
    db_status = "disconnected"
    db_connected = False
    pool_info = {}

    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        db_status = "connected"
        db_connected = True

        # Get connection pool information
        pool = session.get_bind().pool
        pool_info = {
            "size": pool.size(),
            "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
            "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else None,
            "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
        }
        # Remove None values
        pool_info = {k: v for k, v in pool_info.items() if v is not None}

    except Exception as e:
        db_status = f"error: {str(e)}"

    response = {
        "status": "healthy" if db_connected else "degraded",
        "timestamp": timestamp,
        "database": {
            "status": db_status,
            "connected": db_connected,
        },
        "services": {"admin": "available", "cors": "enabled"},
    }

    # Add pool info if available
    if pool_info:
        response["database"]["pool_info"] = pool_info

    # Return 503 if database is not connected
    if not db_connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=response
        )

    return response
