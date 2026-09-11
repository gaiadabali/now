from now_quality.popularity import compute_priors


def test_only_head_gets_nonzero_prior():
    views = {i: 100 for i in range(50)}  # tail, flat
    views.update({100 + i: 3000 - i * 10 for i in range(10)})  # head, spread out
    priors = compute_priors(views, head_n=10)

    head_keys = {100 + i for i in range(10)}
    for key, prior in priors.items():
        if key in head_keys:
            assert prior.in_head is True
        else:
            assert prior.in_head is False
            assert prior.prior_score == 0.0
            assert prior.rank > 10


def test_top_ranked_head_member_gets_prior_near_one():
    views = {i: 1000 + i * 100 for i in range(20)}
    priors = compute_priors(views, head_n=5)
    top_key = max(views, key=views.get)
    assert priors[top_key].rank == 1
    assert priors[top_key].prior_score == 1.0


def test_empty_input_returns_empty():
    assert compute_priors({}, head_n=300) == {}


def test_head_n_larger_than_corpus_includes_everything():
    views = {1: 10, 2: 20, 3: 5}
    priors = compute_priors(views, head_n=300)
    assert all(p.in_head for p in priors.values())
