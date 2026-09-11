"""QA.5 adversarial script against E4.2's claim:
'LinkDecision.rel is a computed @property; no code path (incl.
dataclasses.replace) can produce a non-"sponsored" rel for tier="paid".'

Run directly against the real now_link_resolver package (no mocks).
"""
import dataclasses
import sys

sys.path.insert(0, r"C:\Users\Hansel\Documents\Hansel\Projects\now\engine\packages\link-resolver\src")

from now_link_resolver.types import LinkDecision, _VALID_TIERS  # noqa: E402
from now_link_resolver.render import render_body_blocks  # noqa: E402

print("=== 1. Confirm rel is a property, not a field ===")
print("dataclass fields:", [f.name for f in dataclasses.fields(LinkDecision)])
print("'rel' in fields:", "rel" in {f.name for f in dataclasses.fields(LinkDecision)})
print("type(LinkDecision.rel):", type(LinkDecision.__dict__["rel"]))

decision = LinkDecision(tier="paid", place_id="p1", slug="p1", external_url="https://partner.example")
print("baseline decision.rel:", decision.rel)

print("\n=== 2. dataclasses.replace(decision, rel=...) ===")
try:
    bad = dataclasses.replace(decision, rel="nofollow")
    print("NO EXCEPTION -- replace succeeded:", bad)
except TypeError as e:
    print("TypeError raised (expected):", e)
except Exception as e:
    print("OTHER exception:", type(e), e)

print("\n=== 3. object.__setattr__(decision, 'rel', 'other') ===")
try:
    object.__setattr__(decision, "rel", "other")
    print("__setattr__ did not raise.")
except Exception as e:
    print("Exception on __setattr__:", type(e), e)
print("decision.rel after attempted override:", decision.rel)
print("decision.__dict__:", decision.__dict__)

print("\n=== 4. Subclass override attempt ===")


class EvilLinkDecision(LinkDecision):
    @property
    def rel(self):
        return "definitely-not-sponsored"


evil = EvilLinkDecision(tier="paid", place_id="p1", slug="p1", external_url="https://partner.example")
print("evil.rel:", evil.rel)
print("isinstance(evil, LinkDecision):", isinstance(evil, LinkDecision))

blocks = [{"type": "paragraph", "html": '<span data-place="p1">Place</span>'}]
out = render_body_blocks(blocks, {"p1": evil})
print("Rendered HTML using evil subclass instance through the REAL renderer:")
print(out[0]["html"])
print("Does rendered output still say sponsored?:", 'rel="sponsored"' in out[0]["html"])
print("Does rendered output contain the evil rel value?:", "definitely-not-sponsored" in out[0]["html"])

print("\n=== 4b. Overriding rel as a plain instance attribute (non-property) subclass ===")


class EvilLinkDecision2(LinkDecision):
    def __post_init__(self):
        super().__post_init__()
        try:
            object.__setattr__(self, "rel", "plain-attr-nofollow")
        except Exception as e:
            print("  setattr in subclass __post_init__ raised:", type(e), e)


evil2 = EvilLinkDecision2(tier="paid", place_id="p1", slug="p1", external_url="https://partner.example")
print("evil2.rel:", evil2.rel)
out2 = render_body_blocks(blocks, {"p1": evil2})
print("Rendered HTML with evil2:", out2[0]["html"])

print("\n=== 5. Try every tier value + malformed values via constructor ===")
for tier in list(_VALID_TIERS) + ["PAID", "Paid", " paid", "paid ", "premium", "", None, 123]:
    try:
        d = LinkDecision(tier=tier, place_id="p1", slug="p1", external_url="https://x.example")
        print(f"tier={tier!r:>10} -> constructed OK, rel={d.rel!r}, href={d.href!r}")
    except Exception as e:
        print(f"tier={tier!r:>10} -> rejected: {type(e).__name__}: {e}")

print("\n=== 5b. Can custom_url / other fields influence rel for tier='paid'? ===")
variants = [
    dict(tier="paid", place_id="p1", slug="p1", external_url=""),
    dict(tier="paid", place_id="p1", slug="p1", external_url="https://x.example", org_id="nofollow"),
    dict(tier="paid", place_id="p1", slug="p1", external_url="https://x.example", resolved_via="none"),
]
for kwargs in variants:
    try:
        d = LinkDecision(**kwargs)
        print(kwargs, "-> rel:", d.rel)
    except Exception as e:
        print(kwargs, "-> rejected:", type(e).__name__, e)

print("\n=== 6. Attempt to directly poke __class__ swap ===")
try:
    fake = LinkDecision(tier="free", place_id="p1")
    object.__setattr__(fake, "__class__", EvilLinkDecision)
    print("class swapped; fake.rel:", fake.rel, "fake.tier:", fake.tier)
except Exception as e:
    print("class swap raised:", type(e), e)

print("\nDONE")
