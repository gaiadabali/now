import * as migration_20260914_083357_initial_console_auth from './20260914_083357_initial_console_auth';
import * as migration_20260915_000000_two_dimension_roles from './20260915_000000_two_dimension_roles';
import * as migration_20260915_000001_drop_legacy_role from './20260915_000001_drop_legacy_role';

// Order matters and is not alphabetical by accident: 000000 EXPANDS (adds and
// backfills the two role columns, leaving `role` in place so old and new code
// both work) and 000001 CONTRACTS (drops `role`). Running them as one step
// would break whatever console image is serving at the moment it ran.
// See 20260915_000001_drop_legacy_role.ts for when it is safe to apply.
export const migrations = [
  {
    up: migration_20260914_083357_initial_console_auth.up,
    down: migration_20260914_083357_initial_console_auth.down,
    name: '20260914_083357_initial_console_auth'
  },
  {
    up: migration_20260915_000000_two_dimension_roles.up,
    down: migration_20260915_000000_two_dimension_roles.down,
    name: '20260915_000000_two_dimension_roles'
  },
  {
    up: migration_20260915_000001_drop_legacy_role.up,
    down: migration_20260915_000001_drop_legacy_role.down,
    name: '20260915_000001_drop_legacy_role'
  },
];
