import unittest
import random

from morm.db import DB
from morm.model import Model
from morm.fields import Field, ExprField
import morm.migration as mg


class LineItem(Model):
    price = Field('numeric')
    qty = Field('integer')
    total = ExprField('"price" * "qty"', 'numeric')

    class Meta:
        db_table = 'test_exprfield_lineitem'


class TestExprField(unittest.TestCase):
    db = DB(None)  # query-building only; no pool required

    def test_field_select_sql(self):
        f = Field('varchar(10)')
        f.name = 'name'
        self.assertEqual(f.select_sql('name'), '"name" AS "name"')

    def test_exprfield_select_sql(self):
        ef = ExprField('"price" * "qty"', 'numeric')
        ef.name = 'total'
        self.assertEqual(ef.select_sql('total'), '("price" * "qty") AS "total"')
        self.assertFalse(ef.persisted)

    def test_meta_f_and_fs(self):
        self.assertEqual(LineItem.Meta.f.price, 'price')
        self.assertEqual(LineItem.Meta.f.total, '"price" * "qty"')
        self.assertEqual(LineItem.Meta.fs.price, '"price" AS "price"')
        self.assertEqual(LineItem.Meta.fs.total, '("price" * "qty") AS "total"')

    def test_model_query_f_and_fs(self):
        qh = self.db(LineItem)
        self.assertEqual(qh.f.price, '"price"')
        self.assertEqual(qh.f.total, '("price" * "qty")')
        self.assertEqual(qh.fs.price, '"price" AS "price"')
        self.assertEqual(qh.fs.total, '("price" * "qty") AS "total"')

    def test_qfilter_uses_fs(self):
        qh = self.db(LineItem).qfilter().qc('', '$1', True)
        q, _ = qh.getq()
        self.assertIn('"price" AS "price"', q)
        self.assertIn('("price" * "qty") AS "total"', q)
        self.assertNotIn('SELECT "price","qty"', q)

    def test_exprfield_read_only_setattr(self):
        item = LineItem(price=10, qty=2)
        with self.assertRaises(AttributeError):
            item.total = 99

    def test_insert_skips_exprfield(self):
        item = LineItem(price=10, qty=3)
        query, values = self.db.get_insert_query(item)
        self.assertIn('"price"', query)
        self.assertIn('"qty"', query)
        self.assertNotIn('"total"', query)
        self.assertEqual(values, [10, 3])

    def test_qupdate_rejects_exprfield(self):
        with self.assertRaises(ValueError):
            self.db(LineItem).qupdate({'total': 5})

    def test_migration_ignores_exprfield(self):
        mgo = mg.Migration(LineItem, '/tmp/__morm_exprfield_migration__' + str(random.random()))
        fields = mgo._get_fields()
        self.assertIn('price', fields)
        self.assertIn('qty', fields)
        self.assertNotIn('total', fields)
        create_q = mgo.get_create_table_query()
        self.assertIn('"price"', create_q)
        self.assertNotIn('AS "total"', create_q)

    def test_unique_groups_rejects_exprfield(self):
        with self.assertRaises(ValueError):
            class Bad(Model):
                a = Field('integer')
                b = ExprField('"a" + 1', 'integer')

                class Meta:
                    db_table = 'bad_expr_unique'
                    unique_groups = {'u': ('a', 'b')}

    def test_hydrate_from_db(self):
        item = LineItem()
        item.Meta._fromdb_.append('total')
        item.total = 30
        self.assertEqual(item.total, 30)


if __name__ == '__main__':
    unittest.main()
