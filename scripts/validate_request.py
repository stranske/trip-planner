"""Validate request.json against schema."""

import json
import sys

from jsonschema import ValidationError, validate

SCHEMA = {
    "type": "object",
    "required": ["trip_window", "must_see", "nature_ratio"],
    "properties": {
        "trip_window": {
            "type": "object",
            "required": ["min_weeks", "max_weeks", "months"],
            "properties": {
                "min_weeks": {"type": "number", "minimum": 1},
                "max_weeks": {"type": "number", "maximum": 12},
                "months": {"type": "array", "items": {"type": "string"}},
            },
        },
        "must_see": {"type": "array", "items": {"type": "string"}},
        "nature_ratio": {"type": "number", "minimum": 0, "maximum": 1},
        "complexity_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
        "cost_sensitivity": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def main(path: str = "request.json") -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate(instance=data, schema=SCHEMA)
        print("✓ request.json is valid.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print("✗ request.json cannot be read:", e)
        sys.exit(1)
    except ValidationError as e:
        print("✗ request.json failed schema validation:")
        print("  →", e.message)
        sys.exit(1)


if __name__ == "__main__":
    main()
