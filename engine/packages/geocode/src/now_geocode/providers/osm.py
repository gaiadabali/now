"""OSM-backed providers — the zero-cost alternative to `GoogleProvider`
for rungs 2 and 3 (ARCHITECTURE.md §15 treats the geocoder as a
*resolution service*, so which service resolves is an implementation
detail as long as the result is real and attributable).

Two concrete providers, same OSM data, different strengths:

  - `NominatimProvider` — the reference OSM geocoder. Strong on
    structured addresses (rung 2), weak on business names (rung 3).
  - `PhotonProvider`    — Komoot's OSM search, built for incremental /
    fuzzy *name* lookup. Materially better at rung 3 ("Potato Head
    Beach Club") than Nominatim, which is why both exist here rather
    than one "OSM provider".

Chain them with `providers/chain.ChainProvider` to get a free name
search in front of Google's, and pay Google only for the residue.

## Why this is not simply "Google but free"

ARCHITECTURE.md §15 chose Google deliberately: *"Indonesian addresses
are messy; accuracy matters."* That reason is real and this module does
not pretend otherwise. Two concrete differences are handled explicitly:

(1) **OSM free-text search degrades silently.** Ask Nominatim for
    "Potato Head Beach Club, Seminyak, Bali" and a miss does not return
    zero results — it returns *Seminyak*, a real coordinate for the
    wrong thing. That is worse than `None`, because `None` is a stable
    negative the state cache can trust while a wrong point ships as a
    resolved place. `name_agrees` gates every rung-3 result on the
    returned feature's own name overlapping the queried venue name, and
    returns `None` when it doesn't. See its docstring for why it
    compares against `name` and not `display_name`.

(2) **No `place_id`.** `ProviderResult.google_place_id` is left `None` —
    never an OSM id wearing a Google field's name. OSM identity
    (`osm_type`/`osm_id`) is preserved in `raw` for audit. Downstream,
    `location_type` carries the provenance instead (`osm_poi`,
    `osm_street`, ...), matching how rung 1 already distinguishes
    `mappress_poi` from `google_map_acf`.

## Licensing — a genuine advantage over Google

Google's ToS permits storing `place_id` indefinitely but restricts
caching other fields, which is exactly why §15 says "keep your own
canonical record". OSM data is ODbL: coordinates may be stored
permanently, attribution is the obligation. For a database that *is* the
permanent canonical record, that is the easier fit.

## Rate limits are a correctness concern, not politeness

The public Nominatim instance enforces max 1 request/second **and** a
User-Agent that identifies the application; violating either earns a
403/429 rather than a result, and bulk geocoding on the public instance
is against its usage policy outright. `min_interval_s` defaults to 1.0
and `user_agent` is required for that reason. **Self-hosting against a
Geofabrik Indonesia extract removes both limits** — pass
`base_url=<your host>` and `min_interval_s=0.0`. E5.1 needs the same
extract on disk for OSRM anyway, so the marginal cost of self-hosting is
low.

HTTP goes through an injectable `session` (same contract as
`GoogleProvider`) so `tests/test_osm_provider.py` replays recorded
fixtures with zero network access.
"""

from __future__ import annotations

import time
from typing import Any

from now_geocode.models import ProviderResult
from now_geocode.providers.base import ProviderConfigError, ProviderError, RetryableProviderError
from now_geocode.quality import INDONESIA_BBOX
from now_geocode.textnorm import normalize_name

NOMINATIM_PUBLIC_URL = "https://nominatim.openstreetmap.org"
PHOTON_PUBLIC_URL = "https://photon.komoot.io"

# Nominatim's usage policy requires a UA identifying the application and
# a contact route. A generic/absent UA is answered with 403 by the public
# instance, so this is a functional requirement, not etiquette.
DEFAULT_USER_AGENT = "now-engine-geocode/0.1 (NOW! Engine E2.5 batch geocode; +https://nowjakarta.co.id)"

# Derived from the single bbox source of truth in quality.py rather than
# restated, so the request-time bias and the post-hoc bbox gate can never
# drift apart into "biased to a box the gate then rejects".
_VIEWBOX_LON_MIN = INDONESIA_BBOX["lng_min"]
_VIEWBOX_LON_MAX = INDONESIA_BBOX["lng_max"]
_VIEWBOX_LAT_MIN = INDONESIA_BBOX["lat_min"]
_VIEWBOX_LAT_MAX = INDONESIA_BBOX["lat_max"]

