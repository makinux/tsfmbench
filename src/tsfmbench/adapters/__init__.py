"""Forecasting adapters implementing the Stage 3 batch contract."""

from tsfmbench.adapters.base import Adapter, TaskContext
from tsfmbench.adapters.dvol import DVOLRegression
from tsfmbench.adapters.ewma import EWMA
from tsfmbench.adapters.garch import GARCH, GJRGARCH
from tsfmbench.adapters.har import HARRV
from tsfmbench.adapters.ml import LightGBMGlobal
from tsfmbench.adapters.naive import NaivePrev, RandomWalk, SeasonalMedian4, SeasonalNaive7
from tsfmbench.adapters.prophet_ import Prophet
from tsfmbench.adapters.stats import AutoETSAdapter, AutoThetaAdapter
from tsfmbench.adapters.timesfm3 import TimesFM3

__all__ = [
    "EWMA",
    "GARCH",
    "GJRGARCH",
    "HARRV",
    "Adapter",
    "AutoETSAdapter",
    "AutoThetaAdapter",
    "DVOLRegression",
    "LightGBMGlobal",
    "NaivePrev",
    "Prophet",
    "RandomWalk",
    "SeasonalMedian4",
    "SeasonalNaive7",
    "TaskContext",
    "TimesFM3",
]
