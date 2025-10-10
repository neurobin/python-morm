"""Test unique_groups feature"""

from morm.model import Model
from morm.fields import Field
from morm.pg_models import Base


# Test 1: Define a model with unique_groups
class UserEmail(Base):
    class Meta:
        unique_groups = {
            'user_email': ['user_id', 'email'],
            'user_provider': ['user_id', 'provider']
        }

    user_id = Field('integer')
    email = Field('varchar(255)')
    provider = Field('varchar(50)')
    verified = Field('boolean', default=False)


# Test 2: Verify that unique_groups is stored in Meta
def test_unique_groups_in_meta():
    """Test that unique_groups is properly stored in Meta"""
    assert hasattr(UserEmail.Meta, 'unique_groups')
    assert isinstance(UserEmail.Meta.unique_groups, dict)
    assert 'user_email' in UserEmail.Meta.unique_groups
    assert 'user_provider' in UserEmail.Meta.unique_groups
    assert UserEmail.Meta.unique_groups['user_email'] == ['user_id', 'email']
    assert UserEmail.Meta.unique_groups['user_provider'] == ['user_id', 'provider']
    print("✓ unique_groups is properly stored in Meta")


# Test 3: Test inheritance
class ExtendedUserEmail(UserEmail):
    class Meta:
        unique_groups = {
            'user_email': ['user_id', 'email'],  # Inherited and kept
            'user_token': ['user_id', 'token']   # New constraint
        }

    token = Field('varchar(100)')


def test_inheritance():
    """Test that unique_groups can be overridden in child classes"""
    assert hasattr(ExtendedUserEmail.Meta, 'unique_groups')
    assert 'user_email' in ExtendedUserEmail.Meta.unique_groups
    assert 'user_token' in ExtendedUserEmail.Meta.unique_groups
    # Should not have user_provider as it was not included in the child Meta
    assert 'user_provider' not in ExtendedUserEmail.Meta.unique_groups
    print("✓ unique_groups inheritance works correctly")


# Test 4: Test migration query generation
from morm.migration import Migration


def test_create_table_query():
    """Test that CREATE TABLE query includes unique constraints"""
    import tempfile
    import os

    # Create a temporary directory for migration files
    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(UserEmail, tmpdir)
        query = migration.get_create_table_query()

        # Check that the query contains the unique constraints
        assert '__UNQ_UserEmail_user_email__' in query
        assert '__UNQ_UserEmail_user_provider__' in query
        assert 'UNIQUE ("user_id", "email")' in query
        assert 'UNIQUE ("user_id", "provider")' in query

        print("✓ CREATE TABLE query includes unique constraints")
        print("\nGenerated CREATE TABLE query:")
        print(query)


def test_unique_groups_changes():
    """Test that unique_groups changes are detected"""
    import tempfile
    import json

    # Create a model with initial unique_groups
    class TestModel(Base):
        class Meta:
            unique_groups = {
                'group1': ['field1', 'field2']
            }

        field1 = Field('integer')
        field2 = Field('varchar(100)')
        field3 = Field('varchar(100)')

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial migration
        migration1 = Migration(TestModel, tmpdir)

        # Manually create a previous migration file to simulate existing state
        prev_json = {
            'db_table': 'TestModel',
            'fields': {},
            'unique_groups': {
                'group1': ['field1', 'field2']
            }
        }

        os.makedirs(migration1.migration_dir, exist_ok=True)
        prev_file = os.path.join(migration1.migration_dir, 'TestModel_00000001_test.json')
        with open(prev_file, 'w') as f:
            json.dump(prev_json, f)

        # Create migration with changes
        class TestModel2(Base):
            class Meta:
                db_table = 'TestModel'
                unique_groups = {
                    'group1': ['field1', 'field3'],  # Modified
                    'group2': ['field2', 'field3']   # Added
                }

            field1 = Field('integer')
            field2 = Field('varchar(100)')
            field3 = Field('varchar(100)')

        migration2 = Migration(TestModel2, tmpdir)

        # Get change queries
        changes = list(migration2._get_unique_groups_changes())

        # Should detect modification of group1 and addition of group2
        assert len(changes) >= 2

        queries = [q for q, m in changes]
        combined_query = ' '.join(queries)

        # Check for modifications
        assert 'DROP CONSTRAINT' in combined_query or 'group1' in combined_query
        assert 'ADD CONSTRAINT' in combined_query
        assert '__UNQ_TestModel_group2__' in combined_query

        print("✓ unique_groups changes are detected correctly")
        print("\nDetected changes:")
        for query, msg in changes:
            print(msg)
            print(query)


if __name__ == '__main__':
    print("Testing unique_groups feature...\n")

    test_unique_groups_in_meta()
    test_inheritance()
    test_create_table_query()
    test_unique_groups_changes()

    print("\n✓ All tests passed!")
