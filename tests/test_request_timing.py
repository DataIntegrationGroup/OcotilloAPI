import logging

from fastapi.testclient import TestClient

from core.app import create_base_app


def test_request_lifecycle_logs_start_and_completion(caplog):
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
    request_started_logs = [
        record for record in caplog.records if record.msg == "request started"
    ]
    request_completed_logs = [
        record for record in caplog.records if record.msg == "request completed"
    ]
    assert len(startup_logs) == 1
    assert len(request_started_logs) == 2
    assert len(request_completed_logs) == 2

    assert startup_logs[0].event == "instance_startup_complete"
    assert startup_logs[0].startup_ms >= 0
    assert request_started_logs[0].event == "request_started"
    assert request_started_logs[0].request_id
    assert request_started_logs[0].path == "/ping"
    assert request_completed_logs[0].event == "request_completed"
    assert request_completed_logs[0].request_id == request_started_logs[0].request_id
    assert request_completed_logs[0].status_code == 200
    assert request_completed_logs[1].request_id == request_started_logs[1].request_id
    assert request_completed_logs[1].status_code == 200
