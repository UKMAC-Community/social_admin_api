from fastapi import Response


NO_STORE_CACHE_CONTROL = "no-store, max-age=0, must-revalidate"


def set_no_store_headers(response: Response) -> None:
    """Prevent public post responses from being served with stale content."""
    response.headers["Cache-Control"] = NO_STORE_CACHE_CONTROL
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
