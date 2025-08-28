#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file.

Usage:
  python scripts/export_openapi.py [--out docs/openapi.json]

This does not start the server; it instantiates the app and dumps its schema.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mind_swarm.server.api import MindSwarmServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema")
    parser.add_argument(
        "--out",
        default="docs/openapi.json",
        help="Output file path (default: docs/openapi.json)",
    )
    args = parser.parse_args()

    server = MindSwarmServer()
    schema = server.app.openapi()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(schema, indent=2))
    print(f"Wrote OpenAPI schema to {out_path}")


if __name__ == "__main__":
    main()

