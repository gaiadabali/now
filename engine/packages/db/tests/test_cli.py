"""Tests for now_db.cli commands, especially bare db_ref handling."""

import os
from unittest import mock

import pytest
from click.testing import CliRunner

from now_db.cli import cli
from now_db.settings import city_database_url


class TestCliMigrateUrl:
    """Test that migrate --url works with bare db_refs and full DSNs."""

    def test_migrate_url_with_bare_db_ref(self):
        """migrate --url should accept a bare database name and convert it to a full DSN."""
        runner = CliRunner()

        # Mock the provisioning functions to avoid actual DB access
        with mock.patch("now_db.cli.provisioning.migrate_city") as mock_migrate, \
             mock.patch("now_db.cli.provisioning.ensure_city_partitions") as mock_partitions:
            mock_partitions.return_value = []

            # Pass a bare db_ref like the hash and check commands accept
            result = runner.invoke(cli, ["migrate", "--url", "now_jakarta"])

            assert result.exit_code == 0, f"Command failed: {result.output}"

            # Verify that provisioning.migrate_city was called with a full DSN, not the bare name
            mock_migrate.assert_called_once()
            called_dsn = mock_migrate.call_args[0][0]

            # The DSN should be a full postgresql:// URL
            assert "postgresql" in called_dsn, f"Expected a full DSN, got: {called_dsn}"
            assert "now_jakarta" in called_dsn, f"Expected 'now_jakarta' in the DSN, got: {called_dsn}"

            # Verify the output mentions the bare db_ref we passed
            assert "now_jakarta" in result.output
            assert "migrated" in result.output

    def test_migrate_url_with_full_dsn(self):
        """migrate --url should accept a full DSN and pass it through."""
        runner = CliRunner()

        full_dsn = "postgresql+psycopg://user:pass@localhost:5432/now_bali"

        with mock.patch("now_db.cli.provisioning.migrate_city") as mock_migrate, \
             mock.patch("now_db.cli.provisioning.ensure_city_partitions") as mock_partitions:
            mock_partitions.return_value = []

            result = runner.invoke(cli, ["migrate", "--url", full_dsn])

            assert result.exit_code == 0, f"Command failed: {result.output}"

            # Verify the full DSN was passed through
            mock_migrate.assert_called_once_with(full_dsn)

    def test_city_database_url_bare_ref(self):
        """Verify city_database_url() handles bare db_ref correctly."""
        # Test bare db_ref
        dsn = city_database_url("now_jakarta")
        assert "postgresql" in dsn
        assert "now_jakarta" in dsn
        # Should use default host/port/user/password from settings
        assert "localhost" in dsn or os.environ.get("NOW_PG_HOST") in dsn

    def test_city_database_url_full_dsn_passthrough(self):
        """Verify city_database_url() passes through full DSNs."""
        full_dsn = "postgresql://custom:creds@remotehost:9999/custom_db"
        result = city_database_url(full_dsn)
        assert result == full_dsn
