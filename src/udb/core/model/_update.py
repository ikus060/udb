import time

from sqlalchemy import select, text
from sqlalchemy.sql import ddl

"""
Collection of utility function to update database schema.
"""


def commit(conn):
    # SQLAlchmey 1.4 Commit current transaction and open a new one.
    if getattr(conn, '_transaction', None):
        conn._transaction.commit()


def is_sqlite(conn):
    """
    Check if connected to SQLite database
    """
    return 'SQLite' in conn.engine.dialect.__class__.__name__


def column_exists(conn, column):
    """
    Check if column exists.
    """
    table_name = column.table.fullname
    column_name = column.name
    if is_sqlite(conn):
        sql = 'SELECT %s FROM "%s"' % (column_name, table_name)
        try:
            conn.execute(text(sql)).first()
            return True
        except Exception:
            return False
    else:
        sql = "SELECT 1 FROM information_schema.columns WHERE table_name='%s' and column_name='%s'" % (
            table_name,
            column_name,
        )
        row = conn.execute(text(sql)).first()
        return row is not None


def column_add(conn, column):
    """
    Create column if missing.
    """
    table_name = column.table.fullname
    # Compile string representation of the column creation.
    conn.execute(text('ALTER TABLE "%s" ADD COLUMN %s' % (table_name, ddl.CreateColumn(column).compile(conn.engine))))
    return True


def recreate_table(conn, table, query):
    table_name = table.fullname
    temp_table = '%s_temp_%s' % (table_name, int(time.time()))
    # Create new table
    create_table_sql = str(ddl.CreateTable(table).compile(conn.engine)).replace(
        'CREATE TABLE %s' % table_name, 'CREATE TABLE %s' % temp_table
    )
    conn.execute(text(create_table_sql))
    if is_sqlite(conn):
        conn.execute(text("PRAGMA defer_foreign_keys = '1'"))
    # Copy data to new table using the provided query.
    conn.execute(
        text(
            'INSERT INTO %s (%s) %s'
            % (temp_table, ','.join([c.name for c in query.columns]), query.compile(conn.engine))
        )
    )
    # Drop previous table
    conn.execute(ddl.DropTable(table))
    # Rename table.
    conn.execute(text('ALTER TABLE %s RENAME TO %s' % (temp_table, table_name)))
    if is_sqlite(conn):
        conn.execute(text("PRAGMA defer_foreign_keys = '0'"))


def constraint_exists(conn, constraint):
    """
    Get detail information baout the table.
    """
    table_name = constraint.table.name
    constraint_name = constraint.name
    if is_sqlite(conn):
        try:
            row = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = '%s'" % table_name)
            ).first()
            return ('CONSTRAINT %s' % constraint_name) in row.sql
        except Exception:
            return False
    else:
        sql = "SELECT COUNT(*) FROM pg_catalog.pg_constraint WHERE conname='%s'" % (constraint_name)
        data = conn.execute(text(sql)).first()
        return data[0] >= 1


def constraint_add(conn, constraint):
    """
    Add given constraint to database schema.
    """
    if is_sqlite(conn):
        # On SQLite we need to recreate table.
        columns = [c for c in constraint.table.columns if not c.computed]
        recreate_table(conn, constraint.table, select(*columns))
    else:
        # On postgresql we use alter table.
        conn.execute(text(str(ddl.AddConstraint(constraint).compile(conn.engine))))


def index_exists(conn, index_name):
    """
    Check if the given index exists.
    """
    assert index_name
    if is_sqlite(conn):
        row = conn.execute(text("SELECT 1 FROM sqlite_master WHERE type='index' and name = '%s'" % index_name)).first()
    else:
        row = conn.execute(
            text(
                "SELECT 1 FROM pg_index, pg_class WHERE pg_class.oid = pg_index.indexrelid and relname = '%s'"
                % index_name
            )
        ).first()
    return row is not None


def index_drop(conn, index_name):
    """
    Drop given constraints.
    """
    assert index_name
    conn.execute(text("DROP INDEX %s" % index_name))


def table_exists(conn, table):
    """
    Check if given table exists.
    """
    assert table is not None and table.name
    if is_sqlite(conn):
        row = conn.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name = '%s'" % table.name)).first()
    else:
        row = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name = '%s'" % table.name)).first()
    return row is not None
