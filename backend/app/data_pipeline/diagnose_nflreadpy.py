import inspect

from app.data_sources.nflverse_client import NFLVerseClient


def main() -> None:
    client = NFLVerseClient()
    if not client.available:
        print("nflreadpy is not installed in this Python environment.")
        return

    import nflreadpy

    print(f"nflreadpy version: {getattr(nflreadpy, '__version__', 'unknown')}")
    for name in client.available_functions():
        fn = getattr(nflreadpy, name)
        try:
            signature = inspect.signature(fn)
        except (TypeError, ValueError):
            signature = "(signature unavailable)"
        print(f"{name}{signature}")


if __name__ == "__main__":
    main()
