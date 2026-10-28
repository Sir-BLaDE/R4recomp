"""ESRGAN-family 4x upscaling through spandrel (the model loader chaiNNer
uses), CPU. Models are .pth files the user supplies (e.g. Real-ESRGAN
RealESRGAN_x4plus_anime_6B.pth, BSD-3-Clause, from the Real-ESRGAN releases).

    up = Esrgan("RealESRGAN_x4plus_anime_6B.pth")
    big = up.rgb(pil_rgb)          # 4x RGB
"""
import numpy as np
import torch
from PIL import Image
from spandrel import ModelLoader

torch.set_num_threads(max(1, torch.get_num_threads()))


class Esrgan:
    def __init__(self, path, tile=192, pad=12):
        self.model = ModelLoader().load_from_file(path).eval()
        self.scale = self.model.scale
        self.tile, self.pad = tile, pad

    @torch.inference_mode()
    def _run(self, a):
        """a: HxWx3 float32 0..1 -> (H*s)x(W*s)x3, tiled with overlap."""
        h, w, _ = a.shape
        s, t, p = self.scale, self.tile, self.pad
        out = np.zeros((h * s, w * s, 3), np.float32)
        for y0 in range(0, h, t):
            for x0 in range(0, w, t):
                y1, x1 = min(h, y0 + t), min(w, x0 + t)
                ya, xa = max(0, y0 - p), max(0, x0 - p)
                yb, xb = min(h, y1 + p), min(w, x1 + p)
                blk = torch.from_numpy(np.ascontiguousarray(
                    a[ya:yb, xa:xb].transpose(2, 0, 1)))[None]
                r = self.model(blk)[0].clamp(0, 1).numpy().transpose(1, 2, 0)
                out[y0 * s:y1 * s, x0 * s:x1 * s] = r[(y0 - ya) * s:(y0 - ya + y1 - y0) * s,
                                                      (x0 - xa) * s:(x0 - xa + x1 - x0) * s]
        return out

    def rgb(self, im):
        a = np.asarray(im.convert("RGB"), np.float32) / 255.0
        # edge-replicate a small border so the network sees no false frame
        b = 4
        a = np.pad(a, ((b, b), (b, b), (0, 0)), mode="edge")
        r = self._run(a)
        s = self.scale
        r = r[b * s:-b * s, b * s:-b * s]
        return Image.fromarray(np.clip(r * 255 + 0.5, 0, 255).astype(np.uint8), "RGB")
