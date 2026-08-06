"""ASGI entry point for the Rezumi API process."""

from rezumi_api.application import create_app

__all__ = ["app", "create_app"]


app = create_app()
