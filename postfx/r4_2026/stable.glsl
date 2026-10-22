// Temporal stabilization of the light (half resolution). Lights detected on a game frame whose
// vertices jump by one native pixel (x7 on screen) appear and vanish from frame to frame: the glow
// flickers. Blend with this pass's previous frame (u_h):
//  - light: u_k.x of the current frame, more at high speed (u_race.x) so it does not smear;
//  - exposure (alpha, scene luminance): slow (u_k.y), like an eye adapting; without it the night
//    glow (up to 4x the daytime one) would follow every change in the frame.
void main(){
  vec4 e = texture(u_e, v_uv);
  vec4 h = texture(u_h, v_uv);
  // empty or invalid history (first pass, size change): the current frame
  if (any(isnan(h)) || h.a <= 0.0) { o = e; return; }
  float k = mix(u_k.x, 0.8, clamp(u_race.x, 0.0, 1.0));
  o = vec4(mix(h.rgb, e.rgb, k), mix(h.a, e.a, u_k.y));
}
