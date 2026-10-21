// Quarter resolution: anamorphic streaks of bright lights (horizontal, slightly blue), light
// reflections on the road (vertical trails under each light, stronger at night and in tunnels)
// and light trails at high speed (from the vanishing point, with the previous frame's
// persistence). u_e: lights (first downsample).
void main(){
  vec3 st = vec3(0.0);
  for (int k = 1; k <= 18; ++k) {
    vec2 d = vec2(u_rcp.x * float(k) * 2.5, 0.0);
    vec3 a = texture(u_e, v_uv + d).rgb + texture(u_e, v_uv - d).rgb;
    st += max(a - u_k.w, vec3(0.0)) * exp(-float(k) / 6.0);
  }
  st *= vec3(0.75, 0.85, 1.15) * u_k.x / 10.0;

  float avg = 0.0;
  for (int k = 0; k < 5; ++k) avg += texture(u_m, vec2(0.2 + 0.15 * float(k), 0.5)).a;
  avg /= 5.0;
  float dark = smoothstep(0.45, 0.12, avg);
  vec3 c = texture(u_c, v_uv).rgb;
  float y = dot(c, vec3(0.3, 0.55, 0.15));
  float sat = max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b));
  float road = (1.0 - smoothstep(0.1, 0.25, sat)) * (1.0 - smoothstep(0.4, 0.65, y))
             * smoothstep(0.02, 0.08, u_race.z - v_uv.y) * u_race.w;
  // reflection: the light above, spread wider with distance (wet, rough asphalt)
  vec3 re = vec3(0.0); float ws = 0.0;
  for (int k = 1; k <= 16; ++k) {
    float w = exp(-float(k) / 7.0);
    float lx = u_rcp.x * (1.0 + float(k) * 0.35);
    vec2 p = v_uv + vec2(0.0, float(k) * 0.011);
    re += (texture(u_e, p).rgb * 0.5 + (texture(u_e, p + vec2(lx, 0.0)).rgb +
           texture(u_e, p - vec2(lx, 0.0)).rgb) * 0.25) * w;
    ws += w;
  }
  re = re / ws * road * (0.35 + 1.4 * dark) * u_k.y;

  float v = clamp(u_race.x, 0.0, 1.0) * u_race.w;
  vec2 f = u_race.yz;
  vec2 d = v_uv - f;
  vec3 tr = vec3(0.0); float wt = 0.0;
  for (int k = 0; k < 10; ++k) {
    float t = float(k) / 9.0;
    float w = 1.0 - 0.8 * t;
    tr += texture(u_e, f + d * (1.0 - 0.3 * v * t)).rgb * w;
    wt += w;
  }
  tr = tr / wt * v * u_k.z;
  vec3 h = texture(u_h, v_uv).rgb * 0.45 * v;
  o = vec4(max(st * (0.15 + 0.85 * dark) * u_race.w + re + tr, h), 1.0);
}
