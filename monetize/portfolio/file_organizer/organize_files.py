# -*- coding: utf-8 -*-
"""
폴더 자동 정리기

다운로드 폴더처럼 뒤섞인 파일을 종류별/날짜별 하위 폴더로 옮기고,
같은 이름이 있으면 자동으로 번호를 붙입니다. --dry-run 으로 미리보기 가능.

사용 예:
    python organize_files.py ~/Downloads --by type --dry-run
    python organize_files.py ~/Downloads --by date
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

CATEGORIES = {
    "이미지": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic"},
    "문서": {".pdf", ".doc", ".docx", ".hwp", ".hwpx", ".txt", ".ppt", ".pptx"},
    "엑셀": {".xls", ".xlsx", ".csv"},
    "압축": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "영상": {".mp4", ".mov", ".avi", ".mkv"},
    "음악": {".mp3", ".wav", ".flac", ".m4a"},
    "설치파일": {".exe", ".msi", ".dmg"},
}


def category_of(path: Path) -> str:
    ext = path.suffix.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return "기타"


def unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    n = 1
    while True:
        cand = target.with_name(f"{target.stem} ({n}){target.suffix}")
        if not cand.exists():
            return cand
        n += 1


def plan_moves(folder: Path, by: str):
    moves = []
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.name.startswith("."):
            continue
        if by == "type":
            sub = category_of(p)
        else:
            sub = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m")
        moves.append((p, folder / sub / p.name))
    return moves


def organize(folder: Path, by: str = "type", dry_run: bool = False):
    done = []
    for src, dst in plan_moves(folder, by):
        if dry_run:
            done.append((src, dst))
            continue
        dst.parent.mkdir(exist_ok=True)
        dst = unique_target(dst)
        shutil.move(str(src), str(dst))
        done.append((src, dst))
    return done


def main(argv=None):
    ap = argparse.ArgumentParser(description="폴더 자동 정리")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--by", choices=["type", "date"], default="type")
    ap.add_argument("--dry-run", action="store_true", help="실제로 옮기지 않고 결과만 출력")
    args = ap.parse_args(argv)

    results = organize(args.folder, args.by, args.dry_run)
    for src, dst in results:
        print(f"{'[미리보기] ' if args.dry_run else ''}{src.name} → {dst.parent.name}/{dst.name}")
    print(f"총 {len(results)}개 파일 {'정리 예정' if args.dry_run else '정리 완료'}")


if __name__ == "__main__":
    sys.exit(main())
