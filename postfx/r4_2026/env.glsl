// Surroundings for the car body reflections (eighth resolution): the frame blurred with a 3x3 tent,
// read by the "reflections" pass as a map of the surroundings (sky at the top, scenery at the horizon).
void main(){
  vec2 d = u_rcp * 1.5;
  vec3 a = texture(u_c, v_uv + vec2(-d.x, d.y)).rgb + texture(u_c, v_uv + vec2(d.x, d.y)).rgb
         + texture(u_c, v_uv + vec2(-d.x, -d.y)).rgb + texture(u_c, v_uv + vec2(d.x, -d.y)).rgb;
  vec3 b = texture(u_c, v_uv + vec2(0.0, d.y)).rgb + texture(u_c, v_uv + vec2(0.0, -d.y)).rgb
         + texture(u_c, v_uv + vec2(d.x, 0.0)).rgb + texture(u_c, v_uv + vec2(-d.x, 0.0)).rgb;
  o = vec4((a + 2.0 * b + 4.0 * texture(u_c, v_uv).rgb) / 16.0, 1.0);
}
