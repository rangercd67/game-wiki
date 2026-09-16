from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "library"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "local" / "index.sqlite3"

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

# OOXML 容器（ZIP + XML）由标准库解析，因此需要分别限制容器体积、
# 单个部件解压后的体积（防压缩炸弹）与最终输出的字符数。
OOXML_PREVIEW_EXTENSIONS = {".docx", ".xlsx"}
MAX_OOXML_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_OOXML_MEMBER_BYTES = 8 * 1024 * 1024
MAX_OOXML_TEXT_CHARS = 200_000


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


def preview_kind(extension: str) -> str | None:
    """返回预览载荷类型；None 表示该类型只提供元数据。

    前端据此决定渲染方式，避免在 JavaScript 里重复维护一份扩展名清单。
    """
    if extension in IMAGE_PREVIEW_EXTENSIONS:
        return "image"
    if extension in TEXT_PREVIEW_EXTENSIONS or extension in OOXML_PREVIEW_EXTENSIONS:
        return "text"
    return None
