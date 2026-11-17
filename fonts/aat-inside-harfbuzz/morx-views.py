"""Writes FONT.views.json for this chapter's fonts, for the `table` blocks
in the chapter.

usage: python3 morx-views.py FONT.ttf ...

tools/font-views.py keeps the TTX of a fixed list of tables, which doesn't
include `morx` or `feat`. This script writes the same file in the same
format, with no lookups, and with these tables:

  morx                    the whole `morx` table
  morx chain 0 features   if it has any, an excerpt: the first chain's default flags
                          and feature entries, the lines from <DefaultFlags>
                          to the last </MorphFeature>, as TTX has them
  feat                    the whole `feat` table, if there is one

Like font-views.py, nothing here is written by hand: every view is read
from the compiled font.
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


def chain_features(morx):
    lines = morx.split("\n")
    start = next(i for i, l in enumerate(lines) if "<DefaultFlags " in l)
    end = max(i for i, l in enumerate(lines) if "</MorphFeature>" in l)
    indent = len(lines[start]) - len(lines[start].lstrip())
    return "\n".join(l[indent:] for l in lines[start:end + 1])


def write_views(font_path):
    with open(font_path, "rb") as f:
        data = f.read()
    digest = hashlib.sha256(data).hexdigest()
    morx = font_views.table_view(font_path, "morx")
    tables = {"morx": morx}
    if "</MorphFeature>" in morx:
        tables["morx chain 0 features"] = chain_features(morx)
    if "feat" in TTFont(font_path):
        tables["feat"] = font_views.table_view(font_path, "feat")
    out = os.path.splitext(font_path)[0] + ".views.json"
    with open(out, "w") as f:
        json.dump({"font": os.path.basename(font_path), "sha256": digest,
                   "lookups": {}, "tables": tables}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        write_views(path)
