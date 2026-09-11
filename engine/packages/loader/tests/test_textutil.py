from now_loader.textutil import basename, slugify, strip_tags_light, summarize_content_loss


def test_slugify_basic():
    assert slugify("Bali") == "bali"
    assert slugify("South Jakarta") == "south-jakarta"


def test_slugify_strips_non_ascii():
    assert slugify("NOW!Jakarta’s Best") == "now-jakartas-best"


def test_strip_tags_light_removes_tags_and_unescapes_entities():
    assert strip_tags_light("<p>Hello &amp; welcome</p>") == "Hello & welcome"


def test_strip_tags_light_empty_is_none():
    assert strip_tags_light("") is None
    assert strip_tags_light(None) is None
    assert strip_tags_light("   ") is None


def test_basename_strips_query_and_trailing_slash():
    assert basename("2022/07/Photo.jpg") == "Photo.jpg"
    assert basename("https://example.com/x/y/Photo.jpg?w=200") == "Photo.jpg"


def test_summarize_content_loss_empty_is_all_none():
    assert summarize_content_loss([]) == {"median": None, "p95": None, "max": None}


def test_summarize_content_loss_median_p95_max():
    # 20 values, 0.0..1.9 in steps of 0.1 -> p95 index int(20*0.95)=19 -> max value (1.9)
    values = [round(i * 0.1, 3) for i in range(20)]
    result = summarize_content_loss(values)
    assert result["median"] == 0.95  # statistics.median averages the two middle values (0.9, 1.0)
    assert result["p95"] == 1.9
    assert result["max"] == 1.9


def test_summarize_content_loss_single_value():
    assert summarize_content_loss([0.417]) == {"median": 0.417, "p95": 0.417, "max": 0.417}
