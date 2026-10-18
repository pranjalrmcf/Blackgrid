"""Full-file ingestion must not inherit bounded-window selection or leak raw IDs."""
import hashlib
import json

import pytest

from blackgrid.data.collegemsg import DataIntegrityError
from blackgrid.contracts import DatasetSource
from blackgrid.data.ingestion import ingest_full, write_ingestion


def source(tmp_path, rows):
    path = tmp_path / "events.txt"
    path.write_bytes(rows.encode())
    return DatasetSource(dataset_id="fixture", path="events.txt",
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         source_url="https://example.org/fixture", citations=("test fixture",),
                         rights_status="accepted_local_noncommercial", rights_decision="test")


def test_full_file_duplicates_direction_loops_empty_weeks_and_privacy(tmp_path):
    spec = source(tmp_path, "987654321 987654322 0\n987654321 987654322 0\n"
                  "987654322 987654321 1\n987654323 987654323 1209600\n")
    result = ingest_full(tmp_path, spec)
    assert result["validation"]["valid_events"] == 4
    assert result["validation"]["exact_duplicate_rows"] == 1
    assert result["projection"]["nodes"] == 3
    assert result["projection"]["edges"] == 1
    assert result["projection"]["isolated_nodes"] == 1
    assert result["projection"]["components"] == 2
    assert [w["events"] for w in result["time"]["weekly_bins"]] == [3, 0, 1]
    assert result["execution"]["llm_calls"] == 0
    assert "987654321" not in json.dumps(result)
    output = write_ingestion(result, tmp_path / "report")
    assert hashlib.sha256((output / "ingestion.json").read_bytes()).hexdigest() == (
        output / "ingestion.sha256").read_text().strip()
    with pytest.raises(FileExistsError):
        write_ingestion(result, output)


def test_changed_input_is_rejected(tmp_path):
    spec = source(tmp_path, "1 2 0\n")
    (tmp_path / "events.txt").write_text("1 3 0\n")
    with pytest.raises(DataIntegrityError, match="checksum mismatch"):
        ingest_full(tmp_path, spec)


@pytest.mark.parametrize("rows", ["1 2 broken\n", "# no events\n"])
def test_invalid_or_empty_file_is_refused(tmp_path, rows):
    with pytest.raises(DataIntegrityError):
        ingest_full(tmp_path, source(tmp_path, rows))


def test_rights_and_path_escape_are_refused(tmp_path):
    spec = source(tmp_path, "1 2 0\n")
    with pytest.raises(DataIntegrityError, match="rights"):
        ingest_full(tmp_path, spec.model_copy(update={"rights_status": type(spec.rights_status)("blocked")}))
    with pytest.raises(DataIntegrityError, match="escapes"):
        ingest_full(tmp_path, spec.model_copy(update={"path": "../events.txt"}))


def test_ingest_cli_writes_full_report_and_preserves_existing_output(tmp_path, capsys):
    from blackgrid.cli import EXIT_INVALID, EXIT_OK, main
    from tests.test_cli import fixture_config

    config = fixture_config(tmp_path, "987654321 987654322 0\n987654322 987654323 1209600\n")
    output = tmp_path / "full-report"
    args = ["ingest", str(config), "--data-root", str(tmp_path), "--output", str(output)]
    assert main(args) == EXIT_OK
    saved = (output / "ingestion.json").read_bytes()
    assert json.loads(saved)["validation"]["valid_events"] == 2
    assert "987654321" not in capsys.readouterr().out
    assert main(args) == EXIT_INVALID
    assert "output already exists" in capsys.readouterr().err
    assert (output / "ingestion.json").read_bytes() == saved
