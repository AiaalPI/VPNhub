import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "preflight.sh", repo / "scripts" / "preflight.sh")
    (repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    return repo


def _run_preflight(repo: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    return subprocess.run(
        ["bash", "scripts/preflight.sh"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


def test_preflight_allows_placeholders_and_empty_secret_examples(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "bot").mkdir()
    (repo / "bot" / ".env.example").write_text(
        "\n".join(
            [
                "TG_TOKEN=CHANGE_ME",
                "YOOMONEY_TOKEN=",
                "POSTGRES_PASSWORD=CHANGE_ME",
                "PGADMIN_DEFAULT_PASSWORD=CHANGE_ME",
                "GRAFANA_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-changeme}",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    result = _run_preflight(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_preflight_rejects_real_telegram_token(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "leak.md").write_text(
        "TG_TOKEN=" + "1234567890:" + "abcdefghijklmnopqrstuvwxyzABCDE\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    result = _run_preflight(repo)

    assert result.returncode == 2
    assert "potential secrets found" in result.stdout


def test_preflight_rejects_real_password_assignment(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "leak.md").write_text(
        "POSTGRES_PASSWORD=" + "Bvpn" + "Strong2026\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    result = _run_preflight(repo)

    assert result.returncode == 2
    assert "potential secrets found" in result.stdout


def test_preflight_ignores_binary_assets(tmp_path):
    repo = _make_git_repo(tmp_path)
    (repo / "image.jpg").write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x00" +
        b"1234567890:abcdefghijklmnopqrstuvwxyzABCDE" +
        b"\x00\xff\xd9"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)

    result = _run_preflight(repo)

    assert result.returncode == 0, result.stdout + result.stderr
