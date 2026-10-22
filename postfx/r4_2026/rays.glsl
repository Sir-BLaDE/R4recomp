// God rays, quarter resolution:
//  - from the projected sun (u_sun), out of the bright sky that the scenery cuts out;
//  - from bright lights (tunnel exits, street lamps, sky at the end of a street), from the
//    camera's vanishing point (u_race.yz), the more so the darker the scene (tunnels, night).
// Scene exposure: average luminance of the smallest downsample (u_m, alpha).
float sky(vec2 p, out vec3 col){
  vec3 c = texture(u_c, p).rgb;
  float l = dot(c, vec3(0.3, 0.55, 0.15));
  float blue = smoothstep(-0.05, 0.12, c.b - c.r);
  float high = smoothstep(0.4, 0.7, p.y);
  col = c;
  return high * blue * smoothstep(0.5, 0.85, l);
}
void main(){
  vec3 acc = vec3(0.0);
  float sun = u_sun.z * u_sun.w;
  if (sun > 0.0) {
    vec2 d = (v_uv - u_sun.xy) / 28.0;
    vec2 p = v_uv; float dec = 1.0;
    for (int k = 0; k < 28; ++k) {
      p -= d;
      vec3 col; float m = sky(p, col);
      acc += col * m * dec * vec3(1.0, 0.92, 0.78);
      dec *= u_decay.x;
    }
    acc *= sun * u_strength.x / 28.0;
  }
  float avg = 0.0;
  for (int k = 0; k < 5; ++k) avg += texture(u_m, vec2(0.2 + 0.15 * float(k), 0.5)).a;
  avg /= 5.0;
  float dark = smoothstep(0.42, 0.12, avg);
  if (u_race.w > 0.0 && dark > 0.01) {
    // only large patches of light cast rays (tunnel exit, sky at the end of a street): a bright
    // point (tail light, headlight, lamp) drew a long dotted straight line across the frame.
    // Extent test: the light must cover four points 2% apart. Start offset by per-pixel noise:
    // no more dotted lines at the sampling steps.
    vec2 f = u_race.yz;
    vec2 d = (v_uv - f) / 24.0;
    vec2 p = v_uv - d * fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
    float dec = 1.0; vec3 a = vec3(0.0);
    const vec2 e = vec2(0.02, 0.0);
    for (int k = 0; k < 24; ++k) {
      p -= d;
      vec3 c = texture(u_c, p).rgb;
      float l = max(c.r, max(c.g, c.b));
      vec4 q = vec4(dot(texture(u_c, p + e.xy).rgb, vec3(0.33)), dot(texture(u_c, p - e.xy).rgb, vec3(0.33)),
                    dot(texture(u_c, p + e.yx * 1.8).rgb, vec3(0.33)), dot(texture(u_c, p - e.yx * 1.8).rgb, vec3(0.33)));
      float extent = smoothstep(0.6, 0.85, min(min(q.x, q.y), min(q.z, q.w)));
      a += c * smoothstep(0.78, 1.0, l) * extent * dec;
      dec *= u_decay.y;
    }
    acc += a / 24.0 * dark * u_strength.y;
  }
  // alpha: scene darkness (eye adaptation, read by the "light" pass)
  o = vec4(acc, dark);
}