# Granularity -> confidence, deliberately parallel to GoogleProvider's
# GEOCODE_LOCATION_TYPE_CONFIDENCE so blended runs stay on one scale.
# Every bucket sits at or below its Google counterpart: OSM POI geometry
# is community-contributed and positionally looser than a ROOFTOP
# geocode, so claiming 0.95 for it would overstate what we know.
#   poi/building ~ ROOFTOP(0.95)            -> 0.90/0.85
#   street       ~ RANGE_INTERPOLATED(0.75) -> 0.65
#   locality     ~ GEOMETRIC_CENTER(0.55)   -> 0.45
#   area         ~ APPROXIMATE(0.35)        -> 0.30
GRANULARITY_CONFIDENCE = {
    "poi": 0.90,
    "building": 0.85,
    "street": 0.65,
    "locality": 0.45,
    "area": 0.30,
}
UNKNOWN_GRANULARITY_CONFIDENCE = 0.40

# Rung 3 ceiling. Below GoogleProvider's flat 0.6 for the reason in (1):
# OSM's business-name index is thinner, so a passing name-agreement check
# is weaker evidence here than a Places Text Search hit is there.
NAME_SEARCH_CONFIDENCE = 0.50

# OSM `class` values that denote an actual mapped venue rather than an
# administrative or linear feature.
_POI_CLASSES = {
    "amenity", "shop", "tourism", "leisure", "craft",
    "office", "healthcare", "historic", "club", "sport",
}
_LOCALITY_PLACE_TYPES = {
    "suburb", "neighbourhood", "quarter", "village", "hamlet",
    "locality", "city_block", "borough",
}
_AREA_PLACE_TYPES = {
    "city", "town", "municipality", "county", "state", "region",
    "province", "country", "island", "archipelago",
}

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_CONFIG_STATUS_CODES = {401, 403}

# Tokens too short to carry identity in a venue name ("de", "by", "&" once
# punctuation is stripped). Excluded from the name-agreement denominator
# so "W Bali" isn't judged mostly on "W".
_MIN_SIGNIFICANT_TOKEN_LEN = 3

# Tokens that carry no identity IN THIS CORPUS, so they must not count
# toward name agreement. Length alone does not catch them: "the" is three
# characters and passes the length filter, and "bali" appears in a large
# share of these venue names.
#
# Measured consequence of omitting this list — two wrong venues that the
# gate waved through on a live run:
#
#   "The Legian Seminyak Bali" matched "The Trans Resort Bali"
#       {the, legian, seminyak, bali} vs {the, trans, resort, bali}
#       -> overlap {the, bali} = 2/4 = 0.5, passed, 1.5 km wrong hotel
#   "Anantara Seminyak" matched "Anantara Vacation Club"
#       -> overlap {anantara} = 1/2 = 0.5, passed, different entity
#
# Both are exactly the silent-wrong-answer the gate exists to stop; it
# was being defeated by its own scoring.
_NON_DISTINCTIVE = {
    # articles / connectives that survive the length filter
    "the", "and", "for", "with",
    # venue-type words — true of the venue, useless for identifying it
    "hotel", "hotels", "resort", "resorts", "villa", "villas", "suites",
    "spa", "club", "restaurant", "bar", "cafe", "lounge", "beach",
    "house", "residence", "apartments", "inn",
    # the corpus is entirely Bali/Jakarta, so these discriminate nothing
    "bali", "jakarta", "indonesia",
}


def classify_granularity(osm_class: str | None, osm_type: str | None) -> str:
    """Map an OSM (class, type) pair onto one of GRANULARITY_CONFIDENCE's
    buckets. `osm_class` is OSM's `class`/`osm_key`, `osm_type` its
    `type`/`osm_value` — NOT the `osm_type` w/n/r element kind, which is
    a different field entirely (kept in `raw`)."""

    cls = (osm_class or "").lower()
    typ = (osm_type or "").lower()
    if cls in _POI_CLASSES:
        return "poi"
    if cls == "building":
        return "building"
    if cls == "highway":
        return "street"
    if cls == "place":
        if typ in _LOCALITY_PLACE_TYPES:
            return "locality"
        if typ in _AREA_PLACE_TYPES:
            return "area"
        if typ in {"house", "building"}:
            return "building"
        return "locality"
    if cls in {"boundary", "landuse", "natural", "waterway"}:
        return "area"
    return "unknown"


