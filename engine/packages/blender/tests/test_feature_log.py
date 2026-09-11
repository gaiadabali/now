from __future__ import annotations

import json

from now_filters.models import Candidate

from now_blender.feature_log import build_record, log_feature_vector
from now_blender.features import build_stage4_features


def test_log_feature_vector_emits_valid_json_with_every_field():
    features = build_stage4_features(
        fused_hit=None,
        candidate=Candidate(entity_type="article", entity_id=5),
        subject=None,
        relations=None,
        freshness=0.42,
        quality=0.61,
        popularity_prior=None,
        covis_score=None,
        already_read=None,
        position=3,
    )
    record = build_record(
        site_slug="jakarta",
        surface="search",
        query="rooftop bar senopati",
        subject_entity_id=None,
        entity_type="article",
        entity_id=5,
        blend_score=0.55,
        weights_source="sites.ranking_weights['blend']",
        features=features,
    )
    line = log_feature_vector(record)
    parsed = json.loads(line)

    assert parsed["entity_id"] == 5
    assert parsed["site_slug"] == "jakarta"
    assert parsed["query"] == "rooftop bar senopati"
    assert parsed["features"]["freshness"] == 0.42
    assert parsed["features"]["quality"] == 0.61
    # nulls are present as JSON null, never dropped keys
    assert "covis_score" in parsed["features"]
    assert parsed["features"]["covis_score"] is None
    assert "user_facet_affinity" in parsed["features"]
    assert parsed["features"]["user_facet_affinity"] is None
