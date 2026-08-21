"""Export the FastAPI schema deterministically and optionally check drift."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic_settings import PydanticBaseSettingsSource
from rezumi_api.application import create_app
from rezumi_api.config import Settings

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "openapi" / "rezumi.openapi.json"


class _SchemaSettings(Settings):
    """Validate explicit defaults without consulting ambient configuration sources."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[Settings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del cls, settings_cls, env_settings, dotenv_settings, file_secret_settings
        return (init_settings,)


def render_schema() -> str:
    """Return a stable, reviewable representation of the current API schema."""
    default_values: dict[str, Any] = {
        name: field.get_default(call_default_factory=True)
        for name, field in Settings.model_fields.items()
    }
    default_values["environment"] = "test"
    app = create_app(_SchemaSettings(**default_values))
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when the committed schema is stale",
    )
    args = parser.parse_args()
    rendered = render_schema()

    if args.check:
        if not SCHEMA_PATH.exists() or SCHEMA_PATH.read_text(encoding="utf-8") != rendered:
            parser.error("OpenAPI drift detected; run the contract generation command")
        return 0

    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Exported {SCHEMA_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
