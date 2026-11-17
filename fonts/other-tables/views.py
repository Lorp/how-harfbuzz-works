"""Writes FONT.views.json for this chapter's fonts, with the TTX of the
tables the chapter's `table` blocks show.

usage: python3 views.py FONT.ttf ...

tools/font-views.py keeps the TTX of a fixed list of tables, which has MATH
and STAT but not BASE, name, ltag or meta. This script writes the same file
in the same format, with no lookups and with whichever of those tables the
font has. As in font-views.py, every view is read from the compiled font.
"""
import hashlib
import importlib.util
import json
import os
import sys

from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "font_views", os.path.join(HERE, "..", "..", "tools", "font-views.py"))
font_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font_views)

TABLES = ["MATH", "BASE", "STAT", "name", "ltag", "meta"]


def write_views(font_path):
    with open(font_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    font = TTFont(font_path)
    tables = {tag: font_views.table_view(font_path, tag) for tag in TABLES if tag in font}
    out = os.path.splitext(font_path)[0] + ".views.json"
    with open(out, "w") as f:
        json.dump({"font": os.path.basename(font_path), "sha256": digest,
                   "lookups": {}, "tables": tables}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        write_views(path)
