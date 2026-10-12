import importlib.util, pathlib, re, shutil, subprocess, sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "html-report" / "scripts"
EXAMPLES = ROOT / "examples"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report, checker = load("report"), load("check_report")
PATTERNS = checker.load_patterns([])


def build(tmp_path, spec_dict, name="r"):
    p = tmp_path / f"{name}.yaml"
    p.write_text(yaml.safe_dump(spec_dict))
    out = tmp_path / f"{name}.html"
    out.write_text(report.build(report.load_spec(p)))
    return out


def fails(path):
    return checker.check(path, PATTERNS)[2]


@pytest.fixture
def examples(tmp_path):
    d = tmp_path / "ex"
    shutil.copytree(EXAMPLES, d)
    for f in sorted(d.glob("*.yaml")):
        f.with_suffix(".html").write_text(report.build(report.load_spec(f)))
    return d


def test_every_example_builds_and_passes(examples):
    for html in sorted(examples.glob("2026-*.html")):
        typ, _, f, w = checker.check(html, PATTERNS)
        assert not f, (html.name, f)
        assert not w, (html.name, w)


def test_status_tiles_are_counted_from_items(examples):
    s = (examples / "2026-09-15_status.html").read_text()
    tiles = dict(re.findall(r'data-status="(\w+)"><div class="n">(\d+)<', s))
    assert tiles == {"fixed": "6", "open": "1", "wontdo": "1"}


def test_status_has_one_table_per_source(examples):
    s = (examples / "2026-09-15_status.html").read_text()
    assert s.count("<table") == 2
    assert "<h2>Your 10 Sep follow-up (S1–S3)</h2>" in s


def test_changed_rows_are_marked_against_previous_round(examples):
    s = (examples / "2026-09-15_status.html").read_text()
    changed = re.findall(r'<tr class="changed"><td[^>]*>(\w+)', s)
    assert sorted(changed) == ["R3", "R4", "S1", "S2", "S3"]


def test_only_four_statuses(tmp_path):
    with pytest.raises(SystemExit):
        build(tmp_path, {"type": "status", "title": "a b", "sources": [{"name": "s", "items": [{"id": "1", "status": "deferred"}]}]})


def test_text_is_escaped_and_markdown_applied():
    assert report.md("AS < 30 and **bold** `a<b`") == "AS &lt; 30 and <b>bold</b> <code>a&lt;b</code>"
    assert report.md("[x](y.html)") == '<a href="y.html">x</a>'


def test_skeletons_fail_until_filled(tmp_path):
    for t in report.TYPES:
        spec = yaml.safe_load((ROOT / "skills/html-report/skeletons" / f"{t}.yaml").read_text())
        out = build(tmp_path, spec, t)
        assert any("REPLACE" in f for f in fails(out)), t


@pytest.mark.parametrize("inject,expect", [
    ("<style>@media (prefers-color-scheme: dark){}</style>", "dark-mode"),
    ('<script src="https://cdn.example.com/x.js"></script>', "external"),
    ("<p>" + "ACGT" * 12 + "</p>", "DNA"),
])
def test_checker_catches(tmp_path, inject, expect):
    out = build(tmp_path, {"type": "brief", "title": "a short brief"})
    out.write_text(out.read_text().replace("</main>", inject + "</main>"))
    assert any(expect in f for f in fails(out))


def test_checker_catches_hand_edited_tile(tmp_path, examples):
    p = examples / "2026-09-15_status.html"
    p.write_text(p.read_text().replace('data-status="fixed"><div class="n">6<', 'data-status="fixed"><div class="n">7<'))
    assert any("tile 'fixed'" in f for f in fails(p))


def test_privacy_line_required_unless_turned_off(tmp_path):
    out = build(tmp_path, {"type": "brief", "title": "a short brief", "privacy": False})
    assert not fails(out)
    out.write_text(out.read_text().replace('<meta name="html-report-privacy" content="off">', ""))
    assert any("no patient data" in f for f in fails(out))


def test_cli_init_build(tmp_path):
    spec = tmp_path / "s.yaml"
    subprocess.run([sys.executable, SCRIPTS / "report.py", "init", "--type", "brief", "-o", spec], check=True)
    subprocess.run([sys.executable, SCRIPTS / "report.py", "build", spec], check=True)
    r = subprocess.run([sys.executable, SCRIPTS / "check_report.py", tmp_path / "s.html"])
    assert r.returncode == 1  # REPLACE placeholders still there


def test_tabs_render_panels_asks_and_scoped_css(examples):
    s = (examples / "2026-09-19_lab_update.html").read_text()
    assert s.count('class="panel"') == 4
    assert '<label for="tb1-2">2 &middot; Cloud costs</label>' in s
    assert s.count("<h3>What I need from you</h3>") == 2
    assert "#tb1-4:checked~#tb1-p4" in s
    assert "display:block !important" in s  # print shows every panel


def test_nested_tabs_inside_findings(tmp_path):
    inner = {"tabs": [{"label": "Approach", "blocks": [{"p": "a"}]},
                      {"label": "Results", "blocks": [{"p": "b"}]}], "numbered": False}
    out = build(tmp_path, {"type": "findings", "title": "nested tab test",
                           "blocks": [{"tabs": [{"label": "E1", "heading": "E1", "blocks": [inner]},
                                                {"label": "E2", "heading": "E2"}]}]})
    s = out.read_text()
    assert 'id="tb2-p2"' in s and '<label for="tb2-1">Approach</label>' in s
    assert not fails(out)
