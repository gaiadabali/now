from now_eval.datasets.split import is_eval, split_bucket, split_for


def test_split_is_deterministic():
    for wp_id in range(1000, 1100):
        assert split_for(wp_id) == split_for(wp_id)
        assert is_eval(wp_id) == (split_for(wp_id) == "eval")


def test_split_bucket_in_range():
    for wp_id in range(0, 500):
        b = split_bucket(wp_id)
        assert 0 <= b < 100


def test_split_roughly_matches_eval_fraction_over_large_n():
    # Not a strict guarantee (hash-based), but over 5000 ids it should
    # land close to the configured 20% within a generous tolerance --
    # catches a badly broken hash (e.g. one that always returns 'train').
    n = 5000
    eval_count = sum(1 for wp_id in range(n) if is_eval(wp_id))
    fraction = eval_count / n
    assert 0.15 < fraction < 0.25


def test_split_changes_with_salt():
    # Different salts must not be forced to agree -- if they always did,
    # SPLIT_VERSION bumps would be a no-op.
    wp_ids = range(0, 200)
    a = [split_for(w, salt="salt-a") for w in wp_ids]
    b = [split_for(w, salt="salt-b") for w in wp_ids]
    assert a != b


def test_split_respects_custom_eval_fraction():
    # eval_fraction=0.0 -> nothing is eval; eval_fraction=1.0 -> everything is.
    assert all(split_for(w, eval_fraction=0.0) == "train" for w in range(50))
    assert all(split_for(w, eval_fraction=1.0) == "eval" for w in range(50))
