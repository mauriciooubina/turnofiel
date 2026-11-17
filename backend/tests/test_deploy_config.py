import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def test_docker_compose_config():
    compose_path = os.path.join(ROOT, "docker-compose.yml")
    with open(compose_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "5432:5432" not in content
    assert "8000:8000" not in content
    assert "443:443" in content
    assert "profiles:" in content
    assert "APP_DB_PASS" in content
    assert "container_name: turnofiel_backend" in content
    assert "image: turnofiel-backend:local" in content
    assert "pfi-postgres" not in content
    assert "pfi_backend" not in content
    assert "pfi_caddy" not in content
    assert "pfi-backend:local" not in content
    assert "version:" not in content


def test_caddyfile_config():
    caddy_path = os.path.join(ROOT, "caddy", "Caddyfile")
    with open(caddy_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "tls internal" in content
    assert "reverse_proxy backend:8000" in content
