// Upsample: this level plus the lower level (already accumulated) filtered with a 3x3 tent. The
// final glow thus adds wider and wider radii (sharp core, very soft halo).
vec3 tent(vec2 uv){
  vec2 d = u_rcp * u_radius;
  vec3 a = texture(u_b, uv + vec2(-d.x, d.y)).rgb + texture(u_b, uv + vec2(d.x, d.y)).rgb
         + texture(u_b, uv + vec2(-d.x, -d.y)).rgb + texture(u_b, uv + vec2(d.x, -d.y)).rgb;
  vec3 b = texture(u_b, uv + vec2(0.0, d.y)).rgb + texture(u_b, uv + vec2(0.0, -d.y)).rgb
         + texture(u_b, uv + vec2(d.x, 0.0)).rgb + texture(u_b, uv + vec2(-d.x, 0.0)).rgb;
  return (a + 2.0 * b + 4.0 * texture(u_b, uv).rgb) / 16.0;
}
void main(){
  o = vec4(texture(u_e, v_uv).rgb + tent(v_uv) * u_weight, 1.0);
}
