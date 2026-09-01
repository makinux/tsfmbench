import os

import numpy as np
import pytest

pytestmark = pytest.mark.slow


def _real_forecaster():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    import torch
    from timesfm import TimesFM3Forecaster

    try:
        return TimesFM3Forecaster.from_pretrained(
            "google/timesfm-3.0-pytorch",
            local_files_only=True,
            device="cuda" if torch.cuda.is_available() else "cpu",
            per_core_batch_size=8,
        )
    except OSError as exc:
        pytest.skip(f"TimesFM checkpoint is not cached: {exc}")


def test_real_timesfm_batch_affine_and_context_metamorphics() -> None:
    model = _real_forecaster()
    x = np.sin(np.arange(2048) / 30.0).astype("float32") + 10
    single = next(model.predict_batch([x], horizon=8, return_quantiles=True))
    mixed = next(model.predict_batch([x, x[::-1]], horizon=8, return_quantiles=True))
    affine = next(model.predict_batch([2 * x + 5], horizon=8, return_quantiles=True))
    short = next(model.predict_batch([x[-1024:]], horizon=8, return_quantiles=True))
    np.testing.assert_allclose(single.forecast, mixed.forecast, rtol=1e-5, atol=1e-5)
    np.testing.assert_allclose(2 * single.forecast + 5, affine.forecast, rtol=1e-4, atol=1e-4)
    assert single.forecast.shape == short.forecast.shape
    assert np.isfinite(short.forecast).all()
    scale = max(1.0, float(np.max(np.abs(single.forecast))))
    assert float(np.mean(np.abs(single.forecast - short.forecast))) < scale
