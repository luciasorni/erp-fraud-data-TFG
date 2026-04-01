"""Valida variables de entorno requeridas por perfil."""

from __future__ import annotations

import argparse
import os
import sys


REQUIRED_BY_PROFILE: dict[str, tuple[str, ...]] = {
    "pre_langsmith": (),
    "langsmith": ("LANGSMITH_API_KEY", "LANGSMITH_PROJECT"),
    "cloud": ("AWS_REGION",),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        default="pre_langsmith",
        choices=sorted(REQUIRED_BY_PROFILE.keys()),
    )
    args = parser.parse_args(argv)

    required = REQUIRED_BY_PROFILE[args.profile]
    missing = [key for key in required if not str(os.getenv(key, "")).strip()]
    if missing:
        print(
            f"ERROR: faltan variables para perfil={args.profile}: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    print(f"OK env validation profile={args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
