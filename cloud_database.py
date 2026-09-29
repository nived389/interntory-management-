"""PostgreSQL bridge for the application's parameterized SQLite query subset."""
import re
import sqlite3

ID_TABLES = set('users properties sections items movements counts snapshots audit archives notifications submissions'.split())
TABLES = list('users properties sections items movements counts lines snapshots audit archives settings notifications submissions'.split())

def translate(sql):
    sql = re.sub(r'([\w.]+) COLLATE NOCASE', r'lower(\1)', sql)
    sql = re.sub(r"json_extract\((\w+),'\$\.(\w+)'\)", r"(\1::jsonb ->> '\2')", sql)
    sql = re.sub(r'\bLIKE\b', 'ILIKE', sql)
    ignore = sql.startswith('INSERT OR IGNORE')
    sql = sql.replace('INSERT OR IGNORE', 'INSERT')
    # Leave quoted SQL literals untouched; escape literal percent for psycopg.
    parts = re.split("('(?:[^']|'')*')", sql)
    sql = ''.join(p.replace('%', '%%').replace('?', '%s') if i % 2 == 0 else p.replace('%', '%%') for i,p in enumerate(parts))
    if ignore: sql += ' ON CONFLICT DO NOTHING'
    match = re.match(r'INSERT INTO (\w+)', sql, re.I)
    returning = bool(match and match[1] in ID_TABLES)
    if returning: sql += ' RETURNING id'
    return sql, returning

class Result:
    def __init__(self, cursor, returning=False):
        self.cursor = cursor
        self.rowcount = cursor.rowcount
        row = cursor.fetchone() if returning else None
        self.lastrowid = row['id'] if row else None
    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()

class Database:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.connection = psycopg.connect(url, sslmode='require', row_factory=dict_row, prepare_threshold=None, connect_timeout=15)
        self.connection.execute('SET search_path TO inventory, pg_catalog')
        self.connection.commit()
    def execute(self, sql, args=()):
        import psycopg
        if sql == 'BEGIN IMMEDIATE':
            # Serialize inventory write workflows across workers; held until commit/rollback.
            return Result(self.connection.execute('SELECT pg_advisory_xact_lock(746281905)'))
        statement, returning = translate(sql)
        try: return Result(self.connection.execute(statement, args), returning)
        except psycopg.IntegrityError as exc: raise sqlite3.IntegrityError('Database constraint failed') from exc
    def executemany(self, sql, args):
        for row in args: self.execute(sql,row)
    def commit(self): self.connection.commit()
    def rollback(self): self.connection.rollback()
    def close(self): self.connection.close()
    def dump(self):
        # Single transaction snapshot, also used by the master-only backup endpoint.
        self.connection.rollback()
        self.connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        return {table:self.execute('SELECT * FROM '+table).fetchall() for table in TABLES}
