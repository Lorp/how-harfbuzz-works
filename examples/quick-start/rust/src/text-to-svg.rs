// Shape a line of text with HarfRust and draw it as SVG with Skrifa.
// usage: text-to-svg FONT TEXT > out.svg
use harfrust::{Buffer, Font, ShapeOptions, ShaperFont};
use skrifa::instance::{LocationRef, Size};
use skrifa::outline::{pen::SvgPen, DrawSettings};
use skrifa::{FontRef, GlyphId, MetadataProvider};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        panic!("usage: text-to-svg FONT TEXT");
    }
    let font_path = &args[1];
    let text = &args[2];
    let data = std::fs::read(font_path).expect("can't read the font");

    // Shape: characters in, positioned glyphs out, in font units.
    let font = Font::new(data.clone(), 0).expect("not a font");
    let mut buffer = Buffer::new();
    buffer.push_str(text);
    buffer.guess_segment_properties(); // script, language, direction
    let shaper_font = ShaperFont::new(&font);
    let options = ShapeOptions::new();
    harfrust::shape(&shaper_font, &mut buffer, options).expect("shaping failed");

    // Draw each glyph's outline as an SVG path at its pen position.
    let skrifa_font = FontRef::new(&data).expect("not a font");
    let outlines = skrifa_font.outline_glyphs();
    let mut x = 0;
    let mut y = 0;
    let mut paths = String::new();
    let infos = buffer.glyph_infos();
    let positions = buffer.glyph_positions();
    for i in 0..infos.len() {
        let glyph_id = GlyphId::new(infos[i].glyph_id);
        let pos = &positions[i];
        let mut pen = SvgPen::new();
        if let Some(glyph) = outlines.get(glyph_id) {
            let size = Size::unscaled(); // font units
            let settings = DrawSettings::unhinted(size, LocationRef::default());
            glyph.draw(settings, &mut pen).expect("can't draw");
        }
        paths += &format!(
            "<path transform=\"translate({},{})\" d=\"{}\"/>\n",
            x + pos.x_offset, y + pos.y_offset, pen
        );
        x += pos.x_advance;
        y += pos.y_advance;
    }

    // The box: the line's advance, and the font's ascender and descender.
    let metrics = skrifa_font.metrics(Size::unscaled(), LocationRef::default());
    let top = metrics.ascent;
    let bottom = metrics.descent;
    println!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 {} {} {}\">",
        -top, x, top - bottom
    );
    print!("<g transform=\"scale(1,-1)\">\n{paths}</g>\n</svg>\n");
}
