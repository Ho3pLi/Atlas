"""Safe, local configuration diagnostics: python -m atlas.test."""


def main():
    from atlas.config import validate_config

    result = validate_config()
    for feature, enabled in result["feature_flags"].items():
        print(f"{feature}: {'enabled' if enabled else 'disabled'}")
    return bool(result["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
