"""leadscrub: multi-pass lead list cleaning for outbound sales."""

__version__ = "0.1.0"

from .config import Config, load_config
from .io import read_table
from .pipeline import Scrubber, ScrubResult

__all__ = ["Config", "ScrubResult", "Scrubber", "__version__", "load_config", "read_table"]
