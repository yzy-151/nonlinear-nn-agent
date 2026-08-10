"""Knowledge ingestion from whitelisted project directories.

Every chunk carries provenance: source path, content hash, version and
created_at. Ingestion only walks allowed roots; anything outside the
whitelist is ignored.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source_path: str
    content_hash: str
    version: str
    created_at: float
    text: str
    citation: str
    namespace: tuple[str, ...] = ()


class KnowledgeIngestor:
    """Walk whitelisted roots and split files into provenanced chunks."""

    _MARKDOWN_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
    _DEFAULT_EXTENSIONS = (".md", ".json", ".yaml", ".yml", ".csv", ".txt")

    def __init__(
        self,
        roots: list[Path] | tuple[Path, ...],
        extensions: tuple[str, ...] = _DEFAULT_EXTENSIONS,
        version: str = "main",
        max_chars: int = 800,
    ):
        self._roots = [Path(root) for root in roots]
        self._extensions = tuple(ext.lower() for ext in extensions)
        self._version = version
        self._max_chars = max_chars

    def ingest(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for root in self._roots:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in self._extensions:
                    continue
                chunks.extend(self._ingest_file(root, path))
        return chunks

    def _ingest_file(self, root: Path, path: Path) -> list[KnowledgeChunk]:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return []
        rel = path.relative_to(root)
        created_at = time.time()
        if path.suffix.lower() == ".md":
            sections = self._split_markdown(text, rel)
        else:
            sections = self._split_plain(text, rel)
        chunks = []
        for index, (heading, body) in enumerate(sections):
            if not body.strip():
                continue
            chunk_id = f"{rel.as_posix().replace('/', '_').replace('.', '_')}-{index:03d}"
            content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            citation = f"{rel.as_posix()}#{heading}" if heading else rel.as_posix()
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source_path=str(path),
                    content_hash=content_hash,
                    version=self._version,
                    created_at=created_at,
                    text=body,
                    citation=citation,
                )
            )
        return chunks

    def _split_markdown(self, text: str, rel: Path) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_heading = rel.as_posix()
        current: list[str] = []

        def flush() -> None:
            nonlocal current
            if current:
                merged = "\n".join(current).strip()
                # 超长段落按行继续切块，保持 citation 指向同一标题
                for start in range(0, len(merged), self._max_chars):
                    sections.append((current_heading, merged[start : start + self._max_chars]))
                current = []

        for line in text.splitlines():
            match = self._MARKDOWN_HEADING.match(line)
            if match:
                flush()
                current_heading = f"{rel.as_posix()}#{match.group(2).strip()}"
            current.append(line)
        flush()
        return sections

    def _split_plain(self, text: str, rel: Path) -> list[tuple[str, str]]:
        lines = text.splitlines()
        sections: list[tuple[str, str]] = []
        for start in range(0, len(lines), 20):
            body = "\n".join(lines[start : start + 20]).strip()
            if body:
                sections.append((rel.as_posix(), body))
        return sections
