"""Catalog based migrations (morm 4).

The models are compared directly against the Postgres catalog of the target
database; the desired state is obtained by creating the models in a throwaway
shadow schema inside a transaction that is always rolled back.  Applied
migrations are recorded in the database itself (``_morm_migrations``).
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'

LEDGER_TABLE = '_morm_migrations'
