__version__ = "0.1.0"

try:
    from .engine import Engine, build_index_fast  
except Exception:
    pass
