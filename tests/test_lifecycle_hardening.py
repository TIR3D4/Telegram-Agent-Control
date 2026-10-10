import importlib.util
import io
import json
import tarfile
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import timedelta
import pytest
from sqlalchemy import select
from tac.db import Session, Audit, RateBucket, now
from tac.maintenance import prune

spec = importlib.util.spec_from_file_location(
    "backup_manifest", Path(__file__).parents[1] / "scripts/backup_manifest.py"
)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def backup(tmp_path, member="a" * 32, link=False):
    (tmp_path / "database.dump").write_bytes(b"database fixture")
    with tarfile.open(tmp_path / "media.tar.gz", "w:gz") as tar:
        info = tarfile.TarInfo(member)
        if link:
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
        else:
            info.size = 3
            tar.addfile(info, io.BytesIO(b"abc"))
    meta = {
        "format": 1,
        "commit": "a" * 40,
        "files": {f: manifest.checksum(tmp_path / f) for f in manifest.FILES},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(meta))
    return tmp_path


def test_manifest_detects_corruption(tmp_path):
    root = backup(tmp_path)
    assert manifest.verify(root)["commit"] == "a" * 40
    (root / "database.dump").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        manifest.verify(root)


@pytest.mark.parametrize("current,allowed", [("a" * 40, True), ("b" * 40, False)])
def test_restore_requires_current_backup_revision(tmp_path, monkeypatch, current, allowed):
    root = backup(tmp_path)
    monkeypatch.setattr(manifest.subprocess, "check_output", lambda *a, **kw: current + "\n")
    # Integrity-only inspection remains available for older snapshots.
    assert manifest.verify(root)["commit"] == "a" * 40
    if allowed:
        assert manifest.verify(root, require_current_commit=True)["commit"] == current
    else:
        with pytest.raises(ValueError, match="compatibility"):
            manifest.verify(root, require_current_commit=True)


def test_restore_command_rejects_revision_before_stopping_services(tmp_path):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("Bash is required to exercise the operator shell entrypoint")
    root = backup(tmp_path)
    # Only the version probe is allowed. Never invoke a real Docker daemon.
    script = """
export TAC_TEST_PYTHON="$2"
python3() { "$TAC_TEST_PYTHON" "$@"; }
export -f python3
docker() {
  if [[ "$*" == "compose version" ]]; then return 0; fi
  printf '%s\\n' UNEXPECTED_DOCKER_MUTATION
  return 55
}
export -f docker
bash scripts/tacctl restore "$1"
"""
    result = subprocess.run(
        [bash, "-c", script, "restore-test", str(root), Path(sys.executable).as_posix()],
        cwd=Path(__file__).resolve().parents[1],
        input="RESTORE\n",
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0
    assert "Cross-revision restore is blocked" in result.stderr
    assert "UNEXPECTED_DOCKER_MUTATION" not in result.stdout


@pytest.mark.parametrize(
    "member,link", [("../escape", False), ("/absolute", False), ("nested/file", False), ("b" * 32, True)]
)
def test_manifest_rejects_unsafe_archive_even_with_matching_checksum(tmp_path, member, link):
    with pytest.raises(ValueError, match="Unsafe"):
        manifest.verify(backup(tmp_path, member, link))


def test_body_size_checked_before_json_parsing(client, agent):
    r = client.post(
        "/v1/validate",
        headers={**agent, "Content-Type": "application/json"},
        content=b"x" * (2 * 1024 * 1024 + 1),
    )
    assert r.status_code == 413


def test_retention_keeps_approval_evidence():
    stamp = now() - timedelta(days=100)
    with Session.begin() as db:
        db.add(Audit(actor="test", action="http.request", at=stamp, details={}))
        db.add(Audit(actor="owner", action="operation.approved", at=stamp, details={}))
        db.add(RateBucket(key="old", count=1, expires_at=stamp))
    prune()
    with Session() as db:
        assert [a.action for a in db.scalars(select(Audit))] == ["operation.approved"]
        assert not db.scalars(select(RateBucket)).all()


def test_telemetry_never_records_exception_text(monkeypatch):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from tac import observability

    monkeypatch.setenv("OTEL_SDK_DISABLED", "false")
    from opentelemetry.sdk.trace.sampling import ALWAYS_ON

    provider = TracerProvider(sampler=ALWAYS_ON)
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(observability.trace, "get_tracer", provider.get_tracer)
    with pytest.raises(ValueError):
        with observability.span("fixture", {"tac.operation_id": "safe"}):
            raise ValueError("SECRET-SENTINEL")
    spans = exporter.get_finished_spans()
    assert len(spans) == 1 and not spans[0].events
    assert "SECRET-SENTINEL" not in str(spans[0].attributes)
    provider.shutdown()
