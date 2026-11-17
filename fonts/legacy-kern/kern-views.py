"""Writes FONT.views.json for this chapter's fonts, with the TTX of their
`kern` table, for the `table` blocks in the chapter.

usage: python3 kern-views.py FONT.ttf ...

tools/font-views.py keeps the TTX of a fixed list of tables, which doesn't
include `kern`, and the views of GSUB lookups, which these fonts don't
have. This script writes the same file in the same format, with no lookups
and with the `kern` table. Like font-views.py, nothing here is written by
hand: the view is read from the compiled font.
"""
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "font_views", os.path.join(HERE, "..", "..", "tools", "font-views.py"))
font_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font_views)


def write_views(font_path):
    with open(font_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    tables = {"kern": font_views.table_view(font_path, "kern")}
    out = os.path.splitext(font_path)[0] + ".views.json"
    with open(out, "w") as f:
        json.dump({"font": os.path.basename(font_path), "sha256": digest,
                   "lookups": {}, "tables": tables}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        write_views(path)
