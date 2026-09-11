DELETE FROM engine.entity_terms WHERE entity_type='article' AND entity_id='999999';
INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
VALUES ('article','999999','a7c5f8b9-14bb-4739-a47d-797695d02354', 1, 'editor', 1);

INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
VALUES ('article','999999','a7c5f8b9-14bb-4739-a47d-797695d02354', 0.9, 'ai', 0.51)
ON CONFLICT (entity_type, entity_id, term_id)
DO UPDATE SET weight=EXCLUDED.weight, confidence=EXCLUDED.confidence, source=EXCLUDED.source;

SELECT 'after naive ON CONFLICT DO UPDATE (no guard)' AS attack, entity_type, entity_id, term_id, source, confidence, weight
FROM engine.entity_terms WHERE entity_type='article' AND entity_id='999999';

UPDATE engine.entity_terms SET source='ai', confidence=0.2, weight=0.3
WHERE entity_type='article' AND entity_id='999999';

SELECT 'after plain UPDATE (no guard at all)' AS attack, entity_type, entity_id, term_id, source, confidence, weight
FROM engine.entity_terms WHERE entity_type='article' AND entity_id='999999';

DELETE FROM engine.entity_terms WHERE entity_type='article' AND entity_id='999999';
