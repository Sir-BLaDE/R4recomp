// Added light (quarter resolution): multi-scale glow (this level + the accumulated lower levels),
// rays, streaks, reflections and trails.
vec3 tent(vec2 uv){
  vec2 d = u_rcp;
  vec3 a = texture(u_b, uv + vec2(-d.x, d.y)).rgb + texture(u_b, uv + vec2(d.x, d.y)).rgb
         + texture(u_b, uv + vec2(-d.x, -d.y)).rgb + texture(u_b, uv + vec2(d.x, -d.y)).rgb;
  vec3 b = texture(u_b, uv + vec2(0.0, d.y)).rgb + texture(u_b, uv + vec2(0.0, -d.y)).rgb
         + texture(u_b, uv + vec2(d.x, 0.0)).rgb + texture(u_b, uv + vec2(-d.x, 0.0)).rgb;
  return (a + 2.0 * b + 4.0 * texture(u_b, uv).rgb) / 16.0;
}
void main(){
  // outside a race (menus, native HD screens): reduced glow, text does not bleed
  vec3 glow = (texture(u_e, v_uv).rgb + tent(v_uv)) * 0.25 * mix(0.35, 1.0, u_race.w);
  // adaptation: light glow by day (u_k.x); in the dark (tunnel, night) the open eye sees lights
  // and openings onto daylight glow much more (u_k.w)
  vec4 r = texture(u_r, v_uv);
  glow *= mix(u_k.x, u_k.w, r.a * u_race.w);
  o = vec4(glow + r.rgb * u_k.y + texture(u_s, v_uv).rgb * u_k.z, 1.0);
}
