"""打包要部署的站点文件到 dist/，只装站点，不装开发文件。

用法：
    python deploy.py            # 只打包，生成 dist/
    python deploy.py --upload   # 打包 + 上传到 Cloudflare Pages

ponytail: 用 shutil 复制而不是构建。站点是静态的，build.py 已经生成好了，
再跑一遍 build.py 只会重复劳动。真要重建数据时先手动跑 build.py。
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"

# 必须部署的（站点本体）
FILES = ["index.html", "browse.html", "discover.html", "weekly.html", "about.html", "contact.html", "404.html"]
DIRS = ["assets", "data", "repo", "discover"]
# 上线后补的合规文件，有就带上
OPTIONAL = ["robots.txt", "sitemap.xml", "favicon.png", "favicon-32.png",
            "favicon.ico", "apple-touch-icon.png",
            "manifest.json", "_headers", "_redirects", "og-cover.png",
            "LICENSE", "NOTICE"]


def _assets_only(src_dir, names):
    """copytree 的 ignore 回调：assets/ 只保留站点真正引用的静态资源。

    shutil.copytree 会无条件把目录里的所有文件搬进 dist/，连 .bak 这类
    开发残留也会跟着上线、可通过 URL 下载。这里只放行 css / js / woff2
    以及 fonts 子目录。
    """
    keep = (".css", ".js", ".woff2")
    return [n for n in names
            if not (n == "fonts" and os.path.isdir(os.path.join(src_dir, n)))
            and not (os.path.isfile(os.path.join(src_dir, n)) and n.lower().endswith(keep))]


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    missing = []
    for f in FILES:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, DIST / f)
        else:
            missing.append(f)
    if missing:
        sys.exit(f"❌ 缺关键页面: {missing}")

    for d in DIRS:
        src = ROOT / d
        if not src.exists():
            sys.exit(f"❌ 缺目录: {d}")
        if d == "assets":
            shutil.copytree(src, DIST / d, ignore=_assets_only)
        else:
            shutil.copytree(src, DIST / d)

    for f in OPTIONAL:
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, DIST / f)

    # 统计
    n_files = sum(1 for _ in DIST.rglob("*") if _.is_file())
    size_mb = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file()) / 1024 / 1024
    biggest = max((p for p in DIST.rglob("*") if p.is_file()), key=lambda p: p.stat().st_size)

    print(f"✅ 打包完成: {n_files} 个文件 / {size_mb:.1f} MB")
    print(f"   最大单文件: {biggest.relative_to(DIST)}  {biggest.stat().st_size / 1024 / 1024:.1f} MB")

    # Cloudflare Pages 硬限制
    if n_files > 20000:
        print(f"❌ 超过 Cloudflare 20,000 文件上限（{n_files}）— 必须合并分片")
    elif n_files > 19000:
        print(f"⚠️  {n_files} 个文件，距 20,000 上限只剩 {20000 - n_files} 个")
    if biggest.stat().st_size > 25 * 1024 * 1024:
        print(f"❌ {biggest.name} 超过 25 MB 单文件上限")

    # 自检：关键文件在不在
    checks = [
        ("首页", DIST / "index.html"),
        ("全部项目", DIST / "browse.html"),
        ("发现", DIST / "discover.html"),
        ("周榜", DIST / "weekly.html"),
        ("关于", DIST / "about.html"),
        ("第一个分片", DIST / "data" / "page-1.json"),
        ("搜索索引", DIST / "data" / "s" / "index.json"),
        ("周榜数据", DIST / "data" / "weekly.json"),
        ("分类数据", DIST / "data" / "cats.json"),
        ("样式", DIST / "assets" / "site.css"),
        ("脚本", DIST / "assets" / "site.js"),
        ("字体", DIST / "assets" / "fonts" / "inter-tight.woff2"),
    ]
    bad = [name for name, p in checks if not p.exists()]
    if bad:
        sys.exit(f"❌ 部署包缺: {bad}")
    print("   ✓ 关键文件齐全（首页/浏览/周榜/关于/分片/搜索/数据/样式/脚本/字体）")

    if "--upload" in sys.argv:
        import subprocess
        print("\n上传到 Cloudflare Pages...")
        npx = "npx.cmd" if os.name == "nt" else "npx"
        r = subprocess.run(
            [npx, "wrangler", "pages", "deploy", "dist", "--project-name=gitplain",
             "--branch=main"],
            cwd=ROOT,
        )
        sys.exit(r.returncode)
    else:
        print("\n下一步: npx wrangler pages deploy dist --project-name=gitplain --branch=main")
        print("（必须带 --branch=main，否则发成 preview：日志报成功但线上不变）")
        print("（或 python deploy.py --upload 一步到位）")


if __name__ == "__main__":
    main()
