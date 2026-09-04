from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_compose_has_api_dashboard_healthchecks_and_persistence():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "  api:" in compose
    assert "  dashboard:" in compose
    assert compose.count("healthcheck:") >= 2
    assert "./runtime:/data" in compose
    assert "MERCHANTOS_API_BASE_URL: http://api:8000/api" in compose


def test_docker_image_is_python_311_and_does_not_bake_secrets():
    dockerfile = (ROOT / "Dockerfile").read_text()
    dockerignore = (ROOT / ".dockerignore").read_text()
    assert "FROM python:3.11-slim" in dockerfile
    assert ".env" in dockerignore
    assert "merchantos.db" in dockerignore
