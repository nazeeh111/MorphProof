"""MORPHPROOF: empirical compatibility evidence for code transformations."""
__version__ = "0.1.0"


def verify(*args, **kwargs):
    """Compare a candidate with a frozen reference. See morphproof.oracle.verify."""
    from .oracle import verify as run
    return run(*args, **kwargs)


def transform(*args, **kwargs):
    """Translate a supported numeric Python module into a Rust extension."""
    from .transform import transform as run
    return run(*args, **kwargs)
