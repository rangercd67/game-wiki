"""把 `dist-wiki/` 发布到 GitHub Pages 的 `gh-pages` 分支。

为什么不用 `git subtree push`——`dist-wiki/` 是构建产物，被 `.gitignore` 排除，
而 subtree 要求该目录在 `main` 上被跟踪；照那个路子走，每次重建都会把
70 MB 二进制媒体再写进 `main` 的历史，仓库会永久膨胀。

这里用一个**持久的发布缓存**（`tmp/deploy-cache/`，默认已忽略）持有 `gh-pages`
的完整克隆：把产物同步进去、提交、快进推送。主仓库的工作区与索引完全不受
影响，产物也不必入库。

为什么必须是完整克隆而不是"造一棵树再推"：如果每次造一个无父提交再强制推，
客户端手里没有远端旧提交的对象，就无法在打包时把它们排除，实测每次发布都会
**重传全部 70 MB**。保留克隆后推送变成普通快进，git 按内容去重，未改动的
图片一次都不会上传，日常只改 HTML 时推送量在 1 MB 以内。

用法：

    py -m gamewiki.deploy --remote https://github.com/<user>/<repo>.git
    py -m gamewiki.deploy --remote <url> --build
    py -m gamewiki.deploy --remote <url> --domain wiki.example.com
    py -m gamewiki.deploy --remote <url> --dry-run     # 同步提交，不推送
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT
from .wiki import CONTENT_ROOT, DEFAULT_OUTPUT, build

DEFAULT_BRANCH = "gh-pages"
DEFAULT_CACHE = PROJECT_ROOT / "tmp" / "deploy-cache"
# 顶层以下划线开头的文件会被 Jekyll 吞掉；.nojekyll 由 wiki.build 写出
_ALLOWED_UNDERSCORE = {".nojekyll"}
_BAD_URL_CHARS = "#?%"
_REMOTE_PATTERNS = (
    re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"),
    re.compile(r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"),
    re.compile(r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"),
)
_AUTH_HINT = (
    "先完成一次授权，然后重跑本命令：\n"
    "  git-credential-manager github login\n"
    "  git-credential-manager github login --pat <带 repo 权限的 PAT>"
)


class DeployError(RuntimeError):
    """发布流程中可预期的失败，直接展示给使用者。"""


def _run(args: list[str], *, cwd: Path | None = None, check: bool = True):
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise DeployError(
            f"git {' '.join(args)} 失败（退出码 {result.returncode}）：\n"
            f"{(result.stderr or result.stdout).strip()}"
        )
    return result


def _push(args: list[str], cwd: Path) -> None:
    """执行推送，失败时给出授权提示而不是抛 git 原始报错。"""
    result = _run(args, cwd=cwd, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise DeployError(
            "推送失败——最常见的原因是本机还没有 Git 写权限。\n"
            f"git 原始输出：\n{detail}\n\n{_AUTH_HINT}"
        )


def scan(output: Path) -> tuple[int, int, list[str]]:
    """统计产物，并挑出在 GitHub Pages 上会出问题的路径名。"""
    if not (output / "index.html").is_file():
        raise DeployError(f"{output} 下没有 index.html，先执行 py -m gamewiki.wiki")

    files = [p for p in output.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    problems: list[str] = []
    for path in files:
        relative = path.relative_to(output)
        name = relative.as_posix()
        if relative.parent == Path(".") and name.startswith("_") and name not in _ALLOWED_UNDERSCORE:
            problems.append(f"{name}：顶层下划线开头会被 Jekyll 忽略（缺少 .nojekyll？）")
        if any(char in name for char in _BAD_URL_CHARS):
            problems.append(f"{name}：文件名含 {'、'.join(_BAD_URL_CHARS)}，静态托管下 URL 会被截断")
    return len(files), total, problems


def _normalize_remote(remote: str) -> str:
    """把本地路径形式的远端转成绝对路径。

    缓存仓库的工作目录和主仓库不同，相对路径在第二次发布时会被解析到
    缓存目录里面去，于是找不到仓库。URL 与 scp 风格地址原样返回。
    """
    if "://" in remote or re.match(r"^[^/\\]+@[^:]+:", remote):
        return remote
    path = Path(remote)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return str(path)


def pages_url(remote: str, output: Path) -> str | None:
    """从远端地址推断站点地址；写了 CNAME 就优先用自定义域名。"""
    cname = output / "CNAME"
    if cname.is_file():
        domain = cname.read_text(encoding="utf-8").strip()
        if domain:
            return f"https://{domain}/"

    for pattern in _REMOTE_PATTERNS:
        match = pattern.match(remote)
        if not match:
            continue
        owner, repo = match.group("owner"), match.group("repo")
        if repo.lower() == f"{owner.lower()}.github.io":
            return f"https://{owner}.github.io/"
        return f"https://{owner}.github.io/{repo}/"
    return None


def _sync(source: Path, target: Path) -> None:
    """把产物目录镜像进缓存仓库的工作区：先清掉旧内容（保留 .git），再整树拷贝。"""
    for entry in target.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    shutil.copytree(source, target, dirs_exist_ok=True)


def _prepare_cache(cache: Path, remote: str, branch: str) -> None:
    """确保缓存目录里有一个位于目标分支的可用克隆。"""
    if not (cache / ".git").is_dir():
        if cache.exists():
            shutil.rmtree(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        print(f"首次发布：克隆 {remote} → {cache}")
        result = _run(["clone", "--no-checkout", remote, str(cache)], check=False)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise DeployError(f"克隆失败：\n{detail}\n\n{_AUTH_HINT}")
    else:
        _run(["remote", "set-url", "origin", remote], cwd=cache)

    _run(["fetch", "origin", "--prune"], cwd=cache)

    if _run(
        ["rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"],
        cwd=cache,
        check=False,
    ).returncode == 0:
        _run(["checkout", "-B", branch, f"origin/{branch}"], cwd=cache)
    else:
        print(f"远端还没有 {branch} 分支，创建孤立分支")
        _run(["checkout", "--orphan", branch], cwd=cache)
        # 孤立分支会沿用当前索引，清空它以免把 main 的文件带进发布分支
        _run(["rm", "-rf", "--cached", "."], cwd=cache, check=False)


def publish(
    output: Path = DEFAULT_OUTPUT,
    remote: str = "",
    branch: str = DEFAULT_BRANCH,
    message: str | None = None,
    dry_run: bool = False,
    cache: Path = DEFAULT_CACHE,
) -> dict:
    """把产物目录发布到远端分支，返回发布结果。"""
    output, cache = Path(output), Path(cache)
    if not remote:
        raise DeployError("必须用 --remote 指定远端仓库地址")
    remote = _normalize_remote(remote)

    count, total, problems = scan(output)
    if problems:
        raise DeployError("产物里有不适合 GitHub Pages 的路径：\n  " + "\n  ".join(problems))

    message = message or f"site: 发布 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    _prepare_cache(cache, remote, branch)
    _sync(output, cache)
    _run(["add", "-A"], cwd=cache)

    changed = _run(["diff", "--cached", "--quiet"], cwd=cache, check=False).returncode != 0
    if changed:
        _run(["commit", "--quiet", "-m", message], cwd=cache)
    else:
        print("产物与上次发布一致，没有新提交")

    commit = _run(["rev-parse", "HEAD"], cwd=cache).stdout.strip()

    if not dry_run:
        print(f"推送到 {remote} 的 {branch} 分支…")
        _push(["push", "origin", f"HEAD:refs/heads/{branch}"], cwd=cache)

    return {
        "files": count,
        "bytes": total,
        "commit": commit,
        "branch": branch,
        "remote": remote,
        "changed": changed,
        "dry_run": dry_run,
        "cache": cache,
        "url": pages_url(remote, output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="把 dist-wiki 发布到 GitHub Pages")
    parser.add_argument("--remote", required=True, help="远端仓库，例如 https://github.com/u/r.git")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--domain", default=None, help="写入 CNAME，例如 wiki.example.com")
    parser.add_argument("--build", action="store_true", help="发布前先重新构建站点")
    parser.add_argument("--message", default=None, help="覆盖提交信息")
    parser.add_argument("--dry-run", action="store_true", help="只提交到缓存，不推送")
    parser.add_argument("--library", type=Path, default=None)
    args = parser.parse_args()

    if args.build:
        manifest = build(CONTENT_ROOT, args.output, args.library, args.domain, clean=True)
        print(f"已重建：{manifest['pages']} 个页面，{manifest['site_bytes'] / 1048576:.2f} MB")
    elif args.domain:
        (Path(args.output) / "CNAME").write_text(args.domain.strip() + "\n", encoding="utf-8")

    report = publish(args.output, args.remote, args.branch, args.message, args.dry_run, args.cache)
    verb = "已生成待发布提交" if report["dry_run"] else "已发布"
    print(
        f"{verb}：{report['files']} 个文件，{report['bytes'] / 1048576:.2f} MB，"
        f"提交 {report['commit'][:12]} → {report['branch']}"
    )
    if report["url"]:
        print(f"站点地址：{report['url']}")


if __name__ == "__main__":
    main()
