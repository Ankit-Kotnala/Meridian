"""ASGI entry point for the CareerOS API process."""

from careeros_api.application import create_app

__all__ = ["app", "create_app"]


app = create_app()
