import logging

from fastapi.testclient import TestClient

from core.app import create_base_app


def test_request_timing_logs_cold_then_warm(caplog):
    app = create_base_app()

    @app.get("/ping")
    async def ping():
        return {"status": "ok"}

    with caplog.at_level(logging.INFO, logger="core.app"):
        with TestClient(app) as client:
            assert client.get("/ping").status_code == 200
            assert client.get("/ping").status_code == 200

    startup_logs = [
        record for record in caplog.records if record.msg == "instance startup complete"
    ]
    request_logs = [
        record for record in caplog.records if record.msg == "request timing"
    ]

    assert len(startup_logs) == 1
    assert len(request_logs) == 2

    assert startup_logs[0].event == "instance_startup_complete"
    assert startup_logs[0].startup_ms >= 0

    assert request_logs[0].request_kind == "cold"
    assert request_logs[0].path == "/ping"
    assert request_logs[0].status_code == 200
    assert request_logs[0].request_duration_ms >= 0
    assert request_logs[0].startup_ms >= 0

    assert request_logs[1].request_kind == "warm"
    assert request_logs[1].path == "/ping"
    assert request_logs[1].status_code == 200
    assert request_logs[1].request_duration_ms >= 0
    assert request_logs[1].uptime_before_request_ms >= 0
