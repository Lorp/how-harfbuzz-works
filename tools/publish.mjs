// Publishes the book to GitHub Pages (https://lorp.github.io/how-harfbuzz-works/).
//
// usage: node tools/publish.mjs [--dirty]   (or: npm run publish)
//
// Commit first: the book carries a version stamp, the date and the commit it
// was built from (tools/version.mjs), and publishing stops if book/,
// examples/, fonts/ or tools/ have uncommitted changes, unless --dirty says to
// publish them as they are (the stamp then says "+ changes").
//
// It makes the PDF if the one in site/print/ wasn't made from exactly this
// commit and these files (npm run pdf: a couple of minutes, with Chrome). It
// builds the site afresh into a scratch folder, so pages since renamed or
// dropped don't linger, adds the PDF and its .pages.txt, and makes that the
// gh-pages branch, as one new commit with no history, pushed with --force.
// Only the latest version is kept, so old PDFs don't pile up in the
// repository. Nothing in the working tree is changed but site/print/.

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { RECORD, sourceHash } from "./source-hash.mjs";
import { bookVersion } from "./version.mjs";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const BRANCH = "gh-pages";
const PDF = ["how-harfbuzz-works.pdf", "how-harfbuzz-works.pages.txt"];

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { cwd: ROOT, encoding: "utf8", stdio: ["ignore", "pipe", "inherit"], ...opts });
  if (r.status !== 0) { console.error(`publish: ${cmd} ${args.join(" ")} failed`); process.exit(1); }
  return (r.stdout ?? "").trim();
}

const version = bookVersion(ROOT);
if (version.changes && !process.argv.includes("--dirty")) {
  console.error("publish: book/, examples/, fonts/ or tools/ have uncommitted changes. Commit them first,\n" +
                "or publish them as they are with npm run publish -- --dirty (the version will say “+ changes”).");
  process.exit(1);
}

// The PDF, made again unless it was made from exactly this commit and these files.
const print = path.join(ROOT, "site", "print");
let made = null;
try { made = JSON.parse(fs.readFileSync(path.join(ROOT, RECORD), "utf8")); } catch { /* none, or the old format */ }
if (!fs.existsSync(path.join(print, PDF[0])) || !made || made.commit !== version.commit || made.source !== sourceHash(ROOT)) {
  console.log(`publish: making the PDF for ${version.stamp}`);
  run(process.execPath, [path.join(ROOT, "tools", "build-pdf.mjs")], { stdio: ["ignore", "ignore", "inherit"] });
}

const work = fs.mkdtempSync(path.join(os.tmpdir(), "hb-book-publish-"));
const out = path.join(work, "site");

run(process.execPath, [path.join(ROOT, "tools", "build-site.mjs"), out], { stdio: ["ignore", "ignore", "inherit"] });

fs.mkdirSync(path.join(out, "print"), { recursive: true });
for (const f of PDF) {
  const from = path.join(print, f);
  if (fs.existsSync(from)) fs.copyFileSync(from, path.join(out, "print", f));
  else console.warn(`publish: no site/print/${f} (run npm run pdf), so it's left out`);
}
// Served as they are, not through Jekyll.
fs.writeFileSync(path.join(out, ".nojekyll"), "");

// The commit is made from a scratch index, so the working tree, the index and
// the checked-out branch are left alone.
const env = { ...process.env, GIT_INDEX_FILE: path.join(work, "index") };
run("git", ["--work-tree", out, "add", "--all", "--force", "."], { env });
const tree = run("git", ["write-tree"], { env });
const commit = run("git", ["commit-tree", tree, "-m", `Publish the book: ${version.label}`]);
run("git", ["push", "--force", "origin", `${commit}:refs/heads/${BRANCH}`], { stdio: ["ignore", "inherit", "inherit"] });

fs.rmSync(work, { recursive: true, force: true });
console.log(`publish: ${version.label}; ${BRANCH} is now ${commit.slice(0, 7)}; https://lorp.github.io/how-harfbuzz-works/ updates in a minute or two`);
