#!/usr/bin/env python3
"""Pre-send checks for an html-report file. Exit 1 on any FAIL; WARNs need a human look.

  check_report.py REPORT.html [...] [--patterns extra.txt ...]

Identifier patterns load from ../patterns/identifiers.txt, then every --patterns file, then every
file in $HTML_REPORT_PATTERNS (colon-separated). Use those for site-specific IDs you must never send.
Matched text is never printed — only pattern names and counts.
"""
import argparse, os, pathlib, re, sys

SKILL = pathlib.Path(__file__).resolve().parent.parent


def load_patterns(extra):
    files = [SKILL / "patterns" / "identifiers.txt", *extra]
    files += [f for f in os.environ.get("HTML_REPORT_PATTERNS", "").split(":") if f]
    pats = []
    for f in files:
        for line in pathlib.Path(f).read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            level, name, rx = line.split("\t", 2)
            pats.append((level.strip().upper(), name.strip(), re.compile(rx.strip())))
    return pats


def check(path, patterns):
    path = pathlib.Path(path)
    s = path.read_text(errors="replace")
    body = re.sub(r"data:image/[a-z+]+;base64,[A-Za-z0-9+/=]+", "DATAURI", s)
    text = re.sub(r"<style>.*?</style>", "", body, flags=re.S)
    visible = re.sub(r"<[^>]+>", " ", text)
    typ = re.search(r'name="html-report-type" content="(\w+)"', s)
    typ = typ.group(1) if typ else None
    fails, warns = [], []

    if not re.match(r"\s*<!doctype html>", s, re.I):
        fails.append("missing <!DOCTYPE html>")
    t = re.search(r"<title>(.*?)</title>", s, re.S)
    if not t or not t.group(1).strip():
        fails.append("missing <title>")
    elif not 2 <= len(t.group(1).split()) <= 6:
        warns.append(f"title should be 2-6 words ({len(t.group(1).split())})")
    if '<meta name="color-scheme" content="light">' not in s:
        fails.append('missing <meta name="color-scheme" content="light">')
    if re.search(r"prefers-color-scheme\s*:\s*dark|\[data-theme", s):
        fails.append("dark-mode CSS present: reports are light only")
    if re.search(r"<(?:script|link|img|iframe|source)[^>]+(?:src|href)=\"(?:https?:)?//", s, re.I) or "@import" in s:
        fails.append("external script/stylesheet/image: the file must be self-contained")
    if "<script" in s.lower():
        warns.append("<script> present: many mail clients strip it; the report must read without it")
    if "REPLACE" in visible:
        fails.append(f"{visible.count('REPLACE')} unfilled REPLACE placeholder(s)")
    if len(re.findall(r"<h1\b", text)) != 1:
        warns.append("expected exactly one <h1>")
    if 'name="html-report-privacy" content="off"' not in s and not re.search(r"no patient data", visible, re.I):
        fails.append("footer is missing the 'Contains no patient data...' line")
    if re.search(r"(?<!tw\">)<table\b", text):
        warns.append('a <table> is not wrapped in <div class="tw"> (wide tables will overflow)')

    # tile counts must match the status pills in the tables
    for k, n in re.findall(r'<div class="tile[^"]*" data-status="(\w+)"><div class="n">([\d,]+)</div>', text):
        pills = len(re.findall(rf'<span class="pill \w+" data-status="{k}">', text))
        if int(n.replace(",", "")) != pills:
            fails.append(f"tile '{k}' says {n} but the tables have {pills} '{k}' item(s)")

    # local links must resolve
    for href in re.findall(r'<a href="([^"#:]+)(?:#[^"]*)?"', text):
        if not (path.parent / href).exists():
            warns.append(f"link target not found next to the report: {href}")

    if typ == "brief":
        if 'class="tabs"' in text:
            warns.append("brief uses tabs; a brief should fit one screen without them")
        if len(re.findall(r'<div class="tile[ "]', text)) > 3:
            warns.append("brief has more than 3 boxes")
        if any(len(re.findall(r"<li>", u)) > 3 for u in re.findall(r"<ul>.*?</ul>", text, re.S)):
            warns.append("brief has a list longer than 3 bullets")
        if len(visible.split()) > 350:
            warns.append(f"brief is {len(visible.split())} words; aim for one screen (<350)")

    for level, name, rx in patterns:
        hits = set(rx.findall(visible))
        if hits:
            (fails if level == "FAIL" else warns).append(f"{name}: {len(hits)} distinct match(es)")

    mb = len(s.encode()) / 1e6
    if mb > 20:
        fails.append(f"{mb:.1f} MB: over a 25 MB mail attachment limit once encoded")
    elif mb > 5:
        warns.append(f"{mb:.1f} MB: shrink embedded figures (120-150 dpi PNG, or SVG)")
    return typ, mb, fails, warns


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("reports", nargs="+")
    p.add_argument("--patterns", action="append", default=[])
    a = p.parse_args(argv)
    patterns = load_patterns(a.patterns)
    ok = True
    for r in a.reports:
        typ, mb, fails, warns = check(r, patterns)
        print(f"== {r} ({typ or 'unknown type'}, {mb:.2f} MB)")
        for f in fails:
            print(f"  FAIL  {f}")
        for w in warns:
            print(f"  WARN  {w}")
        if not fails and not warns:
            print("  OK")
        ok &= not fails
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
