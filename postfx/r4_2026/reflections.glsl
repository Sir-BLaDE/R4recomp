// Reflections on the player's car body (full resolution). The PS1 only draws a matte paint. The
// followed car is not in the PGXP depth (its vertices are computed outside the tracked GTE path),
// so its shape is an analytic volume (rounded body and cabin, in meters in the car frame) placed
// where the game puts the car. Each pixel's ray is cast against this volume (signed distance
// march): on a hit the pixel gets a clear coat:
//  - volume normal (smooth: reflections glide over the body as on real paint);
//  - Fresnel (Schlick): little head-on, mirror-like at grazing angles (roof, rear window, flanks);
//  - reflection of the surroundings (u_env, blurred frame): sky at the top of the frame for a
//    rising ray, horizon scenery for a level ray, road below;
//  - highlight of the dominant light (sun, u_vl).
// Tyres and sills are left out; the volume's edges are softened.
// Live values (src/mods/r4_car_effects.cpp): u_vo car origin in camera space (w: active),
// u_vr, u_vu, u_vf right, up and forward axes; u_vp projection centre (ofx + margin, ofy),
// focal length H, view width (320 + 2 margins); u_vl light direction (w: strength).
// u_k: clear-coat strength, highlight, head-on reflectance (F0), tuning (1: volume silhouette).
float box(vec3 p, vec3 b, float r){
  vec3 q = abs(p) - b + r;
  return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r;
}
float smin(float a, float b, float k){
  float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
  return mix(b, a, h) - k * h * (1.0 - h);
}
// car frame in meters: x right, y up, z forward; fitted in the lab on the player's car standing
// still (orbit camera): wheel bottoms -0.37, sills -0.27, belt line 0.42, roof 0.84; rear face
// -0.66, front about 3.5; half width 0.88; the cabin narrower and shorter than its base
float car(vec3 p){
  float body = box(p - vec3(0.0, 0.075, 1.42), vec3(0.88, 0.345, 2.08), 0.18);
  vec3 h = p - vec3(0.0, 0.6, 1.0);
  float e = max(h.y + 0.24, 0.0);
  float cabin = box(vec3(h.x * (1.0 + 0.4 * e), h.y, h.z * (1.0 + 0.9 * e)), vec3(0.7, 0.24, 1.0), 0.2);
  return smin(body, cabin, 0.1) + 0.04;   // inset by 4 cm: the coat stays on the paint
}
vec3 normal(vec3 p){
  const vec2 e = vec2(0.01, -0.01);
  return normalize(e.xyy * car(p + e.xyy) + e.yyx * car(p + e.yyx)
                 + e.yxy * car(p + e.yxy) + e.xxx * car(p + e.xxx));
}
void main(){
  ivec2 px = ivec2(gl_FragCoord.xy) - u_org;
  vec3 c = texelFetch(u_c, px, 0).rgb;
  o = vec4(c, 1.0);
  if (u_vo.w < 0.5) return;
  // the pixel's ray, in the car frame (meters)
  vec3 dc = normalize(vec3(v_uv.x * u_vp.w - u_vp.x, (1.0 - v_uv.y) * 240.0 - u_vp.y, u_vp.z));
  const float m = 4.0 / 125.0;
  vec3 ro = -vec3(dot(u_vo.xyz, u_vr.xyz), dot(u_vo.xyz, u_vu.xyz), dot(u_vo.xyz, u_vf.xyz)) * m;
  vec3 rd = vec3(dot(dc, u_vr.xyz), dot(dc, u_vu.xyz), dot(dc, u_vf.xyz));
  // entry into and exit from the bounding box
  vec3 bmin = vec3(-1.0, -0.4, -0.9), bmax = vec3(1.0, 0.95, 3.7);
  vec3 inv = 1.0 / rd;
  vec3 t0 = (bmin - ro) * inv, t1 = (bmax - ro) * inv;
  float ta = max(max(min(t0.x, t1.x), min(t0.y, t1.y)), min(t0.z, t1.z));
  float tb = min(min(max(t0.x, t1.x), max(t0.y, t1.y)), max(t0.z, t1.z));
  if (tb < max(ta, 0.0)) return;
  float t = max(ta, 0.0), dmin = 1e3, d = 1e3;
  for (int i = 0; i < 48 && t < tb; ++i) {
    d = car(ro + rd * t);
    dmin = min(dmin, d / t);
    if (d < 0.002) break;
    t += d;
  }
  // soft edge: angular distance to the volume relative to the size of a pixel
  float pixel = 1.5 / (u_vp.z * u_size.y / 240.0);
  float hit = d < 0.002 ? 1.0 : 1.0 - smoothstep(0.0, pixel, dmin);
  if (hit <= 0.0) return;
  vec3 p = ro + rd * t;
  if (u_k.w > 0.5) { vec3 n0 = normal(p); o = vec4(mix(c, 0.5 + 0.5 * n0, 0.6 * hit), 1.0); return; }
  vec3 N = normal(p);
  // tyres and sills: the paint stops above the wheels
  float low = 1.0 - smoothstep(-0.2, -0.08, p.y);
  // at the silhouette (normal nearly perpendicular to the view), the volume and the real car no
  // longer match exactly: coat attenuated
  float k = hit * (1.0 - 0.85 * low) * smoothstep(0.08, 0.3, dot(N, -rd));

  // directions in the car frame: the view, the reflected ray, the light
  vec3 R = reflect(rd, N);
  float cv = clamp(dot(N, -rd), 0.0, 1.0);
  float F = u_k.z + (1.0 - u_k.z) * pow(1.0 - cv, 5.0);
  // surroundings, like a lacquer: above the horizon the sky (top of the blurred frame, along the
  // reflected ray's bearing), below it the darkened ground; the sharp horizon line gliding over the
  // flanks is what makes a car body shine
  vec3 Rc = R.x * u_vr.xyz + R.y * u_vu.xyz + R.z * u_vf.xyz;
  float rise = R.y;
  float hz = 1.0 - u_vp.y / 240.0;
  float ex = clamp(0.5 + 0.45 * Rc.x / (abs(Rc.z) + 0.5), 0.03, 0.97);
  vec3 sky = texture(u_env, vec2(ex, mix(0.8, 0.95, clamp(rise, 0.0, 1.0)))).rgb;
  // a ray sent backwards (towards the camera): what it would see is not on screen; rather than a
  // specific object of the frame (the start gantry showed up as an orange blot on the boot), the
  // average hue of the horizon
  float hy = clamp(hz + 0.04, 0.05, 0.95);
  vec3 wide = (texture(u_env, vec2(0.15, hy)).rgb + texture(u_env, vec2(0.5, hy)).rgb
             + texture(u_env, vec2(0.85, hy)).rgb) / 3.0;
  vec3 scenery = mix(texture(u_env, vec2(ex, hy)).rgb, wide, smoothstep(0.1, -0.4, Rc.z));
  // ground: read on the sides of the frame (in the centre, at the bottom, is the car itself, its lights)
  float sy = clamp(hz - 0.3, 0.03, 0.95);
  vec3 ground = (texture(u_env, vec2(0.1, sy)).rgb + texture(u_env, vec2(0.9, sy)).rgb) * 0.225;
  vec3 env = rise >= 0.0 ? mix(scenery, sky * 1.15, smoothstep(0.0, 0.25, rise))
                         : mix(scenery * 0.6, ground, smoothstep(0.0, 0.08, -rise));
  // highlight: the dominant light on the coat, broad (a sharp highlight drew lines on the volume's
  // curves, absent from the real body)
  vec3 Lc = normalize(u_vl.xyz);
  vec3 L = vec3(dot(Lc, u_vr.xyz), dot(Lc, u_vu.xyz), dot(Lc, u_vf.xyz));
  float rl = max(dot(R, L), 0.0);
  vec3 glint = vec3(1.0, 0.95, 0.85) * (pow(rl, 24.0) * 0.45 + pow(rl, 6.0) * 0.08) * u_vl.w * u_k.y;
  vec3 r = mix(c, env, clamp(F * u_k.x, 0.0, 1.0)) + glint * (0.3 + 0.7 * F);
  o = vec4(mix(c, r, k), 1.0);
}
