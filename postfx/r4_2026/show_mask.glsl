// Tuning view: the frame darkened, overlaid with what the "hdr" pass keeps as light (red: light
// points, green: broad highlights).
void main(){
  ivec2 px = ivec2(gl_FragCoord.xy) - u_org;
  vec3 c = texelFetch(u_c, px, 0).rgb;
  vec4 e = texture(u_e, v_uv);
  o = vec4(c * 0.35 + e.rgb * 0.6, 1.0);
}
