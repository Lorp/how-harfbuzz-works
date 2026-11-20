# Foreword

For twenty years, what happened in HarfBuzz stayed in HarfBuzz.

Not by design. Every line of production code I have written is Open Source. HarfBuzz has been there all along for anyone to read. But open is not the same as read, and I should know; HarfBuzz began with things I couldn’t read.

In 1999 it was Persian on the internet. Netscape couldn’t draw it at all. Internet Explorer 5 had just become the first browser that could. But the fonts that came with Windows drew one letter wrong: the medial form of the Persian *yeh*. This was a decade before webfonts were widely used. A page wouldn’t bring its own font. It got whatever was on the reader’s machine. The font was Microsoft’s, and so was the engine. We were not allowed to fix either.

That same year, when I was seventeen, a friend and mentor handed me a printout of the Unicode Bidirectional Algorithm to take home for the [Norouz](https://en.wikipedia.org/wiki/Nowruz) holidays. It was nineteen pages long. I made many attempts at reading it and couldn’t make any sense of it. Then we found a rough Open Source implementation called FriBidi. That, I could read. I could also fix it. So I did, until it matched the specification, and I learned C in the process. I have worked on software I am allowed to fix ever since.

Even before that, it was Persian on the PC. I grew up in the family print shop, in a small town in northern Iran. My father, uncle, and grandfather worked the presses. My mother and her sister practiced Persian Nastaliq calligraphy. Letterforms were part of my family’s everyday life. In 1991, when I was nine, an IBM PC came home, bought by my father to typeset Persian magazines. My brother and I taught ourselves BASIC on it, and then Pascal. We wanted to draw Persian text in Pascal’s graphics mode, and there was no easy way. So we wrote our own Arabic joining. It was my first “shaper,” though the word probably didn’t have that meaning yet.

In high school, I worked on FarsiTeX, because I wanted to typeset Persian poetry. Donald Knuth had given TeX to the world, and written the books that explain it. So I was allowed to fix it, and I could learn how. I made FarsiTeX do what I needed. I never got to typeset the poetry.

HarfBuzz grew out of that same personal itch I have been scratching for way too long. I built HarfBuzz so that the next child in a print shop, in a small town, in a third-world country, can typeset in their own language as much as they want. Nobody should need permission to fix their own letter.

The itch is a common one. Khaled Hosny is HarfBuzz’s maintainer today, while I remain its primary developer. He was a radiologist who wanted a good Arabic Naskh font. Jonathan Kew and I made HarfBuzz what it is over many weeklong hackfests. Many, many others came along in between, and the credits at the back of this book name some of them. For all of us, it has been a labor of love.

When I tell people that I work on putting text on screens in every language, they ask: “Isn’t that, like, done?” I tell them I’m the one doing it. And software is never done. I declared HarfBuzz complete in July 2015 and released version 1.0.0. As of this writing, this book describes version 15.1.0. And there is still no good general solution for typesetting Nastaliq, the hand my mother and my aunt wrote, in HarfBuzz or in any other major shaper. That is why my job is *still* not done.

Which brings me back to reading. HarfBuzz is written in a style of C++ which is loved by some and hated by many, partly because there was no book like this. The first reader to go through all of that code was not a person. This book was drafted by Claude, an AI. Laurence Penney planned it, directed it, and reviewed it. It is developed in the open on [GitHub](https://github.com/Lorp/how-harfbuzz-works), and readers have already sent pull requests.

I came to AI as a skeptic with evidence. Early last year, what it wrote for me was not acceptable in any sense. This year I haven’t written a line of code by hand. I didn’t write this foreword by hand either. I gave Claude my notes, an old essay and some tweets, and argued with it over every sentence. This year will go down in history as a turning point in how software is built. Fascinating time to be alive.

I first met Laurence at ATypI 2014 in Barcelona, or at TYPO Labs 2016 in Berlin, our memories differ. One of us has a bug. What we agree on is a long conversation in Berlin about the design of variable fonts. He has amazed me with his inventions many, many times since. [Samsa](https://lorp.github.io/samsa/src/samsa-gui.html) was one. This book is the latest. A book that runs every one of its examples each time it is revised, so that it can’t quietly go out of date, is his kind of idea. The book was not a day old when he came to me with sixty-five bug reports that its first draft had turned up. I hadn’t read a page of it yet. Most were legitimate bugs, if small ones. I fixed those, and the book records the fixes. There will be many more. Those, I am allowed to fix.

It is a long book. Nobody is expected to read it from end to end, and I haven’t either. What I have read is more meticulous than any documentation one person could write. It cites the line, and it runs the example. If you make fonts, it tells you why HarfBuzz did what it did to yours. If you write software, it is the map of the source that I never drew. Read it with a grain of salt, of the November 2026 kind. Where the book and the code disagree, one of them has a bug, and Laurence and I want to hear about it.

I couldn’t fix that letter in 1999. Today anyone can fix HarfBuzz. With this book, anyone can first read how it works.

*Behdad Esfahbod, with Claude*  
*Edmonton, Alberta*  
*November 2026*
