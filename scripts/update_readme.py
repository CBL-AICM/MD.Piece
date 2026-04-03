#!/usr/bin/env python3
"""Auto-update dynamic sections in README.md."""

import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone, timedelta


REPO = "CBL-AICM/MD.Piece"
README_PATH = "README.md"


def get_contributors():
    """Fetch contributors from GitHub API."""
    url = f"https://api.github.com/repos/{REPO}/contributors?per_page=20"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"Warning: Failed to fetch contributors: {e}")
        return []


def get_repo_stats():
    """Get repo statistics from git and GitHub."""
    stats = {}

    # Commit count
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        stats["commits"] = result.stdout.strip()
    except Exception:
        stats["commits"] = "N/A"

    # File count (tracked)
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True, text=True, check=True,
        )
        stats["files"] = str(len(result.stdout.strip().splitlines()))
    except Exception:
        stats["files"] = "N/A"

    # Last commit date
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            capture_output=True, text=True, check=True,
        )
        stats["last_commit"] = result.stdout.strip()[:10]
    except Exception:
        stats["last_commit"] = "N/A"

    # Python LOC (rough)
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.py"],
            capture_output=True, text=True, check=True,
        )
        py_files = result.stdout.strip().splitlines()
        total_lines = 0
        for f in py_files:
            try:
                result2 = subprocess.run(
                    ["wc", "-l", f],
                    capture_output=True, text=True,
                )
                total_lines += int(result2.stdout.strip().split()[0])
            except Exception:
                # Windows fallback
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                        total_lines += sum(1 for _ in fh)
                except Exception:
                    pass
        stats["python_loc"] = str(total_lines)
    except Exception:
        stats["python_loc"] = "N/A"

    # API endpoint count
    try:
        result = subprocess.run(
            ["git", "ls-files", "backend/routers/*.py"],
            capture_output=True, text=True, check=True,
        )
        stats["api_modules"] = str(len(result.stdout.strip().splitlines()))
    except Exception:
        stats["api_modules"] = "N/A"

    return stats


def build_contributors_section(contributors):
    """Build markdown table for contributors."""
    if not contributors:
        return "_無法載入貢獻者資訊_"

    lines = []
    # Use avatar table layout (max 6 per row)
    row_size = 6
    lines.append("<table>")
    for i in range(0, len(contributors), row_size):
        row = contributors[i : i + row_size]
        lines.append("  <tr>")
        for c in row:
            name = c.get("login", "?")
            avatar = c.get("avatar_url", "")
            url = c.get("html_url", "#")
            count = c.get("contributions", 0)
            lines.append(
                f'    <td align="center">'
                f'<a href="{url}">'
                f'<img src="{avatar}" width="60" style="border-radius:50%" />'
                f"<br /><sub><b>{name}</b></sub></a>"
                f"<br /><sub>{count} commits</sub></td>"
            )
        lines.append("  </tr>")
    lines.append("</table>")
    return "\n".join(lines)


def build_status_section(stats):
    """Build project status badges/table."""
    tw = timezone(timedelta(hours=8))
    now = datetime.now(tw).strftime("%Y-%m-%d %H:%M (UTC+8)")

    lines = [
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| 總 Commits | {stats.get('commits', 'N/A')} |",
        f"| 追蹤檔案數 | {stats.get('files', 'N/A')} |",
        f"| Python 程式碼行數 | {stats.get('python_loc', 'N/A')} |",
        f"| API 模組數 | {stats.get('api_modules', 'N/A')} |",
        f"| 最後更新 | {stats.get('last_commit', 'N/A')} |",
        f"",
        f"_自動更新於 {now}_",
    ]
    return "\n".join(lines)


def replace_section(content, tag, replacement):
    """Replace content between <!-- TAG:START --> and <!-- TAG:END -->."""
    pattern = re.compile(
        rf"(<!-- {tag}:START -->)\n?(.*?)(<!-- {tag}:END -->)",
        re.DOTALL,
    )
    return pattern.sub(rf"\1\n{replacement}\n\3", content)


def main():
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # Update contributors
    contributors = get_contributors()
    contrib_md = build_contributors_section(contributors)
    content = replace_section(content, "CONTRIBUTORS", contrib_md)

    # Update status
    stats = get_repo_stats()
    status_md = build_status_section(stats)
    content = replace_section(content, "STATUS", status_md)

    if content != original:
        with open(README_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print("README.md updated.")
    else:
        print("README.md is already up to date.")


if __name__ == "__main__":
    main()
