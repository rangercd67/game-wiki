from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import DEFAULT_DATABASE, DEFAULT_SOURCE, INDEXED_EXTENSIONS, kind_for_extension


SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    relative_path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    extension TEXT NOT NULL,
    kind TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_ns INTEGER NOT NULL,
    modified_at TEXT NOT NULL,
    game TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_game ON files(game);
CREATE INDEX IF NOT EXISTS idx_files_kind ON files(kind);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class ScanResult:
    indexed: int
    skipped: int
    errors: int
    total_bytes: int


def _game_for(relative_path: Path) -> str:
    return relative_path.parts[0] if len(relative_path.parts) > 1 else "未分类"


def scan(source: Path, database: Path) -> ScanResult:
    """Replace the index using directory entries and stat metadata only."""
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise NotADirectoryError(source)

    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    indexed = skipped = errors = total_bytes = 0
    try:
        connection.executescript(SCHEMA)
        connection.execute("BEGIN")
        connection.execute("DELETE FROM files")

        for directory, dirnames, filenames in os.walk(source, followlinks=False):
            dirnames.sort()
            filenames.sort()
            for filename in filenames:
                path = Path(directory, filename)
                extension = path.suffix.lower()
                if extension not in INDEXED_EXTENSIONS:
                    skipped += 1
                    continue
                try:
                    stat = path.stat(follow_symlinks=False)
                    relative = path.relative_to(source)
                except (OSError, ValueError):
                    errors += 1
                    continue

                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                connection.execute(
                    """INSERT INTO files
                    (relative_path, name, extension, kind, size, modified_ns, modified_at, game)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        relative.as_posix(), filename, extension,
                        kind_for_extension(extension), stat.st_size,
                        stat.st_mtime_ns, modified, _game_for(relative),
                    ),
                )
                indexed += 1
                total_bytes += stat.st_size

        now = datetime.now(tz=timezone.utc).isoformat()
        values = {
            "source": str(source),
            "scanned_at": now,
            "indexed": str(indexed),
            "skipped": str(skipped),
            "errors": str(errors),
            "total_bytes": str(total_bytes),
        }
        connection.executemany(
            "INSERT OR REPLACE INTO metadata(key, value) VALUES (?, ?)", values.items()
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return ScanResult(indexed, skipped, errors, total_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(description="只读扫描游戏资料元数据")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    result = scan(args.source, args.database)
    print(
        f"索引完成：{result.indexed} 个文件，跳过 {result.skipped} 个，"
        f"错误 {result.errors} 个。"
    )


if __name__ == "__main__":
    main()
