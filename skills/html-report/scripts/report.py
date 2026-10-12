#!/usr/bin/env python3
"""html-report: turn a YAML report spec into one self-contained, light-only HTML file.

  report.py init  --type status|findings|update|brief [-o report.yaml]   start a spec from a skeleton
  report.py build report.yaml [-o report.html]                           render it
  report.py embed fig.png --alt "..." --caption "..."                    print a <figure> block (raw HTML)
  report.py gallery OUT.html report1.html report2.html ...               index page linking rendered reports

Text fields accept a small markdown subset: **bold**, *italic*, `code`, [text](url).
Everything else is escaped, so write "AS < 30" as-is. Use a {html: ...} block for raw HTML.
See ../SKILL.md for the spec reference.
"""
import argparse, base64, csv, datetime, html, pathlib, re, sys

import yaml

SKILL = pathlib.Path(__file__).resolve().parent.parent
TYPES = ("status", "findings", "update", "brief")

# status key -> (pill class, pill label, tile label). Order here is tile order.
STATUS = {
    "fixed":     ("ok",   "Fixed",          "fixed"),
    "done":      ("ok",   "Done",           "done"),
    "validated": ("info", "Validated",      "validated"),
    "answered":  ("info", "Answered",       "answered by analysis"),
    "progress":  ("chg",  "In progress",    "in progress"),
    "decision":  ("dec",  "Needs decision", "need your decision"),
    "open":      ("bad",  "Open",           "open"),
    "failed":    ("bad",  "Failed",         "failed"),
    "notfound":  ("nf",   "Not found",      "asked for, not found in code"),
    "deferred":  ("park", "Deferred",       "deferred"),
}
ALIASES = {"inprogress": "progress", "wip": "progress", "needsdecision": "decision", "pass": "done",
           "notfoundincode": "notfound", "parked": "deferred", "fail": "failed"}
ATTENTION = ("open", "failed", "notfound", "decision")
PRIORITY = {"p0": "bad", "critical": "bad", "p1": "chg", "high": "chg"}
PRIVACY = "Contains no patient data, no sample identifiers and no file contents."
TOP_KEYS = {"type", "title", "heading", "project", "date", "meta", "audience", "tiles", "summary", "blocks",
            "footer", "privacy", "methods", "demo", "lettered",
            # status
            "mode", "previous", "tests", "sections", "items_tsv", "columns", "outside", "running", "discrepancies",
            # update / brief
            "open", "asks", "changed", "next"}


def esc(s):
    return html.escape(str(s), quote=True)


def md(s):
    """Escape, then apply **bold**, *italic*, `code`, [text](url)."""
    if s is None:
        return ""
    s = esc(str(s).strip())
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", keep, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", s)


def status_key(raw):
    k = re.sub(r"[\s_\-]", "", str(raw).lower())
    k = ALIASES.get(k, k)
    if k not in STATUS:
        sys.exit(f"unknown status {raw!r}; use one of: {', '.join(STATUS)}")
    return k


def pill(raw, counted=True):
    k = status_key(raw)
    cls, label, _ = STATUS[k]
    ds = f' data-status="{k}"' if counted else ""
    return f'<span class="pill {cls}"{ds}>{label}</span>'


def tile(n, label, kind="", status=None):
    ds = f' data-status="{status}"' if status else ""
    return f'<div class="tile {esc(kind)}"{ds}><div class="n">{md(n)}</div><div class="l">{md(label)}</div></div>'


