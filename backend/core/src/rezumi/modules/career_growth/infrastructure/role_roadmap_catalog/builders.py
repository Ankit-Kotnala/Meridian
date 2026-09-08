"""Tiny helpers for assembling role-roadmap documents."""

from __future__ import annotations

from typing import Any


def skill(name: str, why: str, how_to_start: str) -> dict[str, str]:
    return {"name": name, "why": why, "howToStart": how_to_start}


def stage(name: str, skills: list[dict[str, str]]) -> dict[str, Any]:
    return {"stage": name, "skills": skills}


def role(
    slug: str,
    title: str,
    stages: list[dict[str, Any]],
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "roleSlug": slug,
        "title": title,
        "stages": stages,
    }
    if aliases:
        document["aliases"] = aliases
    return document
