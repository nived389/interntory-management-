import io,sqlite3,zipfile
from pathlib import Path
import pytest
from turso_database import Database
from turso_files import DDL,put,get,CHUNK_SIZE
from turso_backup import archive

@pytest.fixture
def database(tmp_path):
    db=Database(str(tmp_path/'test.db'),local_test=True)
    db.execute('CREATE TABLE items(id INTEGER PRIMARY KEY,name TEXT UNIQUE)')
    for sql in DDL:db.execute(sql)
    db.commit()
    yield db
    db.close()

def test_records_and_photos_share_rollback(database):
    database.execute('BEGIN IMMEDIATE')
    result=database.execute('INSERT INTO items(name) VALUES(?)',('Cup',))
    assert result.lastrowid==1
    put(database,'photos/a.webp',b'a'*(CHUNK_SIZE+10))
    assert get(database,'photos/a.webp')==b'a'*(CHUNK_SIZE+10)
    database.rollback()
    assert database.execute('SELECT * FROM items').fetchall()==[]
    with pytest.raises(FileNotFoundError):get(database,'photos/a.webp')

def test_constraints_and_restoreable_backup(database):
    database.execute('INSERT INTO items(name) VALUES(?)',('Cup',))
    put(database,'photos/a.webp',b'photo')
    database.commit()
    with pytest.raises(sqlite3.IntegrityError):database.execute('INSERT INTO items(name) VALUES(?)',('Cup',))
    database.rollback()
    buffer=io.BytesIO();archive(database,buffer)
    with zipfile.ZipFile(buffer) as z:
        assert z.read('photos/a.webp')==b'photo'
        assert z.read('inventory.db').startswith(b'SQLite format 3')

def test_file_corruption_detected(database):
    put(database,'photos/a.webp',b'photo')
    database.execute('UPDATE stored_file_chunks SET content=?',(b'wrong',))
    with pytest.raises(RuntimeError,match='integrity'):get(database,'photos/a.webp')

def test_no_token_or_wrong_engine_rejected():
    with pytest.raises(RuntimeError,match='libSQL'):Database('turso://example')
    with pytest.raises(RuntimeError,match='TOKEN'):Database('libsql://example')
