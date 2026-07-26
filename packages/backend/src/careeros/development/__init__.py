"""Explicitly local development tooling.

Nothing in this package is imported by a delivery application at runtime.
Each command must enforce its own fail-closed environment guard before any I/O.
"""