def ul(items, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f"<ul{c}>" + "".join(f"<li>{md(i)}</li>" for i in items) + "</ul>"


# ---------------------------------------------------------------- status items

def load_spec(path):
    path = pathlib.Path(path)
    spec = yaml.safe_load(path.read_text()) or {}
    spec["_dir"] = path.parent
    return spec


def collect_sections(spec):
    """Return [{'title', 'sub', 'items': [...]}], from inline sections and/or items_tsv."""
    sections = [dict(s, items=list(s.get("items") or [])) for s in (spec.get("sections") or [])]
    tsv = spec.get("items_tsv")
    if tsv:
        by_title = {s["title"]: s for s in sections}
        with open(spec["_dir"] / tsv, newline="") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                row = {k: v for k, v in row.items() if v not in (None, "")}
                title = row.pop("section", "Items")
                if title not in by_title:
                    by_title[title] = {"title": title, "items": []}
                    sections.append(by_title[title])
                by_title[title]["items"].append(row)
    for s in sections:
        for it in s["items"]:
            if "id" not in it or "status" not in it:
                sys.exit(f"item in section {s.get('title')!r} needs at least id and status: {it}")
            it["id"] = str(it["id"])
            it["_k"] = status_key(it["status"])
    return sections


def changed_ids(spec, sections):
    prev = spec.get("previous")
    if not prev:
        return set(), None
    p = load_spec(spec["_dir"] / prev)
    old = {it["id"]: (it["_k"], str(it.get("done", "")).strip()) for s in collect_sections(p) for it in s["items"]}
    now = {it["id"]: (it["_k"], str(it.get("done", "")).strip()) for s in sections for it in s["items"]}
    return {i for i, v in now.items() if old.get(i) != v}, str(p.get("date", prev))


def ids_label(label, ids):
    return f"{label}: {', '.join(ids)}" if len(ids) <= 6 else label


def render_status(spec, out):
    sections = collect_sections(spec)
    changed, prev_date = changed_ids(spec, sections)
    items = [it for s in sections for it in s["items"]]
    ledger = spec.get("mode", "round") == "ledger"

    tiles = []
    for k, (cls, _, label) in STATUS.items():
        ids = [it["id"] for it in items if it["_k"] == k]
        if ids:
            tiles.append(tile(len(ids), ids_label(label, ids), cls, status=k))
    if changed:
        tiles.append(tile(len(changed), f"changed since {prev_date}", "chg"))
    t = spec.get("tests")
    if t:
        lab = "tests" + (f", from {t['before']}" if "before" in t else "") + (f" on {t['since']}" if "since" in t else "")
        tiles.append(tile(f"{t['now']:,}" if isinstance(t["now"], int) else t["now"], lab, "ok"))
    tiles += [tile(x["n"], x["label"], x.get("kind", "")) for x in spec.get("tiles") or []]
    out.append('<div class="tiles">' + "\n".join(tiles) + "</div>")
    summary(spec, out)

    if ledger:
        att = [it for it in items if it["_k"] in ATTENTION]
        disc = spec.get("discrepancies") or []
        if att or disc:
            out.append('<div class="attn">')
            if att:
                out.append(f"<h3>Needs attention ({len(att)})</h3><ul>" + "".join(
                    f'<li><b>{esc(it["id"])}</b> {pill(it["status"], counted=False)} {md(it.get("asked", ""))}</li>'
                    for it in att) + "</ul>")
            if disc:
                out.append("<h3>Where earlier reports and the code disagree</h3>" + ul(disc))
            out.append("</div>")

    cols = {"id": "ID", "asked": "What you asked", "done": "What was done, and how it was verified", "status": "Status"}
    cols.update(spec.get("columns") or {})
    has_prio = any(it.get("priority") for it in items)
    if has_prio or changed:
        key = []
        if has_prio:
            key += ['<span><i style="background:var(--bad)"></i>P0 / critical</span>',
                    '<span><i style="background:var(--chg)"></i>P1 / high</span>']
        if changed:
            key.append(f'<span><span class="chg-mark">&#9679;</span> changed since {esc(prev_date)}</span>')
        key_html = '<div class="key">' + "".join(key) + "</div>"
    else:
        key_html = ""

    for i, s in enumerate(sections):
        n = len(s["items"])
        sub = s.get("sub") or f"{n} item{'s' if n != 1 else ''}"
        out.append(f'<h2>{md(s["title"])} <span class="cnt">{md(sub)}</span></h2>')
        if i == 0:
            out.append(key_html)
        if s.get("intro"):
            out.append(f"<p>{md(s['intro'])}</p>")
        out.append('<div class="tw"><table class="stack"><thead><tr>'
                   f'<th>{esc(cols["id"])}</th><th>{esc(cols["asked"])}</th><th>{esc(cols["done"])}</th>'
                   f'<th>{esc(cols["status"])}</th></tr></thead><tbody>')
        for it in s["items"]:
            ch = it["id"] in changed
            prio = str(it.get("priority", ""))
            idcls = " ".join(filter(None, ["id", PRIORITY.get(prio.lower(), "")]))
            mark = ' <span class="chg-mark">&#9679;</span>' if ch else ""
            sev = f'<span class="sev">{esc(prio)}</span>' if prio else ""
            more = f' <span class="more">&rarr; {md(it["link"])}</span>' if it.get("link") else ""
            commit = f'<br><code>{esc(it["commit"])}</code>' if it.get("commit") else ""
            trc = ' class="changed"' if ch else ""
            out.append(f'<tr{trc}>'
                       f'<td class="{idcls}" data-label="{esc(cols["id"])}">{esc(it["id"])}{mark}{sev}</td>'
                       f'<td data-label="Asked">{md(it.get("asked", ""))}</td>'
                       f'<td data-label="Done">{md(it.get("done", ""))}{more}</td>'
                       f'<td class="st" data-label="Status">{pill(it["status"])}{commit}</td></tr>')
        out.append("</tbody></table></div>")

    if spec.get("running"):
        out.append("<h2>What is running now</h2>" + ul(spec["running"]))
    if spec.get("outside"):
        out.append('<h2>Outside your numbered list <span class="cnt">items not yet confirmed, and what else I found</span></h2>')
        out.append('<div class="tw"><table class="stack"><thead><tr><th>What you flagged, or what I found</th>'
                   "<th>Where it stands</th><th>Status</th></tr></thead><tbody>")
        for o in spec["outside"]:
            out.append(f'<tr><td data-label="Item">{md(o.get("item"))}</td><td data-label="Where">{md(o.get("where"))}</td>'
                       f'<td class="st" data-label="Status">{pill(o["status"], counted=False)}</td></tr>')
        out.append("</tbody></table></div>")
    blocks(spec, out)


# ---------------------------------------------------------------- generic blocks

def summary(spec, out):
    s = spec.get("summary")
    if not s:
        return
    if isinstance(s, str):
        s = {"body": s}
    kind = esc(s.get("kind", ""))
    head = f"<b>{md(s['headline'])}</b> " if s.get("headline") else ""
    out.append(f'<div class="note {kind}">{head}{md(s.get("body", ""))}</div>')


def bars_svg(b):
    data = b["data"]
    unit = b.get("unit", "")
    vmax = b.get("max") or max(float(d["value"]) for d in data) or 1
    W, L, R, H = 680, 230, 70, 26
    h = H * len(data) + 8
    rows = []
    for i, d in enumerate(data):
        y = 4 + i * H
        w = max(1.0, (W - L - R) * float(d["value"]) / vmax)
        color = f"var(--{d.get('kind', 'accent')})"
        rows.append(f'<text x="{L - 8}" y="{y + 16}" text-anchor="end">{esc(d["label"])}</text>'
                    f'<rect x="{L}" y="{y + 4}" width="{w:.1f}" height="{H - 10}" rx="2" style="fill:{color}"/>'
                    f'<text class="v" x="{L + w + 6:.1f}" y="{y + 16}">{esc(d["value"])}{esc(unit)}</text>')
    return (f'<svg class="bars" viewBox="0 0 {W} {h}" width="100%" role="img" aria-label="{esc(b.get("alt", b.get("caption", "bar chart")))}">'
            f'<line x1="{L}" y1="0" x2="{L}" y2="{h}"/>' + "".join(rows) + "</svg>")


def figure(inner, caption, n):
    cap = f"<figcaption><b>Figure {n}.</b> {md(caption)}</figcaption>" if caption else ""
    return f"<figure>{inner}{cap}</figure>"


def table(t):
    cols = t["columns"]
    num = {c if isinstance(c, int) else cols.index(c) for c in t.get("num", [])}
    nc = lambda i: ' class="num"' if i in num else ""
    th = "".join(f"<th{nc(i)}>{md(c)}</th>" for i, c in enumerate(cols))
    rows = "".join("<tr>" + "".join(f"<td{nc(i)}>{md(v)}</td>" for i, v in enumerate(r)) + "</tr>"
                   for r in t["rows"])
    cap = f'<p class="muted">{md(t["caption"])}</p>' if t.get("caption") else ""
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div>{cap}'


def blocks(spec, out):
    lettered = spec.get("lettered", spec["type"] == "update")
    state = {"letter": 0, "fig": 0, "tabs": 0}

    def h2(text, sub=None):
        prefix = ""
        if lettered:
            prefix = f"{chr(65 + state['letter'])}. "
            state["letter"] += 1
        s = f' <span class="cnt">{md(sub)}</span>' if sub else ""
        return f"<h2>{prefix}{md(text)}{s}</h2>"

    def asks_html(asks, level="h2"):
        return f'<{level}>What I need from you</{level}><ol class="asks">' + "".join(
            f"<li><b>{md(a['ask'])}</b> {md(a.get('detail', ''))}</li>" if isinstance(a, dict) else f"<li>{md(a)}</li>"
            for a in asks) + "</ol>"

    def tabs(b, depth):
        state["tabs"] += 1
        g, items = f"tb{state['tabs']}", b["tabs"]
        numbered = b.get("numbered", True)
        out.append(f'<div class="tabs" id="{g}">')
        for i in range(1, len(items) + 1):
            out.append(f'<input type="radio" name="{g}" id="{g}-{i}"{" checked" if i == 1 else ""}>')
        out.append('<div class="tabbar">' + "".join(
            f'<label for="{g}-{i}">{f"{i} &middot; " if numbered else ""}{md(t["label"])}</label>'
            for i, t in enumerate(items, 1)) + "</div>")
        hl = "h2" if depth == 0 else "h3"
        for i, t in enumerate(items, 1):
            out.append(f'<div class="panel" id="{g}-p{i}">')
            if t.get("heading"):
                out.append(f"<{hl}>{md(t['heading'])}</{hl}>")
            if t.get("summary"):
                out.append(f'<p class="lede">{md(t["summary"])}</p>')
            render(t.get("blocks") or [], depth + 1)
            if t.get("asks"):
                out.append(asks_html(t["asks"], "h3"))
            out.append("</div>")
        out.append("</div>")
        n = range(1, len(items) + 1)
        spec.setdefault("_css", []).extend([
            ",".join(f'#{g}-{i}:checked~.tabbar label[for="{g}-{i}"]' for i in n)
            + "{color:var(--ink);background:var(--surface);border-color:var(--rule);margin-bottom:-1px}",
            ",".join(f"#{g}-{i}:checked~#{g}-p{i}" for i in n) + "{display:block}"])

    def render(blist, depth=0):
        for b in blist:
            if "tabs" in b:
                tabs(b, depth)
            elif "h2" in b:
                out.append(h2(b["h2"], b.get("sub")))
            elif "h3" in b:
                out.append(f"<h3>{md(b['h3'])}</h3>")
            elif "p" in b:
                out.append(f"<p>{md(b['p'])}</p>")
            elif "note" in b:
                head = f"<b>{md(b['headline'])}</b> " if b.get("headline") else ""
                out.append(f'<div class="note {esc(b.get("kind", ""))}">{head}{md(b["note"])}</div>')
            elif "list" in b:
                tag = "ol" if b.get("ordered") else "ul"
                out.append(f"<{tag}>" + "".join(f"<li>{md(i)}</li>" for i in b["list"]) + f"</{tag}>")
            elif "tiles" in b:
                out.append('<div class="tiles">' + "".join(tile(x["n"], x["label"], x.get("kind", "")) for x in b["tiles"]) + "</div>")
            elif "table" in b:
                out.append(table(b["table"]))
            elif "bars" in b:
                state["fig"] += 1
                out.append(figure(bars_svg(b["bars"]), b["bars"].get("caption"), state["fig"]))
            elif "figure" in b:
                f = b["figure"]
                state["fig"] += 1
                data = base64.b64encode((spec["_dir"] / f["png"]).read_bytes()).decode()
                out.append(figure(f'<img src="data:image/png;base64,{data}" alt="{esc(f.get("alt", ""))}">', f.get("caption"), state["fig"]))
            elif "details" in b:
                d = b["details"]
                body = f"<pre><code>{esc(d['code'])}</code></pre>" if "code" in d else ul(d.get("items", []))
                out.append(f"<details><summary>{md(d.get('summary', 'Details'))}</summary>{body}</details>")
            elif "html" in b:
                out.append(str(b["html"]))
            else:
                sys.exit(f"unknown block: {list(b)}; use h2, h3, p, note, list, tiles, table, bars, figure, details, tabs, html")

    render(spec.get("blocks") or [])
    if spec["type"] in ("update",) and spec.get("open"):
        out.append(h2("Still open or deferred") + ul(spec["open"]))
    if spec["type"] == "brief":
        if spec.get("changed"):
            out.append("<h2>What changed</h2>" + ul(spec["changed"]))
        if spec.get("next"):
            out.append("<h2>Next</h2>" + ul(spec["next"]))
    if spec.get("asks"):
        out.append(asks_html(spec["asks"]))


# ---------------------------------------------------------------- page

def build(spec):
    typ = spec.get("type")
    if typ not in TYPES:
        sys.exit(f"type must be one of {TYPES}, got {typ!r}")
    if not spec.get("title"):
        sys.exit("title is required (2-6 words; it becomes the <title>)")
    for k in set(spec) - TOP_KEYS - {"_dir"}:
        print(f"warning: unknown top-level key {k!r} ignored", file=sys.stderr)
    date = str(spec.get("date") or datetime.date.today().isoformat())
    spec["date"] = date
    privacy = spec.get("privacy", True)

    out = [f"<h1>{md(spec.get('heading') or spec['title'])}</h1>"]
    meta = md(spec.get("meta", ""))
    if typ == "status":
        meta = (meta + " &middot; " if meta else "") + f"status as of {esc(date)}"
    elif date not in meta:
        meta = (meta + " &middot; " if meta else "") + esc(date)
    out.append(f'<p class="meta">{meta}</p>')
    if spec.get("demo"):
        out.append(f'<div class="demo">{md(spec["demo"])}</div>')

    if typ == "status":
        render_status(spec, out)
    else:
        if spec.get("tiles"):
            out.append('<div class="tiles">' + "".join(tile(x["n"], x["label"], x.get("kind", "")) for x in spec["tiles"]) + "</div>")
        if typ == "update" and isinstance(spec.get("summary"), str):
            spec["summary"] = {"headline": "In one paragraph.", "body": spec["summary"], "kind": "ok"}
        summary(spec, out)
        blocks(spec, out)

    if spec.get("methods"):
        m = spec["methods"]
        out.append(f"<details><summary>{md(m.get('summary', 'Methods, commands and paths'))}</summary>"
                   f"<pre><code>{esc(m.get('code', ''))}</code></pre></details>")

    foot = f"Generated {esc(date)}" + (f" for {md(spec['project'])}" if spec.get("project") else "") + "."
    if spec.get("footer"):
        foot += " " + md(spec["footer"])
    if privacy:
        foot += "<br>" + PRIVACY
    out.append(f"<footer>{foot}</footer>")

    css = (SKILL / "style.css").read_text() + "".join(f"  {r}\n" for r in spec.get("_css", []))
    privacy_meta = "" if privacy else '\n<meta name="html-report-privacy" content="off">'
    main_cls = ' class="brief"' if typ == "brief" else ""
    return f"""<!DOCTYPE html>
<html lang="en" style="color-scheme:light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="generator" content="html-report">
<meta name="html-report-type" content="{typ}">{privacy_meta}
<title>{esc(spec['title'])}</title>
<style>
{css}</style>
</head>
<body><main{main_cls}>

""" + "\n".join(out) + "\n\n</main></body></html>\n"


def gallery(out_path, pages):
    rows = []
    for p in pages:
        s = pathlib.Path(p).read_text()
        title = re.search(r"<title>(.*?)</title>", s, re.S)
        typ = re.search(r'name="html-report-type" content="(\w+)"', s)
        rel = pathlib.Path(p).resolve().relative_to(pathlib.Path(out_path).resolve().parent)
        rows.append([f"[{title.group(1) if title else p}]({rel})", typ.group(1) if typ else ""])
    spec = {"type": "brief", "title": "html-report examples", "privacy": False, "_dir": pathlib.Path("."),
            "meta": "Rendered from the YAML specs next to each file. Project, people and numbers are invented.",
            "blocks": [{"table": {"columns": ["Report", "Type"], "rows": rows}}]}
    pathlib.Path(out_path).write_text(build(spec))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("init"); i.add_argument("--type", choices=TYPES, required=True); i.add_argument("-o", "--out")
    b = sp.add_parser("build"); b.add_argument("spec"); b.add_argument("-o", "--out")
    e = sp.add_parser("embed"); e.add_argument("png"); e.add_argument("--alt", required=True); e.add_argument("--caption", required=True)
    g = sp.add_parser("gallery"); g.add_argument("out"); g.add_argument("pages", nargs="+")
    a = p.parse_args()

    if a.cmd == "init":
        text = (SKILL / "skeletons" / f"{a.type}.yaml").read_text()
        if not a.out:
            sys.stdout.write(text); return
        out = pathlib.Path(a.out)
        if out.exists():
            sys.exit(f"{out} exists; not overwriting")
        out.write_text(text)
        print(f"wrote {out}; fill every REPLACE, then: report.py build {out}")
    elif a.cmd == "build":
        spec = load_spec(a.spec)
        out = pathlib.Path(a.out) if a.out else pathlib.Path(a.spec).with_suffix(".html")
        out.write_text(build(spec))
        print(f"wrote {out}; now: check_report.py {out}")
    elif a.cmd == "embed":
        data = base64.b64encode(pathlib.Path(a.png).read_bytes()).decode()
        print(f'<figure><img src="data:image/png;base64,{data}" alt="{esc(a.alt)}"><figcaption>{a.caption}</figcaption></figure>')
    elif a.cmd == "gallery":
        gallery(a.out, a.pages)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
