"""Create local demo credentials without replacing the user's Gemini settings."""

from pathlib import Path
import secrets


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / ".env"
    existing = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    additions = []
    for key in ("CORTEX_OPERATOR_KEY", "CORTEX_REVIEWER_KEY"):
        if not any(
            line.strip().startswith(key + "=") for line in existing.splitlines()
        ):
            additions.append(f"{key}={secrets.token_urlsafe(32)}")
    if additions:
        with path.open("a", encoding="utf-8") as stream:
            stream.write("\n" + "\n".join(additions) + "\n")
    ignore = root / ".gitignore"
    ignore_text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    entries = (".env", ".venv/", "backend/data/", "__pycache__/")
    missing = [entry for entry in entries if entry not in ignore_text.splitlines()]
    if missing:
        with ignore.open("a", encoding="utf-8") as stream:
            stream.write("\n" + "\n".join(missing) + "\n")
    print(
        "Local operator/reviewer settings are ready. Existing settings were preserved."
    )
    print("Keep .env private. Keys are not printed by this script.")


if __name__ == "__main__":
    main()