def _confidence_for(granularity: str) -> float:
    return GRANULARITY_CONFIDENCE.get(granularity, UNKNOWN_GRANULARITY_CONFIDENCE)


def _significant_tokens(text: str) -> set[str]:
    return {t for t in normalize_name(text).split() if len(t) >= _MIN_SIGNIFICANT_TOKEN_LEN}


def name_agrees(queried_name: str, feature_name: str | None, *, threshold: float = 0.6) -> bool:
    """Does `feature_name` plausibly name the same venue as `queried_name`?

    Rung 3 asks a free-text search for a *venue name*; OSM answers with
    its nearest interpretation, which on a miss is routinely the
    enclosing suburb or city. Without this gate that lands in
    `geocoded_places.jsonl` as a resolved place at a real-looking
    coordinate — the exact "silently geocode to the wrong thing" failure
    the bbox gate exists to catch for countries, one level down.

    Compared against the feature's **own name only**, never its
    `display_name`: a display name is "Seminyak, Badung, Bali,
    Indonesia", so a venue whose name contains "Bali" would match its
    own city and pass a gate that read the full string. That would
    defeat the check precisely on the names most at risk.

    Coverage is measured over the *queried* name's significant tokens,
    so a shorter OSM name still passes ("Potato Head" vs "Potato Head
    Beach Club" = 2/4 = 0.5) while an unrelated one fails ("Seminyak"
    = 0/4). Single-significant-token venues must match that one token
    exactly, since no fractional threshold is meaningful there.
    """

    wanted_all = _significant_tokens(queried_name)
    got_all = _significant_tokens(feature_name or "")
    if not wanted_all or not got_all:
        # Nothing to check against — do not invent agreement.
        return False

    # Score on distinctive tokens only. "The Legian Seminyak Bali" and
    # "The Trans Resort Bali" share half their significant tokens and none
    # of their distinctive ones. See _NON_DISTINCTIVE.
    wanted = wanted_all - _NON_DISTINCTIVE
    got = got_all - _NON_DISTINCTIVE

    if not wanted:
        # The QUERIED name is entirely generic ("The Beach Club"). Nothing
        # can identify it, so demand the whole significant name rather
        # than guessing on stopwords.
        return wanted_all <= got_all or got_all <= wanted_all
    if not got:
        # The FEATURE's name is entirely generic while the query names
        # something specific: "Potato Head Beach Club" against a feature
        # called merely "Beach Club". That could be any beach club, so it
        # cannot confirm this one. Asymmetric on purpose — treating it the
        # same as the branch above accepted it on stopwords alone.
        return False

    # Containment, not a coverage ratio. A correct match is one name being
    # a shorter form of the other; a wrong match brings distinctive tokens
    # the query never mentioned. Tuning a threshold cannot separate these
    # — measured on the live run, 0.5 admitted two wrong venues and 0.6
    # rejected two right ones:
    #
    #   RIGHT  "The Legian Seminyak Bali" / "The Legian Bali"
    #          {legian} subset of {legian, seminyak}            -> accept
    #   RIGHT  "The Anvaya Becah Resort Bali" / "The ANVAYA Hotel"
    #          {anvaya} subset of {anvaya, becah}               -> accept
    #   WRONG  "Anantara Seminyak" / "Anantara Vacation Club"
    #          {anantara, vacation} brings "vacation"           -> reject
    #   WRONG  "The Legian Seminyak Bali" / "The Trans Resort Bali"
    #          {trans} shares nothing                           -> reject
    #
    # Brand collisions are the case this catches: two properties sharing
    # a brand token differ precisely by the extra token.
    return wanted <= got or got <= wanted


