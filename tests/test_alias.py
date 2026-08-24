import unittest

from morm.db import DB
from morm.model import Model
from morm.fields import Field, ExprField


class Order(Model):
    price = Field('numeric')
    qty = Field('integer')
    total = ExprField('"price" * "qty"', 'numeric')

    class Meta:
        db_table = 'test_alias_order'


class TestAliasMetaLevel(unittest.TestCase):
    def test_meta_f_with_alias(self):
        om = Order.Meta('o')
        self.assertEqual(om.f.price, '"o"."price"')
        self.assertEqual(om.f.qty, '"o"."qty"')

    def test_meta_f_exprfield(self):
        om = Order.Meta('o')
        self.assertEqual(om.f.total, '("price" * "qty")')

    def test_meta_fs_default_as_prefix(self):
        om = Order.Meta('o')
        self.assertEqual(om.fs.price, '"o"."price" AS "price"')
        self.assertEqual(om.fs.total, '("price" * "qty") AS "total"')

    def test_meta_fs_custom_as_prefix(self):
        om = Order.Meta('o', as_prefix='o__')
        self.assertEqual(om.fs.price, '"o"."price" AS "o__price"')
        self.assertEqual(om.fs.total, '("price" * "qty") AS "o__total"')

    def test_meta_fs_no_as(self):
        om = Order.Meta('o', as_prefix=None)
        self.assertEqual(om.fs.price, '"o"."price"')
        self.assertEqual(om.fs.total, '("price" * "qty")')

    def test_meta_f_invalid_field(self):
        om = Order.Meta('o')
        with self.assertRaises(AttributeError):
            om.f.nonexistent


class TestAliasQueryHandle(unittest.TestCase):
    db = DB(None)

    def test_qh_f_with_alias(self):
        qh = self.db(Order, 'o')
        self.assertEqual(qh.f.price, '"o"."price"')
        self.assertEqual(qh.f.total, '("price" * "qty")')

    def test_qh_fs_default(self):
        qh = self.db(Order, 'o')
        self.assertEqual(qh.fs.price, '"o"."price" AS "price"')
        self.assertEqual(qh.fs.total, '("price" * "qty") AS "total"')

    def test_qh_fs_custom_prefix(self):
        qh = self.db(Order, 'o', as_prefix='o__')
        self.assertEqual(qh.fs.price, '"o"."price" AS "o__price"')

    def test_qh_fs_no_as(self):
        qh = self.db(Order, 'o', as_prefix=None)
        self.assertEqual(qh.fs.price, '"o"."price"')

    def test_qfilter_with_alias(self):
        qh = self.db(Order, 'o').qfilter().qc('', '$1', True)
        q, _ = qh.getq()
        self.assertIn('"test_alias_order" "o"', q)
        self.assertIn('"o"."price" AS "price"', q)

    def test_no_alias_unchanged(self):
        qh = self.db(Order)
        self.assertEqual(qh.f.price, '"price"')
        self.assertEqual(qh.fs.price, '"price" AS "price"')


if __name__ == '__main__':
    unittest.main()
