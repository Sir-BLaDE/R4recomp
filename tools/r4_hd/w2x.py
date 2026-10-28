#!/usr/bin/env python3
"""Minimal numpy implementation of waifu2x's upconv_7 network (MIT,
nagadomi/waifu2x, models/upconv_7/art/*.json) for 2x upscaling of 2D art.

    from w2x import Upconv7
    up = Upconv7("scale2.0x_model.json")
    out = up.scale2x(rgb)          # float32 HxWx3 in [0,1] -> 2Hx2Wx3

The network: six valid 3x3 convolutions (leaky ReLU 0.1) and one 4x4
stride-2 transposed convolution (padding 3). Input is padded by 7 px
(edge replicate) so the output covers the whole image.
"""
import json
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


class Upconv7:
    def __init__(self, path):
        layers = json.load(open(path))
        self.convs = []
        for l in layers[:-1]:
            w = np.asarray(l["weight"], np.float32)            # out,in,3,3
            b = np.asarray(l["bias"], np.float32)
            # -> (in*3*3, out) for im2col matmul, order (ky,kx,in)
            wm = w.transpose(2, 3, 1, 0).reshape(-1, w.shape[0])
            self.convs.append((wm, b))
        d = layers[-1]
        self.dw = np.asarray(d["weight"], np.float32)          # in,out,4,4
        self.db = np.asarray(d["bias"], np.float32)

    @staticmethod
    def _conv(x, wm, b):
        # x: H,W,C -> valid 3x3
        win = sliding_window_view(x, (3, 3), axis=(0, 1))     # H-2,W-2,C,3,3
        win = win.transpose(0, 1, 3, 4, 2)                     # H-2,W-2,3,3,C
        h, w = win.shape[:2]
        y = win.reshape(h * w, -1) @ wm + b
        y = np.where(y > 0, y, 0.1 * y)
        return y.reshape(h, w, -1)

    def _deconv(self, x):
        # transposed conv, kernel 4, stride 2, padding 3
        H, W, C = x.shape
        k = 4
        out_c = self.dw.shape[1]
        full = np.zeros(((H - 1) * 2 + k, (W - 1) * 2 + k, out_c), np.float32)
        wk = self.dw.reshape(C, out_c * k * k)                 # in, (out,ky,kx)
        contrib = (x.reshape(H * W, C) @ wk).reshape(H, W, out_c, k, k)
        for ky in range(k):
            for kx in range(k):
                full[ky:ky + 2 * H:2, kx:kx + 2 * W:2, :] += contrib[:, :, :, ky, kx]
        p = 3
        return full[p:full.shape[0] - p, p:full.shape[1] - p, :] + self.db

    def scale2x(self, rgb, tile=96):
        """rgb float32 HxWx3 in [0,1]; processed in tiles to bound memory."""
        H, W, _ = rgb.shape
        pad = 7
        src = np.pad(rgb, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        out = np.zeros((H * 2, W * 2, 3), np.float32)
        for ty in range(0, H, tile):
            for tx in range(0, W, tile):
                th, tw = min(tile, H - ty), min(tile, W - tx)
                x = src[ty:ty + th + 2 * pad, tx:tx + tw + 2 * pad]
                for wm, b in self.convs:
                    x = self._conv(x, wm, b)
                y = self._deconv(x)
                out[ty * 2:ty * 2 + th * 2, tx * 2:tx * 2 + tw * 2] = y[:th * 2, :tw * 2]
        return np.clip(out, 0, 1)
