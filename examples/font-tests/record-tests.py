"""Record what HarfBuzz does with a font now, as lines of a .tests file.

usage: python3 record-tests.py HB-SHAPE FONT CASES > FONT.tests

CASES has one case per line: the text, then, after a tab, any hb-shape
options for it (--language=en, --features=-liga ...). Each output line is
one test in the format of HarfBuzz's own test/shape suite: the font, the
options, the text as code points, and the result hb-shape gives today.
Keep the .tests file beside the font: the font is named without a folder.

Needs only Python 3 and hb-shape.
"""
import os
import subprocess
import sys


def main(hb_shape, font, cases):
    env = dict(os.environ, LC_ALL="C")  # as run-tests.py runs it
    with open(cases, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            text, _, options = line.partition("\t")
            unicodes = ",".join(f"U+{ord(c):04X}" for c in text)
            result = subprocess.run(
                [hb_shape, font, "--unicodes", unicodes, *options.split()],
                capture_output=True, text=True, env=env, check=True,
            ).stdout.strip()
            print(f"{os.path.basename(font)};{options};{unicodes};{result}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
