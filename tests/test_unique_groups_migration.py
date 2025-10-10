#!/usr/bin/python
"""Test unique_groups migration functionality"""

import sys
import os
import tempfile
import json
sys.path.insert(0, '..')

from morm.fields import Field
from morm.pg_models import Base

# Mock the asyncpg and pydantic dependencies for migration testing
sys.modules['asyncpg'] = type(sys)('asyncpg')
sys.modules['asyncpg'].Pool = object
sys.modules['asyncpg'].exceptions = type(sys)('exceptions')
sys.modules['asyncpg'].exceptions.PostgresSyntaxError = Exception

# Now we can import migration
from morm.migration import Migration


class SiteUser(Base):
    class Meta:
        unique_groups = {
            'name_profession': ['name', 'profession'],
            'profession_age': ['profession', 'age']
        }

    name = Field('varchar(254)')
    profession = Field('varchar(258)')
    age = Field('integer')


def test_unique_groups_in_meta():
    """Test that unique_groups is properly stored in SiteUser.Meta"""
    print("\n=== Test 1: Verify unique_groups in Meta ===")

    assert hasattr(SiteUser.Meta, 'unique_groups')
    assert isinstance(SiteUser.Meta.unique_groups, dict)
    assert 'name_profession' in SiteUser.Meta.unique_groups
    assert 'profession_age' in SiteUser.Meta.unique_groups
    assert SiteUser.Meta.unique_groups['name_profession'] == ['name', 'profession']
    assert SiteUser.Meta.unique_groups['profession_age'] == ['profession', 'age']

    print("✓ unique_groups is properly stored in Meta")
    print(f"  unique_groups = {SiteUser.Meta.unique_groups}")


def test_create_table_with_unique_groups():
    """Test CREATE TABLE query generation with unique_groups"""
    print("\n=== Test 2: CREATE TABLE query generation ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(SiteUser, tmpdir)
        query = migration.get_create_table_query()

        print("\nGenerated CREATE TABLE query:")
        print("-" * 80)
        print(query)
        print("-" * 80)

        # Verify the query contains unique constraints
        assert '__UNQ_SiteUser_name_profession__' in query
        assert '__UNQ_SiteUser_profession_age__' in query
        assert 'UNIQUE ("name", "profession")' in query
        assert 'UNIQUE ("profession", "age")' in query
        assert 'ALTER TABLE "SiteUser" ADD CONSTRAINT' in query

        print("\n✓ CREATE TABLE query includes both unique constraints")


def test_migration_json_contains_unique_groups():
    """Test that migration JSON includes unique_groups"""
    print("\n=== Test 3: Migration JSON structure ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(SiteUser, tmpdir)

        # Check current_json structure
        assert 'unique_groups' in migration.current_json
        assert migration.current_json['unique_groups'] == {
            'name_profession': ['name', 'profession'],
            'profession_age': ['profession', 'age']
        }

        print("\nMigration JSON structure:")
        print(json.dumps(migration.current_json, indent=2))

        print("\n✓ Migration JSON contains unique_groups")


def test_unique_groups_change_detection():
    """Test that changes to unique_groups are detected"""
    print("\n=== Test 4: unique_groups change detection ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial migration
        migration1 = Migration(SiteUser, tmpdir)

        # Simulate existing migration with different unique_groups
        os.makedirs(migration1.migration_dir, exist_ok=True)
        prev_json = {
            'db_table': 'SiteUser',
            'fields': {
                'name': {'column_name': 'name', 'sql_type': 'varchar(254)', 'sql_onadd': '', 'sql_alter': (), 'sql_ondrop': ''},
                'profession': {'column_name': 'profession', 'sql_type': 'varchar(258)', 'sql_onadd': '', 'sql_alter': (), 'sql_ondrop': ''},
                'age': {'column_name': 'age', 'sql_type': 'integer', 'sql_onadd': '', 'sql_alter': (), 'sql_ondrop': ''}
            },
            'unique_groups': {
                'old_constraint': ['name', 'age']  # Different constraint
            }
        }

        prev_file = os.path.join(migration1.migration_dir, 'SiteUser_00000001_test.json')
        with open(prev_file, 'w') as f:
            json.dump(prev_json, f)

        # Create new migration with changes
        migration2 = Migration(SiteUser, tmpdir)

        # Get unique_groups changes
        changes = list(migration2._get_unique_groups_changes())

        print(f"\nDetected {len(changes)} unique_groups changes:")
        print("-" * 80)

        for query, msg in changes:
            print(msg)
            print("\nSQL:")
            print(query)
            print("-" * 80)

        # Verify changes were detected
        assert len(changes) > 0

        queries_combined = ' '.join([q for q, m in changes])

        # Should drop old constraint
        assert 'DROP CONSTRAINT' in queries_combined
        assert '__UNQ_SiteUser_old_constraint__' in queries_combined

        # Should add new constraints
        assert 'ADD CONSTRAINT' in queries_combined
        assert '__UNQ_SiteUser_name_profession__' in queries_combined
        assert '__UNQ_SiteUser_profession_age__' in queries_combined

        print("\n✓ unique_groups changes detected correctly")


def test_field_order_preservation():
    """Test that field order in unique_groups is preserved"""
    print("\n=== Test 5: Field order preservation ===")

    class OrderTest(Base):
        class Meta:
            unique_groups = {
                'test_order': ['field3', 'field1', 'field2']  # Specific order
            }

        field1 = Field('integer')
        field2 = Field('varchar(100)')
        field3 = Field('varchar(100)')

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(OrderTest, tmpdir)
        query = migration.get_create_table_query()

        # Find the UNIQUE constraint line
        lines = query.split('\n')
        unique_line = [l for l in lines if '__UNQ_OrderTest_test_order__' in l][0]

        print(f"\nUnique constraint: {unique_line.strip()}")

        # Verify field order is preserved: field3, field1, field2
        assert 'UNIQUE ("field3", "field1", "field2")' in unique_line

        print("✓ Field order is preserved in the constraint")


def test_empty_unique_groups():
    """Test model without unique_groups"""
    print("\n=== Test 6: Model without unique_groups ===")

    class NoUniqueGroups(Base):
        name = Field('varchar(100)')
        age = Field('integer')

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(NoUniqueGroups, tmpdir)
        query = migration.get_create_table_query()

        # Should not contain unique constraint SQL
        assert '__UNQ_' not in query

        # But should still have empty unique_groups in JSON
        assert 'unique_groups' in migration.current_json
        assert migration.current_json['unique_groups'] == {}

        print("✓ Models without unique_groups work correctly")


if __name__ == '__main__':
    print("=" * 80)
    print("Testing unique_groups Migration Functionality")
    print("=" * 80)

    test_unique_groups_in_meta()
    test_create_table_with_unique_groups()
    test_migration_json_contains_unique_groups()
    test_unique_groups_change_detection()
    test_field_order_preservation()
    test_empty_unique_groups()

    print("\n" + "=" * 80)
    print("✓ All migration tests passed!")
    print("=" * 80)
