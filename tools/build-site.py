"""Builds the book as HTML pages: one page per Markdown file in book/toc.txt.

usage: python3 tools/build-site.py [OUT_DIR] [--fragment]   (default: site/)

--fragment leaves out <!doctype>, <html>, <head> and <body>, for hosts
that supply their own.

Needs HB_BUILD (or .cache/harfbuzz/, made by tools/build-harfbuzz.sh): the
HarfBuzz source, with build/ and build-msg/ beside it. Every shaping result
and trace in the book is made here by running that hb-shape, so the text
can't drift from what HarfBuzz does.

Besides ordinary Markdown, a chapter can hold three kinds of fenced block,
all run against the chapter's fonts in fonts/<chapter>/:

  ```views                 the switchable views of one lookup
  font: ligatures.ttf
  lookup: 0
  fea: ligatures.fea liga  (the feature file and block it came from)
  cpp: LigatureSubstFormat1_2
  ```

  ```shape                 one hb-shape run per line: font, text, options,
  ligatures.ttf  ffi       separated by two or more spaces; \\uXXXX in the
  ligatures.ttf  ffi  --features=-liga                text is decoded
  ```

  ```trace                 hb-shape --trace, cut down to the lines between
  font: ligatures.ttf      `from` and `to` (substrings of the trace lines),
  text: f\\u0301i           and without skipped lookups unless `skipped: yes`
  from: start lookup 0
  to: end lookup 0
  ```
"""
import html
import json
import os
import re
import subprocess
import sys

import markdown

sys.path.insert(0, os.path.dirname(__file__))
import views  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HB_TAG = "15.1.0"
HB_BUILD = os.environ.get("HB_BUILD", os.path.join(ROOT, ".cache", "harfbuzz"))
HB_SHAPE = os.path.join(HB_BUILD, "build", "util", "hb-shape")
HB_SHAPE_MSG = os.path.join(HB_BUILD, "build-msg", "util", "hb-shape")

VIEW_LABELS = [("spec", "Spec-like"), ("fea", "Feature file"), ("ttx", "TTX"),
               ("hex", "Bytes"), ("cpp", "HarfBuzz C++")]


def decode(text):
    return re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), text)


def codepoints(text):
    return " ".join(f"U+{ord(c):04X}" for c in text)


def shown(text):
    """The text as a reader should see it: marks on a dotted circle, and
    invisible characters by name."""
    names = {"‍": "⟨ZWJ⟩", "‌": "⟨ZWNJ⟩", " ": "␣"}
    out = ""
    for c in text:
        if c in names:
            out += names[c]
        elif 0x300 <= ord(c) < 0x370:
            out += "◌" + c
        else:
            out += c
    return out


def parse_fields(body):
    fields = {}
    for line in body.strip().split("\n"):
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    return fields


def block_views(body, fonts):
    f = parse_fields(body)
    font = os.path.join(fonts, f["font"])
    idx = int(f["lookup"])
    panes = {"spec": views.spec_view(font, idx), "ttx": views.ttx_view(font, idx)}
    if "fea" in f:
        fea, name = f["fea"].split()
        panes["fea"] = views.fea_view(os.path.join(fonts, fea), name)
    try:
        panes["hex"] = views.hex_view(font, idx)
    except NotImplementedError:
        pass
    cpp_ref = ""
    if "cpp" in f:
        code, rel, line, url = views.cpp_view(os.path.join(HB_BUILD, "src"), f["cpp"], HB_TAG)
        panes["cpp"] = code
        cpp_ref = (f'<a class="src" href="{url}">{html.escape(rel)}:{line}</a>')
    tabs, bodies = [], []
    for key, label in VIEW_LABELS:
        if key not in panes:
            continue
        tabs.append(f'<button type="button" role="tab" data-view="{key}">{label}</button>')
        extra = cpp_ref if key == "cpp" else ""
        bodies.append(f'<div class="pane" data-view="{key}" role="tabpanel">'
                      f'<pre><code>{html.escape(panes[key])}</code></pre>{extra}</div>')
    caption = f'{html.escape(f["font"])}, lookup {idx}'
    return (f'<figure class="views"><div class="tabs" role="tablist" aria-label="Views of {caption}">'
            f'{"".join(tabs)}</div>{"".join(bodies)}'
            f'<figcaption>{caption}</figcaption></figure>')


def run_shape(font, text, opts, msg=False):
    exe = HB_SHAPE_MSG if msg else HB_SHAPE
    r = subprocess.run([exe, font, text] + opts, capture_output=True, text=True, check=True)
    return (r.stderr + r.stdout).strip() if msg else r.stdout.strip()


