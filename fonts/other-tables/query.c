/* Queries this chapter's fonts through HarfBuzz API calls that no HarfBuzz
 * utility exposes: the MATH API, BASE min/max extents, and the name table by
 * language. The chapter quotes its output; it isn't run when the book is built.
 *
 * usage: cc query.c -I$HB/src -I$HB/build/src -L$HB/build/src -lharfbuzz \
 *          -Wl,-rpath,$HB/build/src -o query && ./query .
 *        (HB is .cache/harfbuzz, built by tools/build-harfbuzz.sh)
 */
#include <hb.h>
#include <hb-ot.h>
#include <stdio.h>
#include <stdlib.h>
static hb_font_t *open_font(const char *p){hb_blob_t*b=hb_blob_create_from_file(p);hb_face_t*f=hb_face_create(b,0);return hb_font_create(f);}
static unsigned gid(hb_font_t*f,const char*n){hb_codepoint_t g;hb_font_get_glyph_from_name(f,n,-1,&g);return g;}
int main(int argc,char**argv){
  const char*D=argv[1]; char p[1024];
  /* MATH, at the default scale and then at twice it */
  snprintf(p,sizeof p,"%s/math.ttf",D); hb_font_t*m=open_font(p);
  printf("has math %d\n",hb_ot_math_has_data(hb_font_get_face(m)));
  int cs[]={HB_OT_MATH_CONSTANT_SCRIPT_PERCENT_SCALE_DOWN,HB_OT_MATH_CONSTANT_AXIS_HEIGHT,HB_OT_MATH_CONSTANT_DELIMITED_SUB_FORMULA_MIN_HEIGHT,HB_OT_MATH_CONSTANT_DISPLAY_OPERATOR_MIN_HEIGHT,HB_OT_MATH_CONSTANT_RADICAL_DEGREE_BOTTOM_RAISE_PERCENT,HB_OT_MATH_CONSTANT_FRACTION_RULE_THICKNESS};
  for(int s=0;s<2;s++){ if(s) hb_font_set_scale(m,2000,2000);
  for(unsigned i=0;i<6;i++)printf("const %d = %d\n",cs[i],hb_ot_math_get_constant(m,cs[i]));
  printf("ic f %d x %d\n",hb_ot_math_get_glyph_italics_correction(m,gid(m,"f")),hb_ot_math_get_glyph_italics_correction(m,gid(m,"x")));
  printf("ta a %d x %d\n",hb_ot_math_get_glyph_top_accent_attachment(m,gid(m,"a")),hb_ot_math_get_glyph_top_accent_attachment(m,gid(m,"x")));
  for(int h=0;h<=900;h+=150)printf("kern f TR h=%d -> %d\n",h,hb_ot_math_get_glyph_kerning(m,gid(m,"f"),HB_OT_MATH_KERN_TOP_RIGHT,h));
  hb_ot_math_kern_entry_t ke[4];unsigned kn=4;unsigned kt=hb_ot_math_get_glyph_kernings(m,gid(m,"f"),HB_OT_MATH_KERN_TOP_RIGHT,0,&kn,ke);
  for(unsigned i=0;i<kn;i++)printf(" entry %d %d\n",ke[i].max_correction_height,ke[i].kern_value);
  printf("ext size1 %d paren %d\n",hb_ot_math_is_glyph_extended_shape(hb_font_get_face(m),gid(m,"parenleft.size1")),hb_ot_math_is_glyph_extended_shape(hb_font_get_face(m),gid(m,"parenleft")));
  hb_direction_t dirs[]={HB_DIRECTION_TTB,HB_DIRECTION_BTT,HB_DIRECTION_LTR};
  for(int d=0;d<3;d++){hb_ot_math_glyph_variant_t v[4];unsigned n=4;unsigned t=hb_ot_math_get_glyph_variants(m,gid(m,"parenleft"),dirs[d],0,&n,v);
   printf("dir %d variants %u:",d,t);for(unsigned i=0;i<n;i++)printf(" %u/%d",v[i].glyph,v[i].advance);printf("\n");
   hb_ot_math_glyph_part_t pa[4];unsigned pn=4;hb_position_t ic;unsigned pt=hb_ot_math_get_glyph_assembly(m,gid(m,"parenleft"),dirs[d],0,&pn,pa,&ic);
   printf(" parts %u:",pt);for(unsigned i=0;i<pn;i++)printf(" g%u s%d e%d f%d fl%d",pa[i].glyph,pa[i].start_connector_length,pa[i].end_connector_length,pa[i].full_advance,pa[i].flags);printf(" overlap %d\n",hb_ot_math_get_min_connector_overlap(m,dirs[d]));}
  }
  snprintf(p,sizeof p,"%s/base.ttf",D); hb_font_t*b=open_font(p);
  const char*langs[]={"en","vi",NULL};
  for(int i=0;i<3;i++){hb_font_extents_t e;int r=hb_ot_layout_get_font_extents2(b,HB_DIRECTION_LTR,HB_SCRIPT_LATIN,langs[i]?hb_language_from_string(langs[i],-1):NULL,&e);printf("extents latn %s r=%d %d %d %d\n",langs[i]?langs[i]:"null",r,e.ascender,e.descender,e.line_gap);}
  {hb_font_extents_t e;int r=hb_ot_layout_get_font_extents2(b,HB_DIRECTION_LTR,HB_SCRIPT_DEVANAGARI,NULL,&e);printf("extents deva r=%d %d %d %d\n",r,e.ascender,e.descender,e.line_gap);}
  hb_tag_t st[4],lt[4];unsigned sc=4,lc=4;hb_ot_tags_from_script_and_language(HB_SCRIPT_DEVANAGARI,hb_language_from_string("hi",-1),&sc,st,&lc,lt);
  for(unsigned i=0;i<sc;i++)printf("tag %c%c%c%c\n",HB_UNTAG(st[i]));
  printf("tag for script deva %c%c%c%c\n",HB_UNTAG(hb_ot_layout_get_horizontal_baseline_tag_for_script(HB_SCRIPT_DEVANAGARI)));
  snprintf(p,sizeof p,"%s/names.ttf",D); hb_font_t*n=open_font(p); hb_face_t*nf=hb_font_get_face(n);
  unsigned cnt;const hb_ot_name_entry_t*en=hb_ot_name_list_names(nf,&cnt);
  for(unsigned i=0;i<cnt;i++)printf("name %u %s\n",en[i].name_id,hb_language_to_string(en[i].language));
  const char*ls[]={"en","en-GB","en-US","de-AT","de","ja","ga","fr",NULL};
  for(int i=0;i<9;i++){char buf[100];unsigned l=100;hb_ot_name_get_utf8(nf,1,ls[i]?hb_language_from_string(ls[i],-1):HB_LANGUAGE_INVALID,&l,buf);printf("name1 %s: %s\n",ls[i]?ls[i]:"invalid",buf);}
  {char buf[100];unsigned l=100;hb_ot_name_get_utf8(nf,256,NULL,&l,buf);printf("256: %s\n",buf);}
  {char buf[4];unsigned l=4;unsigned t=hb_ot_name_get_utf8(nf,1,NULL,&l,buf);printf("trunc: %u %u '%s'\n",t,l,buf);}
  {uint16_t buf[100];unsigned l=100;unsigned t=hb_ot_name_get_utf16(nf,1,hb_language_from_string("ja",-1),&l,buf);printf("utf16 ja: %u\n",t);}
  return 0;}
