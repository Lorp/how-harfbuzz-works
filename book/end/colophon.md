# Colophon

The text is set in Source Serif 4, the headings in Commissioner, and code in JetBrains Mono.

The pages are built from Markdown by `tools/build-site.mjs`, with markdown-it. Test fonts are compiled from feature files by fontTools, which also makes the views of their tables. Shaping results and traces come from HarfBuzz {{hb}}, built from source by `tools/build-harfbuzz.sh`.

This version: {{version}}. The date and the commit, in the book’s [repository](https://github.com/Lorp/how-harfbuzz-works), say exactly which text this is; “+ changes” means it was built from changes not yet committed. Quote them when reporting a mistake.
