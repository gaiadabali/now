from now_partner_roster.domains import (
    classify,
    extract_netloc,
    is_own_site,
    parse_root_domain,
    repair_href,
)


def test_repair_href_unwraps_double_scheme():
    # observed in the real corpus (wp_id 456, 6029, 6583...): a stray
    # "http://" prepended to an already-absolute URL by a copy/paste bug.
    assert repair_href("http://https://www.ismaya.com/eat-drink/x") == "https://www.ismaya.com/eat-drink/x"


def test_repair_href_leaves_normal_urls_alone():
    assert repair_href("https://www.marriott.com/hotels") == "https://www.marriott.com/hotels"


def test_extract_netloc_absolute_http():
    assert extract_netloc("https://WWW.Marriott.com/promo") == "www.marriott.com"


def test_extract_netloc_rejects_non_http_schemes():
    assert extract_netloc("mailto:hello@example.com") is None
    assert extract_netloc("tel:+62211234") is None
    assert extract_netloc("#inbox/_blank") is None
    assert extract_netloc("") is None


def test_extract_netloc_repairs_double_scheme():
    assert extract_netloc("http://https://book.chope.co/booking?rid=1") == "book.chope.co"


def test_is_own_site():
    assert is_own_site("nowjakarta.co.id")
    assert is_own_site("www.nowjakarta.co.id")
    assert is_own_site("best.nowjakarta.co.id")
    assert is_own_site("nowbali.co.id")
    assert not is_own_site("marriott.com")


def test_classify_social_stock_shortener_utility_internal():
    assert classify("www.instagram.com").reason == "social"
    assert classify("unsplash.com").reason == "stock"
    assert classify("bit.ly").reason == "shortener"
    assert classify("grab.onelink.me").reason == "shortener"
    assert classify("wa.me").reason == "utility"
    assert classify("nowjakarta.co.id").reason == "internal"
    assert not classify("marriott.com").excluded


def test_parse_root_domain_simple_com():
    rd = parse_root_domain("marriott.com")
    assert rd.root == "marriott"
    assert rd.suffix == "com"
    assert rd.subdomain is None


def test_parse_root_domain_co_id_suffix():
    rd = parse_root_domain("marriott.co.id")
    assert rd.root == "marriott"
    assert rd.suffix == "co.id"
    assert rd.subdomain is None


def test_parse_root_domain_generic_subdomain_collapses():
    rd = parse_root_domain("www.discoverasr.com")
    assert rd.root == "discoverasr"
    assert rd.subdomain is None
    rd2 = parse_root_domain("all.accor.com")
    assert rd2.root == "accor"
    assert rd2.subdomain is None


def test_parse_root_domain_specific_subdomain_is_a_property():
    rd = parse_root_domain("bali.intercontinental.com")
    assert rd.root == "intercontinental"
    assert rd.subdomain == "bali"

    rd2 = parse_root_domain("www.jakartapondokindah.intercontinental.com")
    assert rd2.root == "intercontinental"
    assert rd2.subdomain == "jakartapondokindah"
