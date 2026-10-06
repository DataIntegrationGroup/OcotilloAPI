"""
Which database the CLI is connected to, as the server reports it.

An operator chooses the database with ``POSTGRES_DB`` in ``.env``, but that
name alone doesn't prove where a run goes. The Cloud SQL proxy and a local
Docker database can both listen on port 5432, so ``localhost`` can reach either
one. Asking the server settles it: ``current_database()`` is the database the
connection actually landed in. A local Docker database also reports its own
address (a 172.x container address); a Cloud SQL server reached through the
proxy reports none.

The ingests write through the same engine, so a report that prints this after
a run names the database its results went to.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseInfo:
    name: str
    user: str
    # Where the CLI's settings sent the connection.
    connected_to: str
    # The address the server reports for itself, if any.
    server: str | None


def connected_database() -> DatabaseInfo:
    """Ask the server which database, user and address this connection has.

    Read-only. Raises whatever the driver raises when it can't connect, so the
    caller decides whether that stops the command.
    """
    # Imported here, not at module level: the engine reads its connection
    # settings at import time, and the CLI loads .env only after its own
    # imports (see cli/cli.py).
    from sqlalchemy import text

    from db.engine import engine, session_ctx

    with session_ctx() as session:
        name, user, address, port = session.execute(
            text(
                "select current_database(), current_user, "
                "inet_server_addr(), inet_server_port()"
            )
        ).one()
    # inet_server_addr() is null over a Unix socket, and Cloud SQL returns
    # null through the proxy too.
    server = f"{_host(address)}:{port}" if address else None
    url = engine.url
    # The Cloud SQL connector builds its connections itself; its URL has no host.
    connected_to = (
        f"{_host(url.host)}:{url.port}" if url.host else "Cloud SQL connector"
    )
    return DatabaseInfo(name=name, user=user, connected_to=connected_to, server=server)


def _host(address) -> str:
    """Bracket an IPv6 address, so the port after it reads as a port."""
    text = str(address)
    return f"[{text}]" if ":" in text else text


def describe_failure(exc: BaseException) -> str:
    """One line on why the connection failed, for an operator to act on.

    Driver errors run to several lines, ending in a link to SQLAlchemy's error
    docs. The first line is the part that says what went wrong.
    """
    lines = str(exc).strip().splitlines()
    first = lines[0] if lines else ""
    return f"{type(exc).__name__}: {first}" if first else type(exc).__name__
