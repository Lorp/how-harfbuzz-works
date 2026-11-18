// The book's own version, as the site and the PDF show it: the edition from
// book/book.json ("Draft"), and a stamp of the date and the git commit the
// book was built from, such as "18 November 2026 · 30688e6".
//
// With nothing uncommitted in the book's sources (book/, examples/, fonts/,
// tools/), the date is the commit's, so the same commit always gives the same
// stamp. Otherwise it is today's, and the stamp says "+ changes": the files
// built from aren't exactly any commit.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export const SOURCE_DIRS = ["book", "examples", "fonts", "tools"];

function git(root, args) {
  const r = spawnSync("git", args, { cwd: root, encoding: "utf8" });
  if (r.status !== 0) throw new Error(`git ${args.join(" ")} failed:\n${r.stderr}`);
  return r.stdout.trim();
}

const longDate = (d) => d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

export function bookVersion(root) {
  const meta = JSON.parse(fs.readFileSync(path.join(root, "book", "book.json"), "utf8"));
  const full = git(root, ["rev-parse", "HEAD"]);
  const commit = full.slice(0, 7);
  const changes = git(root, ["status", "--porcelain", "--", ...SOURCE_DIRS]) !== "";
  const date = longDate(changes ? new Date() : new Date(git(root, ["log", "-1", "--format=%cI"])));
  const stamp = `${date} · ${commit}${changes ? " + changes" : ""}`;
  return {
    edition: meta.edition || "Draft",
    commit, full, changes, date, stamp,
    label: `${meta.edition || "Draft"}, ${stamp}`,
    url: `${meta.repository}/commit/${full}`,
  };
}
