import os
import json
import random
import shutil
import unittest
import tempfile

from morm.model import Model
from morm.fields.field import (
    Field,
    parse_name_list,
    parse_index_specs,
    normalize_meta_indexes,
)
import morm.migration as mg


class SiteUser(Model):
    class Meta:
        db_table = 'SiteUser'
        indexes = {
            'my_index': {
                'cols': ['id', 'userID'],
                'indexes': 'hash,btree',
            },
        }

    id = Field('SERIAL', sql_onadd='PRIMARY KEY NOT NULL')
    userID = Field('integer')
    name = Field('varchar(254)')


class TestIndexHelpers(unittest.TestCase):
    def test_parse_name_list(self):
        self.assertEqual(parse_name_list('userID'), ['userID'])
        self.assertEqual(parse_name_list('id,userID'), ['id', 'userID'])
        self.assertEqual(parse_name_list('id, userID'), ['id', 'userID'])
        self.assertEqual(parse_name_list(['id', 'userID']), ['id', 'userID'])
        self.assertEqual(parse_name_list(('id', 'userID')), ['id', 'userID'])
        self.assertEqual(parse_name_list(''), [])
        with self.assertRaises(ValueError):
            parse_name_list('id,,userID')
        with self.assertRaises(TypeError):
            parse_name_list(12)

    def test_parse_index_specs(self):
        self.assertEqual(parse_index_specs('hash,btree'), [
            ('hash', '', False),
            ('btree', '', False),
        ])
        self.assertEqual(parse_index_specs(['gin:gin__int_ops']), [
            ('gin', 'gin__int_ops', False),
        ])
        self.assertEqual(parse_index_specs('-hash'), [
            ('hash', '', True),
        ])
        with self.assertRaises(ValueError):
            parse_index_specs('bcrypt')

    def test_normalize_meta_indexes(self):
        a = normalize_meta_indexes({
            'my_index': {'cols': 'id,userID', 'indexes': 'hash,btree'},
        })
        b = normalize_meta_indexes({
            'my_index': {'cols': ['id', 'userID'], 'indexes': ['hash', 'btree']},
        })
        self.assertEqual(a, b)
        self.assertEqual(a['my_index']['cols'], ['id', 'userID'])
        self.assertEqual(a['my_index']['indexes'], ['hash', 'btree'])
        with self.assertRaises(ValueError):
            normalize_meta_indexes({'x': {'cols': ['id'], 'indexes': 'bcrypt'}})
        with self.assertRaises(ValueError):
            normalize_meta_indexes({'x': {'cols': [], 'indexes': 'btree'}})


