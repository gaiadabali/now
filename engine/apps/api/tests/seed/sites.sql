-- Synthetic registry rows for tests. Deliberately not named after any real
-- city (see the site-name-literal ban, ARCHITECTURE.md §3.5) -- `alpha` /
-- `beta` exercise pool isolation, `gamma-provisioning` exercises the
-- not-yet-active path, `delta-unreachable` exercises the unreachable-DB
-- path (its db_ref points at a database that is never created).
INSERT INTO engine.sites (slug, hostname, name, locale, timezone, currency, db_ref, enabled_modules, status)
VALUES
  ('alpha', 'alpha.example.test', 'Alpha City', 'en-ID', 'Asia/Pontianak', 'IDR', 'now_alpha', '{feed,search}', 'active'),
  ('beta', 'beta.example.test', 'Beta City', 'en-ID', 'Asia/Makassar', 'IDR', 'now_beta', '{feed}', 'active'),
  ('gamma-provisioning', 'gamma.example.test', 'Gamma City', 'en-ID', 'Asia/Pontianak', 'IDR', 'now_gamma', '{}', 'provisioning'),
  ('delta-unreachable', 'delta.example.test', 'Delta City', 'en-ID', 'Asia/Pontianak', 'IDR', 'now_missing_db', '{}', 'active')
ON CONFLICT (slug) DO NOTHING;
