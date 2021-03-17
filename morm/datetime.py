"""datetime handling.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


from datetime import datetime, timezone


def timestamp() -> datetime:
    """Get current timestamp.

    Returns:
        datetime.datetime
    """
    return datetime.now()

def timestampu() -> datetime:
    """Get current UTC timestamp.

    Example: '2021-03-12 05:29:22.497195+00:00'

    Returns:
        datetime.datetime
    """
    return datetime.now(timezone.utc)
