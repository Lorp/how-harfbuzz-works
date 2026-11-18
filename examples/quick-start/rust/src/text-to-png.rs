// Shape a line of text with HarfRust, and draw it as a PNG with Skrifa's
// outlines and tiny-skia's rasterizer.
// usage: text-to-png FONT TEXT PIXELS > out.png
use harfrust::{Buffer, Font, ShapeOptions, ShaperFont};
use skrifa::instance::{LocationRef, Size};
use skrifa::outline::{DrawSettings, OutlinePen};
use skrifa::{FontRef, GlyphId, MetadataProvider};
use std::io::Write;
use tiny_skia::{FillRule, Paint, PathBuilder, Pixmap, Transform};

// A pen that turns outline commands, which are y-up, into a tiny-skia path,
// which is y-down, moved to (x, y) in pixels.
struct Pen { path: PathBuilder, x: f32, y: f32 }

impl OutlinePen for Pen {
    fn move_to(&mut self, x: f32, y: f32) { self.path.move_to(self.x + x, self.y - y) }
    fn line_to(&mut self, x: f32, y: f32) { self.path.line_to(self.x + x, self.y - y) }
    fn quad_to(&mut self, x1: f32, y1: f32, x: f32, y: f32) {
        self.path.quad_to(self.x + x1, self.y - y1, self.x + x, self.y - y)
    }
    fn curve_to(&mut self, x1: f32, y1: f32, x2: f32, y2: f32, x: f32, y: f32) {
        self.path.cubic_to(self.x + x1, self.y - y1, self.x + x2, self.y - y2,
                           self.x + x, self.y - y)
    }
    fn close(&mut self) { self.path.close() }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 4 {
        panic!("usage: text-to-png FONT TEXT PIXELS");
    }
    let font_path = &args[1];
    let text = &args[2];
    let pixels: f32 = args[3].parse().expect("PIXELS must be a number");
    let data = std::fs::read(font_path).expect("can't read the font");

    // Shape, in font units: HarfRust has no font size.
    let font = Font::new(data.clone(), 0).expect("not a font");
    let mut buffer = Buffer::new();
    buffer.push_str(text);
    buffer.guess_segment_properties();
    let shaper_font = ShaperFont::new(&font);
    let options = ShapeOptions::new();
    harfrust::shape(&shaper_font, &mut buffer, options).expect("shaping failed");

    // Font units to pixels.
    let skrifa_font = FontRef::new(&data).expect("not a font");
    let size = Size::new(pixels);
    let scale = pixels / font.units_per_em() as f32;
    let metrics = skrifa_font.metrics(size, LocationRef::default());

    // The image: as wide as the line, as tall as the ascender and descender.
    let mut advance = 0;
    for pos in buffer.glyph_positions() {
        advance += pos.x_advance;
    }
    let width = (advance as f32 * scale).ceil() as u32;
    let height = (metrics.ascent - metrics.descent).ceil() as u32;
    let baseline = metrics.ascent.ceil();

    // One path for the whole line, each glyph drawn at its pen position.
    let outlines = skrifa_font.outline_glyphs();
    let mut pen = Pen { path: PathBuilder::new(), x: 0.0, y: 0.0 };
    let mut x = 0;
    let mut y = 0;
    let infos = buffer.glyph_infos();
    let positions = buffer.glyph_positions();
    for i in 0..infos.len() {
        let glyph_id = GlyphId::new(infos[i].glyph_id);
        let pos = &positions[i];
        pen.x = (x + pos.x_offset) as f32 * scale;
        pen.y = baseline - (y + pos.y_offset) as f32 * scale;
        if let Some(glyph) = outlines.get(glyph_id) {
            let settings = DrawSettings::unhinted(size, LocationRef::default());
            glyph.draw(settings, &mut pen).expect("can't draw");
        }
        x += pos.x_advance;
        y += pos.y_advance;
    }

    // Fill it in black, on a transparent background, and write the PNG.
    let mut pixmap = Pixmap::new(width, height).expect("empty image");
    if let Some(path) = pen.path.finish() {
        let mut paint = Paint::default();
        paint.set_color_rgba8(0, 0, 0, 255);
        let transform = Transform::identity();
        pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
    }
    let png = pixmap.encode_png().expect("can't encode PNG");
    std::io::stdout().write_all(&png).unwrap();
}
