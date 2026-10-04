#!/usr/bin/env python3
"""Summarize a release from git so the announcement video can focus on what changed.

Usage:
  gather_release.py --repo . [--from v1.3.0] [--to v1.4.0]

Defaults: --to is HEAD, --from is the tag before it (or the last 20 commits when
the repo has no tags). Prints JSON to stdout:

  range, commits[{hash, type, scope, subject, body}], grouped{feat, fix, ...},
  files[{path, added, deleted}], likely_routes[...], changelog_excerpt

`likely_routes` is a heuristic for Next.js (app/ and pages/ routers) and plain
HTML sites. Treat it as a hint about where to point the browser, not proof.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout


def default_range(repo, frm, to):
    to = to or "HEAD"
    if frm:
        return frm, to
    try:
        tags = git(repo, "tag", "--sort=-creatordate").split()
    except RuntimeError:
        tags = []
    if to != "HEAD" and to in tags:
        i = tags.index(to)
        if i + 1 < len(tags):
            return tags[i + 1], to
    if to == "HEAD" and tags:
        # If HEAD is exactly the newest tag, compare against the previous tag.
        head = git(repo, "rev-parse", "HEAD").strip()
        newest = git(repo, "rev-list", "-n1", tags[0]).strip()
        if head == newest and len(tags) > 1:
            return tags[1], to
        return tags[0], to
    count = int(git(repo, "rev-list", "--count", "HEAD").strip() or 0)
    back = min(20, max(count - 1, 0))
    return f"HEAD~{back}", to


CONVENTIONAL = re.compile(r"^(?P<type>\w+)(\((?P<scope>[^)]+)\))?!?:\s*(?P<subject>.+)$")


def parse_commits(repo, rng):
    sep = "\x1e"
    fmt = f"%H%x1f%s%x1f%b{sep}"
    out = git(repo, "log", rng, f"--pretty=format:{fmt}", "--no-merges")
    commits = []
    for chunk in out.split(sep):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        h, subject, body = (chunk.split("\x1f") + ["", ""])[:3]
        m = CONVENTIONAL.match(subject)
        commits.append({
            "hash": h[:8],
            "type": (m.group("type").lower() if m else "other"),
            "scope": (m.group("scope") if m else None),
            "subject": (m.group("subject") if m else subject),
            "body": body.strip(),
        })
    return commits


def changed_files(repo, rng):
    out = git(repo, "diff", "--numstat", rng)
    files = []
    for line in out.splitlines():
        a, d, p = line.split("\t", 2)
        files.append({
            "path": p,
            "added": int(a) if a.isdigit() else 0,
            "deleted": int(d) if d.isdigit() else 0,
        })
    return files


def guess_routes(paths):
    """Map changed files to URL paths for common web layouts."""
    routes = set()
    for p in paths:
        # Next.js app router: app/foo/bar/page.tsx -> /foo/bar ; route groups (x) are dropped
        m = re.match(r"^(?:src/)?app/(.*?)/?page\.(?:tsx|jsx|ts|js|mdx)$", p)
        if m:
            seg = [s for s in m.group(1).split("/") if s and not (s.startswith("(") and s.endswith(")"))]
            routes.add("/" + "/".join(seg))
            continue
        # Next.js pages router: pages/foo.tsx -> /foo ; pages/index.tsx -> /
        m = re.match(r"^(?:src/)?pages/(.*)\.(?:tsx|jsx|ts|js|mdx)$", p)
        if m and not m.group(1).startswith(("api/", "_")):
            name = re.sub(r"(^|/)index$", "", m.group(1))
            routes.add("/" + name)
            continue
        # Static HTML sites
        if p.endswith(".html") and "node_modules" not in p:
            name = re.sub(r"index\.html$", "", p)
            routes.add("/" + name.removesuffix(".html"))
    return sorted(routes)


def changelog_excerpt(repo, version_hint):
    for name in ("CHANGELOG.md", "CHANGELOG", "HISTORY.md", "RELEASES.md"):
        f = Path(repo) / name
        if f.exists():
            text = f.read_text(errors="ignore")
            if version_hint:
                v = re.escape(version_hint.lstrip("v"))
                m = re.search(rf"^#+\s*\[?v?{v}\]?.*?(?=^#+\s*\[?v?\d|\Z)", text, re.S | re.M)
                if m:
                    return m.group(0).strip()[:2500]
            return text[:1500].strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    a = ap.parse_args()
    try:
        frm, to = default_range(a.repo, a.frm, a.to)
        rng = f"{frm}..{to}"
        commits = parse_commits(a.repo, rng)
        files = changed_files(a.repo, rng)
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

    grouped = {}
    for c in commits:
        grouped.setdefault(c["type"], []).append(c["subject"])

    ui_files = [f["path"] for f in files if not re.search(r"(^|/)(node_modules|\.next|dist)/|\.lock$|package-lock", f["path"])]
    print(json.dumps({
        "range": rng,
        "commit_count": len(commits),
        "commits": commits,
        "grouped": grouped,
        "files": files,
        "likely_routes": guess_routes(ui_files),
        "changelog_excerpt": changelog_excerpt(a.repo, to if to != "HEAD" else None),
    }, indent=2))


if __name__ == "__main__":
    main()
