import * as migration_20260914_083357_initial_console_auth from './20260914_083357_initial_console_auth';

export const migrations = [
  {
    up: migration_20260914_083357_initial_console_auth.up,
    down: migration_20260914_083357_initial_console_auth.down,
    name: '20260914_083357_initial_console_auth'
  },
];
