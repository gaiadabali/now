import * as migration_20260908_131927_initial_schema from './20260908_131927_initial_schema';
import * as migration_20260908_140000_places_geography from './20260908_140000_places_geography';
import * as migration_20260908_144101_events_content from './20260908_144101_events_content';
import * as migration_20260909_150000_add_unknown_type_enum_value from './20260909_150000_add_unknown_type_enum_value';
import * as migration_20260909_150100_places_unknown_type_and_status_type_index from './20260909_150100_places_unknown_type_and_status_type_index';
import * as migration_20260910_020207_add_classification_reviews from './20260910_020207_add_classification_reviews';
import * as migration_20260910_032226_vocabulary_delta_140_terms from './20260910_032226_vocabulary_delta_140_terms';
import * as migration_20260910_060000_classification_reviews_no_clobber_trigger from './20260910_060000_classification_reviews_no_clobber_trigger';
import * as migration_20260910_095611_add_places_legacy_wp_id from './20260910_095611_add_places_legacy_wp_id';
import * as migration_20260918_090000_articles_slug from './20260918_090000_articles_slug';
import * as migration_20260924_111729_articles_created_by from './20260924_111729_articles_created_by';
import * as migration_20260926_090000_places_junk_status_enum_value from './20260926_090000_places_junk_status_enum_value';
import * as migration_20260926_090100_places_provenance_and_curation_fields from './20260926_090100_places_provenance_and_curation_fields';
import * as migration_20260926_100000_editions_collection from './20260926_100000_editions_collection';
import * as migration_20260927_090000_places_aliases_and_reviewed_by from './20260927_090000_places_aliases_and_reviewed_by';

export const migrations = [
  {
    up: migration_20260908_131927_initial_schema.up,
    down: migration_20260908_131927_initial_schema.down,
    name: '20260908_131927_initial_schema',
  },
  {
    up: migration_20260908_140000_places_geography.up,
    down: migration_20260908_140000_places_geography.down,
    name: '20260908_140000_places_geography',
  },
  {
    up: migration_20260908_144101_events_content.up,
    down: migration_20260908_144101_events_content.down,
    name: '20260908_144101_events_content',
  },
  {
    up: migration_20260909_150000_add_unknown_type_enum_value.up,
    down: migration_20260909_150000_add_unknown_type_enum_value.down,
    name: '20260909_150000_add_unknown_type_enum_value',
  },
  {
    up: migration_20260909_150100_places_unknown_type_and_status_type_index.up,
    down: migration_20260909_150100_places_unknown_type_and_status_type_index.down,
    name: '20260909_150100_places_unknown_type_and_status_type_index',
  },
  {
    up: migration_20260910_020207_add_classification_reviews.up,
    down: migration_20260910_020207_add_classification_reviews.down,
    name: '20260910_020207_add_classification_reviews',
  },
  {
    up: migration_20260910_032226_vocabulary_delta_140_terms.up,
    down: migration_20260910_032226_vocabulary_delta_140_terms.down,
    name: '20260910_032226_vocabulary_delta_140_terms',
  },
  {
    up: migration_20260910_060000_classification_reviews_no_clobber_trigger.up,
    down: migration_20260910_060000_classification_reviews_no_clobber_trigger.down,
    name: '20260910_060000_classification_reviews_no_clobber_trigger',
  },
  {
    up: migration_20260910_095611_add_places_legacy_wp_id.up,
    down: migration_20260910_095611_add_places_legacy_wp_id.down,
    name: '20260910_095611_add_places_legacy_wp_id',
  },
  {
    up: migration_20260918_090000_articles_slug.up,
    down: migration_20260918_090000_articles_slug.down,
    name: '20260918_090000_articles_slug',
  },
  {
    up: migration_20260924_111729_articles_created_by.up,
    down: migration_20260924_111729_articles_created_by.down,
    name: '20260924_111729_articles_created_by'
  },
  {
    up: migration_20260926_090000_places_junk_status_enum_value.up,
    down: migration_20260926_090000_places_junk_status_enum_value.down,
    name: '20260926_090000_places_junk_status_enum_value',
  },
  {
    up: migration_20260926_090100_places_provenance_and_curation_fields.up,
    down: migration_20260926_090100_places_provenance_and_curation_fields.down,
    name: '20260926_090100_places_provenance_and_curation_fields',
  },
  {
    up: migration_20260926_100000_editions_collection.up,
    down: migration_20260926_100000_editions_collection.down,
    name: '20260926_100000_editions_collection',
  },
  {
    up: migration_20260927_090000_places_aliases_and_reviewed_by.up,
    down: migration_20260927_090000_places_aliases_and_reviewed_by.down,
    name: '20260927_090000_places_aliases_and_reviewed_by',
  },
];
