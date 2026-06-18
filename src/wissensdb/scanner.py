import hashlib
import subprocess
from collections.abc import Iterable
from pathlib import Path

from wissensdb.enums import KnowledgeType
from wissensdb.schemas import KnowledgeSource, KnowledgeWrite, Scope

IGNORED_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

TEXT_EXTENSIONS = {
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".sql",
    ".sh",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".swift",
}


def scan_repo(
    root: Path,
    scope: Scope,
    max_files: int = 300,
) -> list[KnowledgeWrite]:
    root = root.resolve()
    commit_sha = git_commit(root)
    writes: list[KnowledgeWrite] = []
    for path in iter_candidate_files(root):
        rel_path = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8", errors="ignore")
        summary = summarize_file(rel_path, content)
        if not summary:
            continue
        writes.append(
            KnowledgeWrite(
                scope=scope,
                type=KnowledgeType.CODE_MAP,
                title=f"{rel_path}",
                content=summary,
                confidence=0.72,
                source=KnowledgeSource(
                    source_type="repo_scan",
                    source_ref=f"{root}@{commit_sha or 'unknown'}:{rel_path}",
                    path=rel_path,
                    commit_sha=commit_sha,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                ),
            )
        )
        if len(writes) >= max_files:
            break
    return writes


def iter_candidate_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.stat().st_size > 200_000:
            continue
        yield path


def summarize_file(rel_path: str, content: str) -> str:
    lines = content.splitlines()
    if not lines:
        return ""
    headings = [line.strip("# ").strip() for line in lines if line.startswith("#")][:5]
    symbols = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("def ", "class ", "async def ", "function ", "export function ")):
            symbols.append(stripped[:160])
        if len(symbols) >= 12:
            break
    parts = [f"File `{rel_path}` is part of the codebase."]
    if headings:
        parts.append("Headings: " + "; ".join(headings))
    if symbols:
        parts.append("Key symbols: " + "; ".join(symbols))
    parts.append(f"Approx size: {len(lines)} lines.")
    return "\n".join(parts)


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip()
