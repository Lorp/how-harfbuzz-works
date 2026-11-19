// Shape a line of text with HarfRust and print the glyphs, as hb-shape does.
// usage: text-to-glyphs FONT TEXT
use harfrust::{Buffer, Font, GlyphId, ShapeOptions, ShaperFont};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        panic!("usage: text-to-glyphs FONT TEXT");
    }
    let font_path = &args[1];
    let text = &args[2];
    let data = std::fs::read(font_path).expect("can't read the font");

    // Shape: characters in, positioned glyphs out, in font units.
    let font = Font::new(data, 0).expect("not a font");
    let mut buffer = Buffer::new();
    buffer.push_str(text);
    buffer.guess_segment_properties(); // script, language, direction
    let shaper_font = ShaperFont::new(&font);
    let options = ShapeOptions::new();
    harfrust::shape(&shaper_font, &mut buffer, options).expect("shaping failed");

    // Print each glyph: name=cluster, @offset if it has one, +advance.
    let infos = buffer.glyph_infos();
    let positions = buffer.glyph_positions();
    let mut glyphs = Vec::new();
    for i in 0..infos.len() {
        let pos = &positions[i];
        let name = match shaper_font.glyph_name(GlyphId::new(infos[i].glyph_id)) {
            Some(name) => name.to_string(),
            None => format!("gid{}", infos[i].glyph_id),
        };
        let mut glyph = format!("{}={}", name, infos[i].cluster);
        if pos.x_offset != 0 || pos.y_offset != 0 {
            glyph += &format!("@{},{}", pos.x_offset, pos.y_offset);
        }
        glyph += &format!("+{}", pos.x_advance);
        glyphs.push(glyph);
    }
    println!("[{}]", glyphs.join("|"));
}
