// Publishes the book to GitHub Pages (https://lorp.github.io/how-harfbuzz-works/).
//
// usage: node tools/publish.mjs   (or: npm run publish)
//
// It builds the site afresh into a scratch folder, so pages since renamed or
// dropped don't linger, adds the PDF and its .pages.txt from site/print/ (made
// by npm run pdf, which isn't rerun here: it's slow and needs Chrome), and
// makes that the gh-pages branch, as one new commit with no history, pushed
// with --force. Only the latest version is kept, so old PDFs don't pile up in
// the repository. Nothing in site/ or the working tree is changed.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { RECORD, sourceHash } from "./source-hash.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BRANCH = "gh-pages";
const PDF = ["how-harfbuzz-works.pdf", "how-harfbuzz-works.pages.txt"];

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"], ...opts });
  if (r.status !== 0) { console.error(`publish: ${cmd} ${args.join(" ")} failed`); process.exit(1); }
  return (r.stdout ?? "").trim();
}

const work = fs.mkdtempSync(path.join(os.tmpdir(), "hb-book-publish-"));
const out = path.join(work, "site");

run(process.execPath, [path.join(ROOT, "tools", "build-site.mjs"), out], { stdio: ["ignore", "ignore", "inherit"] });

const print = path.join(ROOT, "site", "print");
fs.mkdirSync(path.join(out, "print"), { recursive: true });
for (const f of PDF) {
  const from = path.join(print, f);
  if (fs.existsSync(from)) fs.copyFileSync(from, path.join(out, "print", f));
  else console.warn(`publish: no site/print/${f} (run npm run pdf), so it's left out`);
}
// A reminder when the PDF wasn't made from the book as it is now.
if (fs.existsSync(path.join(print, PDF[0]))) {
  const record = path.join(ROOT, RECORD);
  const made = fs.existsSync(record) ? fs.readFileSync(record, "utf8").trim() : null;
  if (made !== sourceHash(ROOT)) {
    console.warn(made ? "publish: the book has changed since the PDF was made, so it's out of date (npm run pdf, then publish again)"
      : "publish: can't tell whether the PDF is up to date, as it was made before that was recorded (npm run pdf to be sure)");
  }
}
// Served as they are, not through Jekyll.
fs.writeFileSync(path.join(out, ".nojekyll"), "");

// The commit is made from a scratch index, so the working tree, the index and
// the checked-out branch are left alone.
const env = { ...process.env, GIT_INDEX_FILE: path.join(work, "index") };
run("git", ["--work-tree", out, "add", "--all", "--force", "."], { env });
const tree = run("git", ["write-tree"], { env });
const source = run("git", ["rev-parse", "--short", "HEAD"]);
const dirty = run("git", ["status", "--porcelain"]) ? " (with uncommitted changes)" : "";
const commit = run("git", ["commit-tree", tree, "-m", `Publish the book, built from ${source}${dirty}`]);
run("git", ["push", "--force", "origin", `${commit}:refs/heads/${BRANCH}`], { stdio: ["ignore", "inherit", "inherit"] });

fs.rmSync(work, { recursive: true, force: true });
console.log(`publish: ${BRANCH} is now ${commit.slice(0, 7)}; https://lorp.github.io/how-harfbuzz-works/ updates in a minute or two`);
