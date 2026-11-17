// What the PDF is made from, as one hash: every file in book/, fonts/ and
// tools/ (but not the publishing scripts), by path and content (not date,
// which git checkouts change). The PDF build records it in
// .cache/pdf-source.txt; publishing compares it with the current one, to
// warn when the PDF is out of date.

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export const RECORD = ".cache/pdf-source.txt";

export function sourceHash(root) {
  const hash = crypto.createHash("sha256");
  for (const dir of ["book", "fonts", "tools"]) {
    const files = fs.readdirSync(path.join(root, dir), { recursive: true })
      .filter((f) => !f.split(path.sep).includes("__pycache__") && !f.endsWith(".DS_Store"))
      .filter((f) => !(dir === "tools" && ["publish.mjs", "source-hash.mjs"].includes(f)))
      .map((f) => path.join(dir, f))
      .filter((f) => fs.statSync(path.join(root, f)).isFile())
      .sort();
    for (const f of files) hash.update(f + "\0").update(fs.readFileSync(path.join(root, f))).update("\0");
  }
  return hash.digest("hex");
}
