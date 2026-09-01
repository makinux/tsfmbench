"""Environment smoke test: CUDA availability + TimesFM 3.0 toy forecast.

Verifies the documented API surface before the adapter is built. Run:
    uv run python scripts/smoke_timesfm.py
"""

import sys

import truststore

truststore.inject_into_ssl()  # support TLS-inspecting proxies via the OS trust store

import numpy as np
import torch

print(f"torch {torch.__version__} cuda_available={torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"device: {torch.cuda.get_device_name(0)}")

try:
    import timesfm3
except ImportError as e:
    print(f"import timesfm3 FAILED: {e}")
    import timesfm

    print("timesfm members:", [n for n in dir(timesfm) if not n.startswith("_")])
    sys.exit(1)

print("timesfm3 members:", [n for n in dir(timesfm3) if not n.startswith("_")])

from timesfm3 import ModelConfig, TimesFM3Evaluator

device = "cuda" if torch.cuda.is_available() else "cpu"
cfg = ModelConfig(
    checkpoint_path="google/timesfm-3.0-pytorch",
    per_core_batch_size=4,
    device=device,
)
print("loading checkpoint (first run downloads ~1.3GB)...")
ev = TimesFM3Evaluator(cfg)

rng = np.random.default_rng(0)
ts = np.cumsum(rng.normal(size=512)).astype(np.float32)
outputs = list(ev.predict_batch([ts, ts * 2.0 + 5.0], horizon=16, return_quantiles=True))

print(f"n_outputs={len(outputs)}")
o = outputs[0]
print(f"forecast shape: {o.forecast.shape}")
q = getattr(o, "quantiles", None)
print(f"quantiles shape: {None if q is None else q.shape}")
print(f"forecast head: {np.asarray(o.forecast)[:4]}")
if q is not None:
    qa = np.asarray(q)
    mono = bool(np.all(np.diff(qa, axis=-1) >= -1e-6))
    print(f"quantile monotonicity (axis=-1): {mono}")
if torch.cuda.is_available():
    print(f"max CUDA mem: {torch.cuda.max_memory_allocated() / 1e6:.0f} MB")
print("SMOKE OK")