def block_shape(body, fonts):
    rows = []
    for line in body.strip().split("\n"):
        parts = re.split(r"\s{2,}", line.strip())
        font, text, opts = parts[0], decode(parts[1]), parts[2:]
        out = run_shape(os.path.join(fonts, font), text, opts)
        opt_text = " ".join(opts)
        rows.append(
            "<tr>"
            f'<td class="font">{html.escape(font)}</td>'
            f'<td class="in"><span class="txt">{html.escape(shown(text))}</span>'
            f'<span class="cps">{codepoints(text)}</span></td>'
            f'<td class="opt">{html.escape(opt_text)}</td>'
            f'<td class="out"><code>{html.escape(out)}</code></td>'
            "</tr>")
    return ('<div class="shape"><table><thead><tr><th>Font</th><th>Text</th>'
            '<th>Options</th><th>hb-shape output</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def block_trace(body, fonts):
    f = parse_fields(body)
    text = decode(f["text"])
    opts = f.get("options", "").split()
    out = run_shape(os.path.join(fonts, f["font"]), text, opts + ["--trace"], msg=True)
    lines = [l.removeprefix("trace: ") for l in out.split("\n") if l.startswith("trace: ")]
    if "from" in f:
        lines = lines[next(i for i, l in enumerate(lines) if f["from"] in l):]
    if "to" in f:
        lines = lines[:next(i for i, l in enumerate(lines) if f["to"] in l) + 1]
    if f.get("skipped") != "yes":
        drop = set()
        for i, l in enumerate(lines):
            if "skipped lookup" in l:
                drop |= {i - 1, i, i + 1}
        lines = [l for i, l in enumerate(lines) if i not in drop]
    rows = []
    for l in lines:
        what, _, buf = l.partition("\tbuffer: ")
        rows.append(f'<tr><td class="what">{html.escape(what)}</td>'
                    f'<td class="buf"><code>{html.escape(buf)}</code></td></tr>')
    head = (f'<div class="trace-head"><code>hb-shape {html.escape(f["font"])} '
            f'"{html.escape(shown(text))}" {html.escape(" ".join(opts))} --trace</code></div>')
    return f'<div class="trace">{head}<table><tbody>{"".join(rows)}</tbody></table></div>'


BLOCKS = {"views": block_views, "shape": block_shape, "trace": block_trace}


def render(md_text, fonts):
    placeholders = {}

    def stash(m):
        key = f"@@BLOCK{len(placeholders)}@@"
        placeholders[key] = BLOCKS[m.group(1)](m.group(2), fonts)
        return f"\n\n{key}\n\n"

    md_text = re.sub(r"^```(views|shape|trace)\n(.*?)^```\s*$", stash, md_text,
                     flags=re.S | re.M)
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc", "attr_list"],
                             extension_configs={"toc": {"permalink": False}})
    body = body.replace("{{hb}}", HB_TAG)
    for key, value in placeholders.items():
        body = body.replace(f"<p>{key}</p>", value)
    return body


def main(out_dir, fragment=False):
    os.makedirs(out_dir, exist_ok=True)
    template = open(os.path.join(ROOT, "tools", "page.html")).read()
    toc = [l.strip() for l in open(os.path.join(ROOT, "book", "toc.txt"))
           if l.strip() and not l.startswith("#")]
    meta = json.load(open(os.path.join(ROOT, "book", "book.json")))
    pages = []
    for entry in toc:
        src = open(os.path.join(ROOT, "book", entry)).read()
        title = re.search(r"^# (.+)$", src, re.M).group(1)
        slug = os.path.splitext(os.path.basename(entry))[0]
        pages.append((entry, slug, title, src))
    nav = "".join(f'<li><a href="{s}.html">{html.escape(t)}</a></li>' for _, s, t, _ in pages)
    for n, (entry, slug, title, src) in enumerate(pages):
        fonts = os.path.join(ROOT, "fonts", slug)
        body = render(src, fonts)
        prev_link = (f'<a rel="prev" href="{pages[n-1][1]}.html">← {html.escape(pages[n-1][2])}</a>'
                     if n else "<span></span>")
        next_link = (f'<a rel="next" href="{pages[n+1][1]}.html">{html.escape(pages[n+1][2])} →</a>'
                     if n + 1 < len(pages) else "<span></span>")
        page = (template.replace("{{title}}", html.escape(title))
                .replace("{{book}}", html.escape(meta["title"]))
                .replace("{{subtitle}}", html.escape(meta["subtitle"]))
                .replace("{{hb_version}}", HB_TAG)
                .replace("{{nav}}", nav)
                .replace("{{prev}}", prev_link).replace("{{next}}", next_link)
                .replace("{{body}}", body))
        if not fragment:
            page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                    + page.replace("<div class=\"page\">", "</head>\n<body>\n<div class=\"page\">", 1)
                    + "\n</body>\n</html>\n")
        open(os.path.join(out_dir, f"{slug}.html"), "w").write(page)
        print(f"{slug}.html")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else os.path.join(ROOT, "site"), "--fragment" in sys.argv)
