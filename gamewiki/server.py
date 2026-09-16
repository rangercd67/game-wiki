from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
from contextlib import closing
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .config import (
    DEFAULT_DATABASE,
    DEFAULT_SOURCE,
    IMAGE_PREVIEW_EXTENSIONS,
    MAX_IMAGE_PREVIEW_BYTES,
    MAX_OOXML_ARCHIVE_BYTES,
    MAX_TEXT_PREVIEW_BYTES,
    OOXML_PREVIEW_EXTENSIONS,
    TEXT_PREVIEW_EXTENSIONS,
    preview_kind,
)
from .ooxml import OoxmlError, extract_text

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


class WikiHandler(SimpleHTTPRequestHandler):
    source = DEFAULT_SOURCE
    database = DEFAULT_DATABASE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.database}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            try:
                self._api_get(parsed.path, parse_qs(parsed.query))
            except (FileNotFoundError, sqlite3.OperationalError):
                self._json({"error": "索引尚未建立，请先运行扫描。"}, HTTPStatus.SERVICE_UNAVAILABLE)
            except PermissionError as error:
                self._json({"error": str(error)}, HTTPStatus.FORBIDDEN)
            except OoxmlError as error:
                self._json({"error": f"文档无法解析：{error}"}, HTTPStatus.UNPROCESSABLE_ENTITY)
            except (KeyError, ValueError) as error:
                self._json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        super().do_GET()

    def _api_get(self, path: str, query: dict[str, list[str]]) -> None:
        if path == "/api/stats":
            with closing(self._connection()) as connection:
                metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                kinds = [dict(row) for row in connection.execute(
                    "SELECT kind, COUNT(*) count FROM files GROUP BY kind ORDER BY count DESC"
                )]
            self._json({"metadata": metadata, "kinds": kinds})
            return

        if path == "/api/games":
            with closing(self._connection()) as connection:
                rows = connection.execute(
                    "SELECT game, COUNT(*) count, SUM(size) size FROM files "
                    "GROUP BY game ORDER BY count DESC, game COLLATE NOCASE"
                )
                games = [dict(row) for row in rows]
            self._json({"games": games})
            return

        if path == "/api/files":
            self._list_files(query)
            return

        if path == "/api/preview":
            self._preview(query)
            return

        self._json({"error": "接口不存在"}, HTTPStatus.NOT_FOUND)

    def _list_files(self, query: dict[str, list[str]]) -> None:
        keyword = query.get("q", [""])[0].strip()
        game = query.get("game", [""])[0].strip()
        kind = query.get("kind", [""])[0].strip()
        page = max(1, int(query.get("page", ["1"])[0]))
        limit = min(100, max(1, int(query.get("limit", ["40"])[0])))

        clauses: list[str] = []
        parameters: list[object] = []
        if keyword:
            clauses.append("(name LIKE ? ESCAPE '\\' OR relative_path LIKE ? ESCAPE '\\')")
            escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            parameters.extend([f"%{escaped}%", f"%{escaped}%"])
        if game:
            clauses.append("game = ?")
            parameters.append(game)
        if kind:
            clauses.append("kind = ?")
            parameters.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with closing(self._connection()) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM files {where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"""SELECT id, relative_path, name, extension, kind, size, modified_at, game
                FROM files {where} ORDER BY modified_ns DESC, name COLLATE NOCASE
                LIMIT ? OFFSET ?""",
                [*parameters, limit, (page - 1) * limit],
            )
            files = [
                {**dict(row), "preview": preview_kind(row["extension"])}
                for row in rows
            ]
        self._json({"files": files, "total": total, "page": page, "limit": limit})

    def _preview(self, query: dict[str, list[str]]) -> None:
        relative = unquote(query.get("path", [""])[0]).replace("\\", "/")
        if not relative:
            raise ValueError("缺少预览路径")
        with closing(self._connection()) as connection:
            row = connection.execute(
                "SELECT relative_path, extension, size FROM files WHERE relative_path = ?", (relative,)
            ).fetchone()
        if row is None:
            raise FileNotFoundError(relative)

        source = self.source.resolve(strict=True)
        target = (source / Path(row["relative_path"])).resolve(strict=True)
        if not target.is_relative_to(source) or not target.is_file():
            raise PermissionError("预览路径越界")
        extension = row["extension"]
        size = target.stat().st_size

        if extension in TEXT_PREVIEW_EXTENSIONS:
            if size > MAX_TEXT_PREVIEW_BYTES:
                raise PermissionError("文本超过 2 MB，仅保留元数据")
            content = target.read_text(encoding="utf-8", errors="replace")
            self._json({"type": "text", "content": content, "path": relative})
            return
        if extension in OOXML_PREVIEW_EXTENSIONS:
            if size > MAX_OOXML_ARCHIVE_BYTES:
                raise PermissionError(
                    f"文档超过 {MAX_OOXML_ARCHIVE_BYTES // 1048576} MB，仅保留元数据"
                )
            content = extract_text(target, extension)
            self._json(
                {"type": "text", "format": "ooxml", "content": content, "path": relative}
            )
            return
        if extension in IMAGE_PREVIEW_EXTENSIONS:
            if size > MAX_IMAGE_PREVIEW_BYTES:
                raise PermissionError("图片超过 30 MB，仅保留元数据")
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "private, max-age=60")
            self.end_headers()
            with target.open("rb") as stream:
                while chunk := stream.read(64 * 1024):
                    self.wfile.write(chunk)
            return
        raise PermissionError("此类型禁止内容预览，仅显示元数据")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动本地 Game Wiki")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    WikiHandler.source = args.source
    WikiHandler.database = args.database
    server = ThreadingHTTPServer((args.host, args.port), WikiHandler)
    print(f"Game Wiki: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
