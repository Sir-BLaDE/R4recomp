// HDR light (half resolution): the part of each pixel that "spills over" into glow. Lights (points
// clearly brighter than their surroundings: tail lights, headlights, street lamps, neon, the sun)
// are boosted; broad highlights are extended gently. White road markings, bright but with little
// contrast against grey asphalt, stay out (threshold on the peak). Bright sky is kept out of the
// glow: it would bleed over the silhouettes of the buildings and trees cut out against it.
// Alpha: scene luminance (exposure, night and tunnels), averaged by the following downsamples.
void main(){
  vec3 c = texture(u_c, v_uv).rgb;
  float l = max(c.r, max(c.g, c.b));
  float y = dot(c, vec3(0.2126, 0.7152, 0.0722));
  // near (contrast) and far (size) neighbourhood: a light is small and surrounded by dark;
  // a white roof against the sky or a lit wall stays bright all around
  float near = 0.0, bright = 0.0;
  for (int k = 0; k < 8; ++k) {
    float a = 6.2831853 * (float(k) + 0.5) / 8.0;
    vec2 dir = vec2(cos(a) * u_size.y / u_size.x, sin(a));
    // neighbourhood brightness as luminance: an orange wall lit by a lamp is not a lamp
    vec3 v = texture(u_c, v_uv + dir * 0.022).rgb;
    float lv = dot(v, vec3(0.3, 0.55, 0.15)) * 1.2;
    near += lv;
    vec3 w = texture(u_c, v_uv + dir * 0.05).rgb;
    bright += step(0.82, lv) + step(0.82, dot(w, vec3(0.3, 0.55, 0.15)) * 1.2);
  }
  near /= 8.0;
  float small = 1.0 - smoothstep(2.0, 6.0, bright);
  float contrast = smoothstep(0.15, 0.4, l - near) * small;
  // a light's hue: near white (headlights, street lamps, sun), orange (sodium lamps) or pure red
  // (tail lights); not vivid paints (yellow, green) with one component off
  float lo = min(c.r, min(c.g, c.b));
  float red = smoothstep(0.45, 0.7, c.r - max(c.g, c.b)) * smoothstep(0.85, 0.97, c.r);
  // sodium is about (1, 0.7, 0.3); the vivid yellow of paints (1, 0.9, 0.1) is ruled out by blue and green
  float sodium = smoothstep(0.8, 0.95, c.r) * smoothstep(0.35, 0.55, c.g) * (1.0 - smoothstep(0.8, 0.92, c.g))
               * smoothstep(0.12, 0.3, c.b);
  float hue = max(max(smoothstep(0.3, 0.55, lo), red), sodium);
  float point = smoothstep(u_threshold.x, 0.98, l) * contrast * hue;
  // bright sky (bluish or hazy, at the top of the frame): neither diffuse glow nor light
  float sky = smoothstep(-0.04, 0.1, c.b - c.r) * smoothstep(0.45, 0.7, v_uv.y);
  float high = max(y - u_threshold.y, 0.0) / (1.0 - u_threshold.y) * (1.0 - sky);
  vec3 e = c * (point * (1.0 - 0.7 * sky) * u_gain.x + high * high * u_gain.y);
  o = vec4(e, y);
}