class _OsmProviderBase:
    """Shared HTTP, rate limiting and error mapping. Subclasses supply
    endpoint construction and response parsing only."""

    name = "osm"

    def __init__(
        self,
        base_url: str,
        *,
        session: Any = None,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_s: float = 1.0,
        timeout: float = 10.0,
        sleep_fn: Any = None,
        clock_fn: Any = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = session
        self.user_agent = user_agent
        self.min_interval_s = min_interval_s
        self.timeout = timeout
        self._sleep = sleep_fn or time.sleep
        self._clock = clock_fn or time.monotonic
        self._last_call_at: float | None = None

    @property
    def session(self) -> Any:
        if self._session is None:
            import requests  # lazy, mirroring GoogleProvider

            self._session = requests.Session()
        return self._session

    def _throttle(self) -> None:
        if self.min_interval_s <= 0:
            return
        now = self._clock()
        if self._last_call_at is not None:
            elapsed = now - self._last_call_at
            if elapsed < self.min_interval_s:
                self._sleep(self.min_interval_s - elapsed)
        self._last_call_at = self._clock()

    def _get(self, url: str, params: dict) -> Any:
        if not self.user_agent:
            raise ProviderConfigError(
                "An identifying User-Agent is mandatory for Nominatim/Photon; the public "
                "instances answer a generic or absent UA with 403. Pass user_agent=... "
                "(see providers/osm.py module docstring)."
            )
        self._throttle()
        try:
            response = self.session.get(
                url, params=params, timeout=self.timeout, headers={"User-Agent": self.user_agent}
            )
        except Exception as exc:  # network-level failure — resumable
            raise RetryableProviderError(f"network error calling {url}: {exc}") from exc

        # Fakes in tests may omit status_code; absent means "a 200 body".
        status_code = getattr(response, "status_code", 200)
        if status_code in _RETRYABLE_STATUS_CODES:
            raise RetryableProviderError(
                f"HTTP {status_code} from {url} — rate limited or upstream unavailable, resumable"
            )
        if status_code in _CONFIG_STATUS_CODES:
            raise ProviderConfigError(
                f"HTTP {status_code} from {url} — blocked. On the public Nominatim instance this "
                "is normally a missing/generic User-Agent or bulk use against the usage policy; "
                "self-host against a Geofabrik extract for batch runs."
            )
        if status_code >= 400:
            raise ProviderError(f"HTTP {status_code} from {url}")

        try:
            return response.json()
        except Exception as exc:
            raise ProviderError(f"non-JSON response from {url}") from exc


class NominatimProvider(_OsmProviderBase):
    """OSM reference geocoder. Best at rung 2 (structured addresses)."""

    name = "nominatim"

    def __init__(self, base_url: str = NOMINATIM_PUBLIC_URL, **kwargs: Any) -> None:
        super().__init__(base_url, **kwargs)

    @property
    def search_url(self) -> str:
        return f"{self.base_url}/search"

    def _base_params(self, query: str) -> dict:
        return {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            # Country restriction is the analogue of Google's
            # components=country:ID — same same-named-street-worldwide
            # failure mode called out in §15/§6.
            "countrycodes": "id",
            "viewbox": f"{_VIEWBOX_LON_MIN},{_VIEWBOX_LAT_MAX},{_VIEWBOX_LON_MAX},{_VIEWBOX_LAT_MIN}",
        }

    def geocode_address(self, address: str) -> ProviderResult | None:
        data = self._get(self.search_url, self._base_params(address))
        feature = self._first(data)
        if feature is None:
            return None
        return self._to_result(feature, rung_is_name_search=False)

    def find_place(self, name: str, context: str | None) -> ProviderResult | None:
        query = name if not context else f"{name}, {context}"
        data = self._get(self.search_url, self._base_params(query))
        feature = self._first(data)
        if feature is None:
            return None
        if not name_agrees(name, self._feature_name(feature)):
            # A real coordinate for the wrong thing — see (1) in the
            # module docstring. A stable negative is the correct answer.
            return None
        return self._to_result(feature, rung_is_name_search=True)

    @staticmethod
    def _first(data: Any) -> dict | None:
        if not isinstance(data, list) or not data:
            return None
        return data[0]

    @staticmethod
    def _feature_name(feature: dict) -> str | None:
        name = feature.get("name")
        if name:
            return name
        display = feature.get("display_name")
        # First comma-component is the feature's own label; the rest is
        # its administrative envelope (see name_agrees' docstring).
        return display.split(",")[0].strip() if display else None

    @staticmethod
    def _feature_category(feature: dict) -> str | None:
        """Nominatim's `format=jsonv2` calls the OSM key **`category`**;
        the older `format=json` calls it `class`. Verified against a live
        Nominatim 5.3.2: jsonv2 returns `category`. Reading only `class`
        silently classified every result as `unknown` (0.40) instead of
        `poi` (0.90) — the tests missed it because the fixtures had been
        written in the `json` shape. Both spellings are accepted so a
        version or format change cannot reintroduce that."""
        return feature.get("category") or feature.get("class")

    def _to_result(self, feature: dict, *, rung_is_name_search: bool) -> ProviderResult:
        granularity = classify_granularity(self._feature_category(feature), feature.get("type"))
        confidence = (
            min(NAME_SEARCH_CONFIDENCE, _confidence_for(granularity))
            if rung_is_name_search
            else _confidence_for(granularity)
        )
        return ProviderResult(
            lat=float(feature["lat"]),
            lng=float(feature["lon"]),
            formatted_address=feature.get("display_name"),
            google_place_id=None,  # never an OSM id in a Google-named field
            location_type=f"osm_{granularity}",
            confidence=confidence,
            provider=self.name,
            is_synthetic=False,
            raw=feature,
        )


class PhotonProvider(_OsmProviderBase):
    """Komoot's OSM search. Built for fuzzy name lookup — the rung-3
    provider of choice, and the reason this module ships two classes."""

    name = "photon"

    def __init__(self, base_url: str = PHOTON_PUBLIC_URL, **kwargs: Any) -> None:
        super().__init__(base_url, **kwargs)

    @property
    def search_url(self) -> str:
        return f"{self.base_url}/api"

    def _base_params(self, query: str) -> dict:
        return {
            "q": query,
            "limit": 1,
            "lang": "en",
            # Photon has no countrycodes; bbox is the available bias.
            "bbox": f"{_VIEWBOX_LON_MIN},{_VIEWBOX_LAT_MIN},{_VIEWBOX_LON_MAX},{_VIEWBOX_LAT_MAX}",
        }

    def geocode_address(self, address: str) -> ProviderResult | None:
        data = self._get(self.search_url, self._base_params(address))
        feature = self._first(data)
        if feature is None:
            return None
        return self._to_result(feature, rung_is_name_search=False)

    def find_place(self, name: str, context: str | None) -> ProviderResult | None:
        query = name if not context else f"{name}, {context}"
        data = self._get(self.search_url, self._base_params(query))
        feature = self._first(data)
        if feature is None:
            return None
        if not name_agrees(name, (feature.get("properties") or {}).get("name")):
            return None
        return self._to_result(feature, rung_is_name_search=True)

    @staticmethod
    def _first(data: Any) -> dict | None:
        if not isinstance(data, dict):
            return None
        features = data.get("features")
        if not features:
            return None
        return features[0]

    def _to_result(self, feature: dict, *, rung_is_name_search: bool) -> ProviderResult:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            raise ProviderError("Photon feature has no usable Point geometry")
        # GeoJSON is [lon, lat] — the inverse of every other shape here.
        lng, lat = float(coords[0]), float(coords[1])

        granularity = classify_granularity(props.get("osm_key"), props.get("osm_value"))
        confidence = (
            min(NAME_SEARCH_CONFIDENCE, _confidence_for(granularity))
            if rung_is_name_search
            else _confidence_for(granularity)
        )
        return ProviderResult(
            lat=lat,
            lng=lng,
            formatted_address=self._format_address(props),
            google_place_id=None,
            location_type=f"osm_{granularity}",
            confidence=confidence,
            provider=self.name,
            is_synthetic=False,
            raw=feature,
        )

    @staticmethod
    def _format_address(props: dict) -> str | None:
        parts = [
            props.get("name"),
            props.get("street"),
            props.get("district"),
            props.get("city"),
            props.get("state"),
            props.get("country"),
        ]
        joined = ", ".join(p for p in parts if p)
        return joined or None