class TestMetaIndexes(unittest.TestCase):
    def test_indexes_in_meta(self):
        self.assertTrue(hasattr(SiteUser.Meta, 'indexes'))
        self.assertEqual(SiteUser.Meta.indexes, {
            'my_index': {
                'cols': ['id', 'userID'],
                'indexes': 'hash,btree',
            },
        })

    def test_invalid_index_type_on_model(self):
        with self.assertRaises(ValueError):
            class BadUser(Model):
                class Meta:
                    indexes = {
                        'bad': {'cols': ['id'], 'indexes': 'bcrypt'},
                    }
                id = Field('SERIAL')

    def test_create_table_and_json(self):
        mgpath = tempfile.mkdtemp(prefix='_morm_indexes_')
        try:
            mgo = mg.Migration(SiteUser, mgpath)
            query = mgo.get_create_table_query()
            self.assertIn('__IDX_SiteUser_my_index_hash__', query)
            self.assertIn('__IDX_SiteUser_my_index_btree__', query)
            self.assertIn('USING hash ("id", "userID")', query)
            self.assertIn('USING btree ("id", "userID")', query)
            self.assertIn('CREATE INDEX IF NOT EXISTS', query)

            self.assertIn('indexes', mgo.current_json)
            self.assertEqual(mgo.current_json['indexes'], {
                'my_index': {
                    'cols': ['id', 'userID'],
                    'indexes': ['hash', 'btree'],
                },
            })
        finally:
            shutil.rmtree(mgpath, ignore_errors=True)

    def test_string_vs_list_cols_and_indexes_equal(self):
        class UserA(Model):
            class Meta:
                db_table = 'IdxEq'
                indexes = {
                    'id_user': {'cols': 'id,userID', 'indexes': 'btree'},
                }
            id = Field('SERIAL')
            userID = Field('integer')

        class UserB(Model):
            class Meta:
                db_table = 'IdxEq'
                indexes = {
                    'id_user': {'cols': ['id', 'userID'], 'indexes': ['btree']},
                }
            id = Field('SERIAL')
            userID = Field('integer')

        mgpath = tempfile.mkdtemp(prefix='_morm_indexes_eq_')
        try:
            a = mg.Migration(UserA, mgpath)
            b = mg.Migration(UserB, mgpath)
            self.assertEqual(a.current_json['indexes'], b.current_json['indexes'])
            self.assertEqual(a.get_create_table_query(), b.get_create_table_query())
        finally:
            shutil.rmtree(mgpath, ignore_errors=True)

    def test_indexes_change_detection(self):
        mgpath = '/tmp/_morm_indexes_chg_' + str(random.random())
        os.makedirs(mgpath, exist_ok=True)
        try:
            mgo = mg.Migration(SiteUser, mgpath)
            os.makedirs(mgo.migration_dir, exist_ok=True)
            prev_json = json.loads(json.dumps(mgo.current_json))
            prev_json['indexes'] = {
                'old_index': {
                    'cols': ['name'],
                    'indexes': ['hash'],
                },
            }
            prev_file = os.path.join(mgo.migration_dir, 'SiteUser_00000001_test.json')
            with open(prev_file, 'w') as f:
                json.dump(prev_json, f)

            mgo2 = mg.Migration(SiteUser, mgpath)
            changes = list(mgo2._get_indexes_changes())
            self.assertGreater(len(changes), 0)
            queries_combined = ' '.join([q for q, m in changes])
            self.assertIn('DROP INDEX IF EXISTS', queries_combined)
            self.assertIn('__IDX_SiteUser_old_index_hash__', queries_combined)
            self.assertIn('CREATE INDEX IF NOT EXISTS', queries_combined)
            self.assertIn('__IDX_SiteUser_my_index_hash__', queries_combined)
            self.assertIn('__IDX_SiteUser_my_index_btree__', queries_combined)
        finally:
            shutil.rmtree(mgpath, ignore_errors=True)

    def test_modify_index_cols(self):
        class UserMod(Model):
            class Meta:
                db_table = 'IdxMod'
                indexes = {
                    'my_index': {'cols': ['id', 'name'], 'indexes': ['btree']},
                }
            id = Field('SERIAL')
            name = Field('varchar(10)')

        mgpath = tempfile.mkdtemp(prefix='_morm_indexes_mod_')
        try:
            mgo = mg.Migration(UserMod, mgpath)
            os.makedirs(mgo.migration_dir, exist_ok=True)
            prev_json = json.loads(json.dumps(mgo.current_json))
            prev_json['indexes'] = {
                'my_index': {'cols': ['id'], 'indexes': ['btree']},
            }
            prev_file = os.path.join(mgo.migration_dir, 'IdxMod_00000001_test.json')
            with open(prev_file, 'w') as f:
                json.dump(prev_json, f)

            mgo2 = mg.Migration(UserMod, mgpath)
            changes = list(mgo2._get_indexes_changes())
            self.assertEqual(len(changes), 1)
            query, msg = changes[0]
            self.assertIn('DROP INDEX IF EXISTS "__IDX_IdxMod_my_index_btree__"', query)
            self.assertIn('USING btree ("id", "name")', query)
            self.assertIn('MODIFY INDEX', msg)
        finally:
            shutil.rmtree(mgpath, ignore_errors=True)

    def test_empty_indexes(self):
        class Plain(Model):
            class Meta:
                db_table = 'PlainIdx'
            id = Field('SERIAL')

        mgpath = tempfile.mkdtemp(prefix='_morm_indexes_empty_')
        try:
            mgo = mg.Migration(Plain, mgpath)
            self.assertEqual(mgo.current_json['indexes'], {})
            self.assertNotIn('CREATE INDEX IF NOT EXISTS "__IDX_PlainIdx_', mgo.get_create_table_query())
            self.assertEqual(list(mgo._get_indexes_changes()), [])
        finally:
            shutil.rmtree(mgpath, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
