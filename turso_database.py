"""Direct libSQL driver; no local replica that can serve stale inventory."""
import sqlite3

class Result:
    def __init__(self,cursor):
        self.cursor=cursor
        self.lastrowid=cursor.lastrowid
        self.rowcount=cursor.rowcount
        self.names=[column[0] for column in (cursor.description or ())]
    def fetchone(self):
        row=self.cursor.fetchone()
        return dict(zip(self.names,row)) if row is not None else None
    def fetchall(self):return [dict(zip(self.names,row)) for row in self.cursor.fetchall()]

class DummyCursor:
    lastrowid = None
    rowcount = 0
    description = None
    def fetchone(self): return None
    def fetchall(self): return []

class Database:
    def __init__(self,url,token='',local_test=False):
        if not local_test and not url.startswith('libsql://'):
            raise RuntimeError('Use a Turso libSQL database URL (libsql://)')
        if not local_test and not token:raise RuntimeError('TURSO_AUTH_TOKEN is required')
        try:
            import libsql
            self.connection=libsql.connect(url,auth_token=token)
        except ImportError:
            if local_test:
                self.connection=sqlite3.connect(url)
            else:
                raise
        self.connection.execute('PRAGMA foreign_keys=ON')
    def execute(self,sql,args=()):
        if sql.strip().upper() in ('BEGIN', 'BEGIN IMMEDIATE', 'BEGIN TRANSACTION', 'BEGIN EXCLUSIVE'):
            try:
                return Result(self.connection.execute(sql,args))
            except Exception as exc:
                if 'cannot start a transaction within a transaction' in str(exc).lower():
                    return Result(DummyCursor())
                raise
        try:return Result(self.connection.execute(sql,args))
        except Exception as exc:
            # libSQL exposes ValueError for SQLite constraint errors.
            if any(word in str(exc).lower() for word in ('constraint failed','ledger entries are immutable','snapshots are immutable','audit entries are immutable')):
                raise sqlite3.IntegrityError('Database constraint failed') from exc
            raise
    def executemany(self,sql,params):return self.connection.executemany(sql,params)
    def commit(self):self.connection.commit()
    def rollback(self):self.connection.rollback()
    def close(self):
        try:self.connection.rollback()
        finally:self.connection.close()
