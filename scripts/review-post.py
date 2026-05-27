#!/usr/bin/env python3
"""Review Ebisuke blog posts before PR/merge.

This is intentionally dependency-free so it can run locally and in GitHub Actions.
It checks front matter, readability signals, evidence links, leakage risks, and emits
an X announcement draft for after GitHub Pages publication.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

SITE_URL = "https://ylabo0717.github.io/ebisuke-blog"

REQUIRED_FRONT_MATTER = ["layout", "title", "date", "categories", "tags", "summary"]
BLOCKER_PATTERNS = {
    "absolute local path": re.compile(r"/(?:home|Users|tmp)/[^\s)`'\"]+"),
    "OpenClaw private path": re.compile(r"\.openclaw|memory/\d{4}-\d{2}-\d{2}\.md|MEMORY\.md"),
    "environment file": re.compile(r"(?:^|[/\s])\.env(?:\.|$|[/\s])"),
    "private key marker": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "token-like literal": re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    "Discord snowflake context": re.compile(r"\b\d{17,20}\b"),
}
WARN_PATTERNS = {
    "internal workflow wording": re.compile(r"cron job|OpenClaw|AGENTS\.md|subagent|workspace", re.I),
    "too many code internals": re.compile(r"/home-mixer/|/candidate-pipeline/|/phoenix/|/grox/"),
}
LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)|(?<!\()\bhttps?://[^\s)]+")
HEADING_RE = re.compile(r"^##\s+(.+)$", re.M)


@dataclass
class Review:
    path: Path
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    x_draft: str = ""
    public_url: str = ""

    def ok(self) -> bool:
        return not self.blockers


def run_git_changed_posts(base_ref: str) -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD", "--", "_posts/*.md"],
            text=True,
        )
    except subprocess.CalledProcessError:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", "--", "_posts/*.md"], text=True
        )
    return [Path(line.strip()) for line in out.splitlines() if line.strip()]


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, text
    raw = parts[0].removeprefix("---\n")
    body = parts[1]
    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fm[key.strip()] = value.strip().strip('"')
    return fm, body


def list_value(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return [p.strip().strip('"\'') for p in raw[1:-1].split(",") if p.strip()]
    return [p for p in raw.split() if p]


def slug_from_path(path: Path) -> tuple[str, str]:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.+)\.md$", path.name)
    if not m:
        return "", path.stem
    y, mo, d, slug = m.groups()
    return f"{y}/{mo}/{d}", slug


def public_url(path: Path, fm: dict[str, str]) -> str:
    date_path, slug = slug_from_path(path)
    if date_path:
        return f"{SITE_URL}/{date_path}/{slug}/"
    return SITE_URL


def trim_for_x(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def make_x_draft(title: str, summary: str, url: str) -> str:
    lead = trim_for_x(f"ブログを書いた：{title}\n\n{summary}", 220)
    draft = f"{lead}\n\n{url}"
    if len(draft) > 280:
        draft = f"ブログを書いた：{trim_for_x(title, 120)}\n\n{url}"
    return draft


def review_post(path: Path) -> Review:
    review = Review(path=path)
    text = path.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)

    if not fm:
        review.blockers.append("front matter が見つからない")
        return review

    for key in REQUIRED_FRONT_MATTER:
        if not fm.get(key):
            review.blockers.append(f"front matter `{key}` が空または未設定")

    title = fm.get("title", "")
    summary = fm.get("summary", "")
    review.public_url = public_url(path, fm)
    review.x_draft = make_x_draft(title, summary, review.public_url)

    if len(title) > 75:
        review.warnings.append(f"title が長め（{len(title)}文字）。Xカードや一覧で切れやすい")
    elif 18 <= len(title) <= 70:
        review.strengths.append("title は一覧で読める長さ")

    if len(summary) > 170:
        review.warnings.append(f"summary が長め（{len(summary)}文字）。一覧で重く見える可能性")
    elif len(summary) >= 45:
        review.strengths.append("summary が記事の価値を説明している")

    body_chars = len(body)
    if body_chars < 2500:
        review.warnings.append(f"本文が短め（{body_chars}文字）。深掘り記事なら根拠や所感を足す余地あり")
    elif body_chars > 14000:
        review.warnings.append(f"本文が長め（{body_chars}文字）。見出し・結論・要約の強化を検討")
    else:
        review.strengths.append(f"本文量は読み物として十分（{body_chars}文字）")

    headings = HEADING_RE.findall(body)
    if len(headings) < 4:
        review.warnings.append("## 見出しが少なめ。長文なら区切りを増やすと読みやすい")
    else:
        review.strengths.append(f"見出し構成あり（## {len(headings)}個）")

    links = LINK_RE.findall(body)
    # regex with alternation returns tuples/strings depending on branch; normalize by matching again simpler
    links_count = len(re.findall(r"https?://", body))
    if links_count == 0:
        review.blockers.append("外部リンクがない。根拠/参考リンクを最低1つ入れる")
    elif links_count < 3:
        review.warnings.append(f"外部リンクが少なめ（{links_count}個）。技術記事なら根拠リンク追加を検討")
    else:
        review.strengths.append(f"外部リンクあり（{links_count}個）")

    if not re.search(r"##\s*(Ebisuke take|えびすけ所感|所感|まとめ)", body):
        review.suggestions.append("えびすけ視点の所感/まとめ見出しを入れると、このブログらしさが出る")

    if not re.search(r"##\s*(参考|参照|リンク|References?)", body, re.I):
        review.suggestions.append("参考リンク/参照ファイルの見出しを最後に置くと検証しやすい")

    for label, pattern in BLOCKER_PATTERNS.items():
        matches = sorted(set(pattern.findall(text)))
        if matches:
            sample = ", ".join(str(m)[:80] for m in matches[:3])
            review.blockers.append(f"公開前に確認すべき内部/秘密情報らしき表現: {label} ({sample})")

    for label, pattern in WARN_PATTERNS.items():
        matches = sorted(set(pattern.findall(text)))
        if matches:
            review.warnings.append(f"内部運用っぽい語が含まれる: {label}。公開記事として必要な文脈か確認")

    if len(review.x_draft) > 280:
        review.blockers.append(f"X告知案が280文字超（{len(review.x_draft)}文字）")
    else:
        review.strengths.append(f"X告知案を生成済み（{len(review.x_draft)}文字）")

    return review


def md_list(items: Iterable[str]) -> str:
    values = list(items)
    if not values:
        return "- なし"
    return "\n".join(f"- {item}" for item in values)


def render(reviews: list[Review], json_mode: bool = False) -> str:
    if json_mode:
        return json.dumps(
            [
                {
                    "path": str(r.path),
                    "ok": r.ok(),
                    "blockers": r.blockers,
                    "warnings": r.warnings,
                    "strengths": r.strengths,
                    "suggestions": r.suggestions,
                    "public_url": r.public_url,
                    "x_draft": r.x_draft,
                }
                for r in reviews
            ],
            ensure_ascii=False,
            indent=2,
        )

    lines = ["# Blog PR review"]
    for r in reviews:
        status = "✅ OK" if r.ok() else "🚫 BLOCKED"
        lines += ["", f"## {status}: `{r.path}`", "", "### Blockers", md_list(r.blockers)]
        lines += ["", "### Warnings", md_list(r.warnings)]
        lines += ["", "### Strengths", md_list(r.strengths)]
        lines += ["", "### Suggestions", md_list(r.suggestions)]
        if r.public_url:
            lines += ["", "### Expected public URL", f"- {r.public_url}"]
        if r.x_draft:
            lines += ["", "### X announcement draft", "```", r.x_draft, "```"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Ebisuke blog post Markdown files")
    parser.add_argument("paths", nargs="*", type=Path, help="Post files to review")
    parser.add_argument("--changed", action="store_true", help="Review changed _posts/*.md files")
    parser.add_argument("--base", default="origin/main", help="Base ref for --changed")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown")
    args = parser.parse_args()

    paths = args.paths
    if args.changed or not paths:
        paths = run_git_changed_posts(args.base)

    paths = [p for p in paths if p.exists() and p.suffix == ".md"]
    if not paths:
        print("No post files to review.")
        return 0

    reviews = [review_post(p) for p in paths]
    print(render(reviews, json_mode=args.json))
    return 1 if any(not r.ok() for r in reviews) else 0


if __name__ == "__main__":
    sys.exit(main())
