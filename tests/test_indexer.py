import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from gamewiki.indexer import scan


class IndexerTests(unittest.TestCase):
    def test_scans_metadata_without_opening_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            game = source / "测试游戏"
            game.mkdir(parents=True)
            (game / "攻略.md").write_text("绝不能进入索引的正文", encoding="utf-8")
            (game / "工具.exe").write_bytes(b"MZ-not-executed")
            (game / "忽略.xyz").write_text("ignored", encoding="utf-8")
            database = root / "index.sqlite3"

            result = scan(source, database)

            self.assertEqual(result.indexed, 2)
            self.assertEqual(result.skipped, 1)
            with closing(sqlite3.connect(database)) as connection:
                rows = connection.execute(
                    "SELECT name, kind, game FROM files ORDER BY name"
                ).fetchall()
                schema = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE name = 'files'"
                ).fetchone()[0]
            self.assertEqual(rows, [("工具.exe", "binary", "测试游戏"), ("攻略.md", "document", "测试游戏")])
            self.assertNotIn("正文", schema)


if __name__ == "__main__":
    unittest.main()
