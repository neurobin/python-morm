#!/usr/bin/python
"""
Demonstration of unique_groups feature
This script shows how unique_groups work in the morm ORM
"""

import sys
sys.path.insert(0, '..')

# We need to check if dependencies are available
try:
    from morm.fields import Field
    from morm.pg_models import Base
    from morm.migration import Migration
    import tempfile
    import json
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"⚠ Dependencies not available: {e}")
    print("This demonstration requires pydantic and asyncpg to be installed.")
    print("Install with: pip install pydantic asyncpg")
    DEPENDENCIES_AVAILABLE = False
    sys.exit(1)


def demo_basic_usage():
    """Demonstrate basic unique_groups usage"""
    print("\n" + "="*80)
    print("DEMO 1: Basic unique_groups Usage")
    print("="*80)

    class SiteUser(Base):
        class Meta:
            unique_groups = {
                'name_profession': ['name', 'profession'],
                'profession_age': ['profession', 'age']
            }

        name = Field('varchar(254)')
        profession = Field('varchar(258)')
        age = Field('integer')

    print("\nModel Definition:")
    print("-" * 80)
    print("""
class SiteUser(Base):
    class Meta:
        unique_groups = {
            'name_profession': ['name', 'profession'],
            'profession_age': ['profession', 'age']
        }

    name = Field('varchar(254)')
    profession = Field('varchar(258)')
    age = Field('integer')
    """)

    print("\nMeta.unique_groups:")
    print(f"  {SiteUser.Meta.unique_groups}")

    print("\nThis creates two composite unique constraints:")
    print("  1. UNIQUE (name, profession)")
    print("  2. UNIQUE (profession, age)")


def demo_create_table_sql():
    """Demonstrate CREATE TABLE SQL generation"""
    print("\n" + "="*80)
    print("DEMO 2: CREATE TABLE SQL Generation")
    print("="*80)

    class UserEmail(Base):
        class Meta:
            unique_groups = {
                'user_email': ['user_id', 'email'],
            }

        user_id = Field('integer')
        email = Field('varchar(255)')
        verified = Field('boolean', default=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(UserEmail, tmpdir)
        create_query = migration.get_create_table_query()

        print("\nGenerated CREATE TABLE Query:")
        print("-" * 80)
        print(create_query)
        print("-" * 80)

        print("\n✓ Notice the ALTER TABLE ADD CONSTRAINT statement for unique_groups")


def demo_migration_json():
    """Demonstrate migration JSON structure"""
    print("\n" + "="*80)
    print("DEMO 3: Migration JSON Structure")
    print("="*80)

    class Product(Base):
        class Meta:
            unique_groups = {
                'warehouse_sku': ['warehouse_id', 'sku'],
            }

        warehouse_id = Field('integer')
        sku = Field('varchar(100)')
        quantity = Field('integer')

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(Product, tmpdir)

        print("\nMigration JSON (current_json):")
        print("-" * 80)
        print(json.dumps(migration.current_json, indent=2))
        print("-" * 80)

        print("\n✓ Notice 'unique_groups' is stored in the migration JSON")


def demo_change_detection():
    """Demonstrate unique_groups change detection"""
    print("\n" + "="*80)
    print("DEMO 4: Change Detection for unique_groups")
    print("="*80)

    class Item(Base):
        class Meta:
            db_table = 'Item'
            unique_groups = {
                'category_name': ['category', 'name'],
                'category_order': ['category', 'sort_order']
            }

        category = Field('varchar(100)')
        name = Field('varchar(255)')
        sort_order = Field('integer')

    with tempfile.TemporaryDirectory() as tmpdir:
        migration = Migration(Item, tmpdir)

        # Simulate existing migration with different unique_groups
        import os
        os.makedirs(migration.migration_dir, exist_ok=True)

        prev_json = {
            'db_table': 'Item',
            'fields': {
                'category': {'column_name': 'category', 'sql_type': 'varchar(100)', 'sql_onadd': '', 'sql_alter': (), 'sql_ondrop': ''},
                'name': {'column_name': 'name', 'sql_type': 'varchar(255)', 'sql_onadd': '', 'sql_alter': (), 'sql_ondrop': ''},
                'sort_order': {'column_name': 'sort_order', 'sql_type': 'integer', 'sql_onadd': '', 'sql_alter': (), 'sql_ondrop': ''}
            },
            'unique_groups': {
                'old_constraint': ['category', 'name']  # Only this one existed
            }
        }

        prev_file = os.path.join(migration.migration_dir, 'Item_00000001_test.json')
        with open(prev_file, 'w') as f:
            json.dump(prev_json, f)

        # Create new migration to detect changes
        migration2 = Migration(Item, tmpdir)
        changes = list(migration2._get_unique_groups_changes())

        print(f"\nDetected {len(changes)} changes:")
        print("-" * 80)

        for query, msg in changes:
            print(msg)
            print("\nSQL:")
            print(query)
            print("-" * 80)

        print("\n✓ Migration system automatically detected:")
        print("  1. Modified 'category_name' constraint (old: old_constraint)")
        print("  2. Added new 'category_order' constraint")


def demo_real_world_example():
    """Demonstrate a real-world use case"""
    print("\n" + "="*80)
    print("DEMO 5: Real-World Example - Multi-Tenant Application")
    print("="*80)

    class TenantSetting(Base):
        class Meta:
            unique_groups = {
                'tenant_key': ['tenant_id', 'setting_key'],
            }

        tenant_id = Field('integer')
        setting_key = Field('varchar(100)')
        setting_value = Field('text')
        updated_at = Field('timestamp with time zone')

    print("\nUse Case: Multi-tenant application where each tenant can have settings")
    print("         with unique keys, but different tenants can have the same key.")
    print("\nModel Definition:")
    print("-" * 80)
    print("""
class TenantSetting(Base):
    class Meta:
        unique_groups = {
            'tenant_key': ['tenant_id', 'setting_key'],
        }

    tenant_id = Field('integer')
    setting_key = Field('varchar(100)')
    setting_value = Field('text')
    updated_at = Field('timestamp with time zone')
    """)

    print("\nWhat this allows:")
    print("  ✓ Tenant 1 can have setting_key='theme' with value='dark'")
    print("  ✓ Tenant 2 can have setting_key='theme' with value='light'")
    print("  ✗ Tenant 1 CANNOT have two rows with setting_key='theme'")

    print("\nConstraint: UNIQUE (tenant_id, setting_key)")


def main():
    if not DEPENDENCIES_AVAILABLE:
        return

    print("\n" + "="*80)
    print("MORM unique_groups Feature Demonstration")
    print("="*80)

    demo_basic_usage()
    demo_create_table_sql()
    demo_migration_json()
    demo_change_detection()
    demo_real_world_example()

    print("\n" + "="*80)
    print("✓ All demonstrations completed successfully!")
    print("="*80)

    print("\nKey Takeaways:")
    print("  1. unique_groups is defined in the Model's Meta class")
    print("  2. Format: Dict[str, List[str]] - {group_name: [field1, field2, ...]}")
    print("  3. Field order in the list is preserved in the database constraint")
    print("  4. Migration system automatically handles CREATE/DROP/ALTER for constraints")
    print("  5. Constraint naming: __UNQ_{table}_{groupname}__")

    print("\nNext Steps:")
    print("  - Define unique_groups in your model's Meta class")
    print("  - Run: python mgr.py makemigrations")
    print("  - Run: python mgr.py migrate")
    print("  - Your database now has the composite unique constraints!")


if __name__ == '__main__':
    main()
