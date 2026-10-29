#!/usr/bin/env python3
# package.py — blender-learn-pipeline 打包脚本
# 职责：打包时自动递增版本号 → 同步更新 SKILL.md / README / 用户手册 / 技术手册 中的版本 → 产出 dist zip
# 用法：
#   python package.py                # patch +1（1.0.0 -> 1.0.1）
#   python package.py --minor        # minor +1（1.0.0 -> 1.1.0）
#   python package.py --major        # major +1
#   python package.py --no-bump      # 不递增，仅按当前版本重新打包
import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_DIR = ROOT / "blender-learn-pipeline"
VERSION_FILE = ROOT / "VERSION"
DIST = ROOT / "dist"

# 版本号出现的位置：文件 -> 匹配模式（模式里 \d+\.\d+\.\d+ 会被替换）
VERSION_SLOTS = {
    VERSION_FILE: [re.compile(r"^\d+\.\d+\.\d+$", re.M)],
    SKILL_DIR / "SKILL.md": [re.compile(r"(?<=^version: )\d+\.\d+\.\d+$", re.M)],
    SKILL_DIR / "scripts" / "blender_learn.py": [re.compile(r'(?<=^VERSION = ")\d+\.\d+\.\d+(?=")', re.M)],
    ROOT / "README.md": [re.compile(r"(?<=当前版本：v)\d+\.\d+\.\d+")],
    ROOT / "用户手册.md": [re.compile(r"(?<=版本：v)\d+\.\d+\.\d+")],
    ROOT / "技术手册.md": [re.compile(r"(?<=版本：v)\d+\.\d+\.\d+")],
}

ZIP_EXCLUDE = re.compile(r"__pycache__|\.pyc$|\.bak$|~$")


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def bump(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    return {"major": f"{major + 1}.0.0",
            "minor": f"{major}.{minor + 1}.0",
            "patch": f"{major}.{minor}.{patch + 1}"}[part]


def apply_version(new_version: str) -> None:
    for path, patterns in VERSION_SLOTS.items():
        if not path.exists():
            print(f"[WARN] 版本槽文件缺失，跳过: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            text, n = pat.subn(new_version, text)
            if n == 0:
                print(f"[WARN] 未找到版本号位置: {path.name} / {pat.pattern}")
        path.write_text(text, encoding="utf-8")
        print(f"[OK] 版本号已写入 {path.name} -> {new_version}")


def make_zip(new_version: str) -> Path:
    DIST.mkdir(exist_ok=True)
    zip_path = DIST / f"blender-learn-pipeline-v{new_version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(SKILL_DIR.rglob("*")):
            if p.is_dir() or ZIP_EXCLUDE.search(p.name):
                continue
            zf.write(p, SKILL_DIR.name / p.relative_to(SKILL_DIR))
    print(f"[OK] 打包完成: {zip_path} ({zip_path.stat().st_size / 1024:.0f} KB)")
    return zip_path


def main():
    ap = argparse.ArgumentParser(description="版本递增 + 文档同步 + 打包")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--major", action="store_true")
    g.add_argument("--minor", action="store_true")
    g.add_argument("--patch", action="store_true")
    g.add_argument("--no-bump", action="store_true", help="不递增，仅重新打包")
    args = ap.parse_args()

    old = read_version()
    part = "major" if args.major else "minor" if args.minor else "patch"
    new = old if args.no_bump else bump(old, part)
    print(f"版本: {old} -> {new}")
    apply_version(new)
    make_zip(new)


if __name__ == "__main__":
    sys.exit(main())
