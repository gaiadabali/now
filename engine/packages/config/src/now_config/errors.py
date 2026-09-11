class SiteNotFoundError(Exception):
    """Raised when no registry row matches the requested slug/hostname.

    Callers (e.g. the API's `get_city_db` dependency) are expected to map
    this to a 404 — an unknown site is a client error, never a 500.
    """

    def __init__(self, *, lookup: str, value: str) -> None:
        self.lookup = lookup
        self.value = value
        super().__init__(f"no site registry row for {lookup}={value!r}")
