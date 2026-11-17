# Foreword

The first time a font of mine shaped wrongly, I spent a week sure that the fault was in the font. I rewrote the feature file twice, reordered the lookups, renamed every glyph I could find, and the ligature still refused to form. The fault was in the font, as it turned out, but not anywhere I had looked: a mark class that I’d never thought of as having anything to do with ligatures. What I needed that week was not a better feature file. It was someone to tell me what the shaping engine actually did, step by step, with my glyphs in its hands.

For most of the history of digital type, nobody could. The engines that turned characters into glyphs were closed, and what we knew about them came from specifications, which say what a font may contain, and from experiment, which says what one engine did on one day. The specifications are careful documents, but they leave a great deal to the implementer, and the implementers didn’t write down what they chose.

HarfBuzz changed that, though it took most of us a while to notice. Its source is open, so the answer to almost every question about shaping is now written down somewhere. The difficulty is that it’s written down in C++, spread across a few hundred files, and organized for the people who maintain it rather than for the people who make fonts.

This book does the reading for us. It doesn’t ask you to take its word for anything. It names the version it describes, points to the line of code behind each claim, and runs every example on HarfBuzz itself when the book is built. When it says a ligature forms, you are looking at HarfBuzz forming it.

I wish I’d had it that week. I expect I’ll keep it open the next time a font of mine misbehaves, which, fonts being what they are, will be soon.

*Blabla Estragon*
