// Final composite (full resolution):
//  - light added in linear space, with an exponential shoulder (a frame with no added light is
//    output unchanged, no loss of whites);
//  - sun lens flare when the sun is on screen and the sky around it is clear;
//  - subtle grading: S-curve contrast, vibrance, cool shadows and warm highlights, vignette.
// u_grade: contrast, vibrance, split toning, vignette.
float sky(vec2 p){
  vec3 c = texture(u_c, p).rgb;
  float l = dot(c, vec3(0.3, 0.55, 0.15));
  return smoothstep(-0.05, 0.12, c.b - c.r) * smoothstep(0.5, 0.85, l);
}
void main(){
  ivec2 px = ivec2(gl_FragCoord.xy) - u_org;
  vec3 c = texelFetch(u_c, px, 0).rgb;
  vec3 L = texture(u_l, v_uv).rgb;
  float on = u_sun.z * u_sun.w * u_flare;
  vec2 s = u_sun.xy;
  if (on > 0.0 && s.x > -0.05 && s.x < 1.05 && s.y > -0.05 && s.y < 1.05) {
    float vis = 0.0;
    for (int k = 0; k < 9; ++k)
      vis += sky(s + vec2(float(k % 3 - 1), float(k / 3 - 1)) * 0.015);
    vis /= 9.0;
    vec2 asp = vec2(u_size.x / u_size.y, 1.0);
    vec2 ax = vec2(0.5) - s;
    const float ts[6] = float[](0.35, 0.7, 1.0, 1.25, 1.55, 1.9);
    const float rs[6] = float[](0.02, 0.045, 0.012, 0.07, 0.03, 0.11);
    const vec3 cs[6] = vec3[](vec3(1.0, 0.6, 0.3), vec3(0.4, 0.8, 1.0), vec3(1.0, 0.95, 0.7),
                              vec3(0.5, 1.0, 0.6), vec3(0.9, 0.5, 1.0), vec3(0.4, 0.6, 1.0));
    vec3 fl = vec3(0.0);
    for (int k = 0; k < 6; ++k) {
      float dd = length((v_uv - (s + ax * ts[k])) * asp);
      fl += cs[k] * (1.0 - smoothstep(rs[k] * 0.55, rs[k], dd)) * 0.07;
    }
    vec2 ds = (v_uv - s) * asp;
    float r = length(ds);
    float star = pow(abs(ds.x * ds.y) * 900.0 + 1.0, -1.5);
    fl += vec3(1.0, 0.93, 0.82) * (exp(-r * r * 400.0) * 0.9 + exp(-r * 6.0) * 0.18 + star * exp(-r * 4.0) * 0.5);
    L += fl * vis * on;
  }
  vec3 lin = c * c;
  vec3 add = L * L + L * 0.6;
  lin = 1.0 - (1.0 - lin) * exp(-add);
  c = sqrt(max(lin, 0.0));
  // grading
  float y = dot(c, vec3(0.2126, 0.7152, 0.0722));
  float sat = max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b));
  c = mix(vec3(y), c, 1.0 + u_grade.y * (1.0 - sat));
  c = mix(c, c * c * (3.0 - 2.0 * c), u_grade.x);
  c += u_grade.z * (vec3(-0.02, 0.0, 0.03) * (1.0 - y) + vec3(0.03, 0.01, -0.03) * y);
  vec2 q = (v_uv - 0.5) * vec2(1.0, 0.8);
  c *= 1.0 - u_grade.w * pow(dot(q, q) * 2.2, 1.6);
  o = vec4(clamp(c, 0.0, 1.0), 1.0);
}
