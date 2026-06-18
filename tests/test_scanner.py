from pathlib import Path

from wissensdb.scanner import scan_repo
from wissensdb.schemas import Scope


def test_scan_repo_creates_code_map_writes(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text("class Service:\n    pass\n\ndef run():\n    pass\n", encoding="utf-8")

    writes = scan_repo(
        tmp_path,
        Scope(project="example-project", repo="example-repo"),
        max_files=10,
    )

    assert len(writes) == 1
    assert writes[0].title == "service.py"
    assert "class Service" in writes[0].content
