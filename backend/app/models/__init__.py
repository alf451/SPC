from app.models import audit, core, daq, gage, spc  # noqa: F401  (registra tutte le tabelle su Base.metadata)

__all__ = ["core", "spc", "daq", "gage", "audit"]
