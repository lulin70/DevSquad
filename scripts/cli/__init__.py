# CLI Package
#
# V4.5.16 P2.16 housekeeping: ``scripts/cli/cli_visual.py`` is retained
# (see docstring note in that file) because ``scripts.cli_lifecycle``
# dynamically inserts ``scripts/cli`` on ``sys.path`` and imports
# ``cli_visual`` by short name. The package itself is otherwise empty
# and acts as a sys.path anchor for that legacy import path.
# 已登记 V4.5.16 housekeeping 待确认.
