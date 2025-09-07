from contextlib import contextmanager
from time import perf_counter
import logging


@contextmanager
def timed(stage: str):
    t0 = perf_counter()
    try:
        yield
    finally:
        dt = (perf_counter() - t0) * 1000.0
        logging.info(f"[timing] {stage} ms={dt:.1f}")


