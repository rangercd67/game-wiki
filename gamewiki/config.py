from pathlib import Path

DEFAULT_SOURCE = Path(r"E:\Games\GameTools")
DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data" / "local" / "index.sqlite3"

DOCUMENT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".pdf", ".doc", ".docx",
    ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".tsv", ".rtf",
    ".html", ".htm", ".xml", ".yaml", ".yml", ".ini", ".cfg",
}
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
}
DATA_EXTENSIONS = {".json", ".jsonl", ".geojson"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
BINARY_EXTENSIONS = {
    ".exe", ".dll", ".msi", ".apk", ".bin", ".iso", ".pak", ".so",
    ".dylib", ".bat", ".cmd", ".ps1", ".com", ".scr",
}

INDEXED_EXTENSIONS = (
    DOCUMENT_EXTENSIONS
    | IMAGE_EXTENSIONS
    | DATA_EXTENSIONS
    | ARCHIVE_EXTENSIONS
    | BINARY_EXTENSIONS
)

TEXT_PREVIEW_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json",
    ".jsonl", ".geojson", ".xml", ".yaml", ".yml", ".ini", ".cfg",
}
IMAGE_PREVIEW_EXTENSIONS = IMAGE_EXTENSIONS - {".svg"}
MAX_TEXT_PREVIEW_BYTES = 2 * 1024 * 1024
MAX_IMAGE_PREVIEW_BYTES = 30 * 1024 * 1024


def kind_for_extension(extension: str) -> str:
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if extension in DATA_EXTENSIONS:
        return "data"
    if extension in DOCUMENT_EXTENSIONS:
        return "document"
    if extension in ARCHIVE_EXTENSIONS:
        return "archive"
    return "binary"
