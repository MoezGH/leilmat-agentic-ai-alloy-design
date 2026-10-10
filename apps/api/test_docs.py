"""
The documentation must not rot.

* The two reference pages are GENERATED from the code (scripts/gen_reference_docs.py); this fails
  if they differ from what the generator would write now, so the reference can only change
  together with the code.
* Every relative link in the docs and the top-level markdown must point at a file that exists, and
  every `#anchor` must match a real heading — so a renamed heading or moved file is caught.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC_FILES = sorted(
    [*ROOT.glob("docs/**/*.md"), *(ROOT / n for n in
     ("README.md", "CONTRIBUTING.md", "SECURITY.md", "NOTICE.md", "CHANGELOG.md"))]
)
DOC_FILES = [p for p in DOC_FILES if p.exists() and "sprint_2_6" not in p.parts]


def _generator():
    spec = importlib.util.spec_from_file_location("gen_reference_docs",
                                                   ROOT / "scripts" / "gen_reference_docs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", ["api.md", "configuration.md"])
def test_reference_pages_match_the_code(name):
    gen = _generator()
    committed = (ROOT / "docs" / "reference" / name).read_text()
    assert committed == gen.PAGES[name](), (
        f"docs/reference/{name} is stale. Regenerate it: python scripts/gen_reference_docs.py"
    )


# ── links ───────────────────────────────────────────────────────────────────────────────────

_LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _slug(heading: str) -> str:
    """GitHub-style anchor for a Markdown heading."""
    h = re.sub(r"`", "", heading.strip().lower())
    h = re.sub(r"[^\w\- ]", "", h)          # drop punctuation, keep word chars, hyphen, space
    return h.replace(" ", "-")


def _anchors(md: Path) -> set[str]:
    out, seen = set(), {}
    in_code = False
    for line in md.read_text().splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            base = _slug(m.group(1))
            n = seen.get(base, 0)
            out.add(base if n == 0 else f"{base}-{n}")
            seen[base] = n + 1
    return out


def _links(md: Path):
    text = md.read_text()
    text = re.sub(r"```.*?```", "", text, flags=re.S)       # ignore code blocks
    text = re.sub(r"`[^`\n]*`", "", text)                   # ...and inline code
    for m in _LINK.finditer(text):
        yield m.group(1)


@pytest.mark.parametrize("md", DOC_FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_and_anchors_resolve(md):
    problems = []
    for target in _links(md):
        if re.match(r"^(https?:|mailto:|tel:)", target):
            continue
        path_part, _, anchor = target.partition("#")
        dest = md if not path_part else (md.parent / path_part).resolve()
        if not dest.exists():
            problems.append(f"{target}  -> missing file")
            continue
        if anchor and dest.suffix == ".md" and anchor not in _anchors(dest):
            problems.append(f"{target}  -> no such heading in {dest.name}")
    assert not problems, f"{md.relative_to(ROOT)}: " + "; ".join(problems)


def test_images_referenced_by_the_docs_exist():
    missing = []
    for md in DOC_FILES:
        text = md.read_text()
        for src in re.findall(r'(?:!\[[^\]]*\]\(|<img[^>]*src=")([^)"\s]+)', text):
            if re.match(r"^(https?:|data:)", src):
                continue
            if not (md.parent / src).resolve().exists():
                missing.append(f"{md.relative_to(ROOT)}: {src}")
    assert not missing, "missing images: " + "; ".join(missing)
