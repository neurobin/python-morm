"""Exceptions.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


class ItemDoesNotExistError(Exception): pass
class TransactionError(Exception): pass
class MigrationError(Exception): pass
class MigrationModelNotAllowedError(Exception): pass
class UnsupportedError(Exception): pass
