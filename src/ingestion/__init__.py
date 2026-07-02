"""Ingestion pipeline package."""

__all__ = ["DocumentIngester"]


def __getattr__(name):
    if name == "DocumentIngester":
        from .pipeline import DocumentIngester

        return DocumentIngester
    raise AttributeError(name)
