import pytest
from cloud_database import translate
import cloud_files

def test_sqlite_query_compatibility():
    sql,returns=translate('INSERT OR IGNORE INTO counts(section_id,month) VALUES(?,?)')
    assert sql=='INSERT INTO counts(section_id,month) VALUES(%s,%s) ON CONFLICT DO NOTHING RETURNING id'
    assert returns
    sql,_=translate("SELECT id FROM submissions WHERE substr(json_extract(payload,'$.date'),1,7)<=? AND status IN ('PENDING','RETURNED')")
    assert "substr((payload::jsonb ->> 'date'),1,7)<=%s" in sql
    sql,_=translate("SELECT * FROM items WHERE name LIKE ? ORDER BY name COLLATE NOCASE")
    assert 'ILIKE %s ORDER BY lower(name)' in sql
    assert translate("SELECT '?' literal WHERE name=?")[0]=="SELECT '?' literal WHERE name=%s"

def test_private_upload_failure_is_not_silent(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','configured')
    monkeypatch.setenv('SUPABASE_URL','https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_SECRET_KEY','test-only')
    (tmp_path/'photos').mkdir();(tmp_path/'photos'/'a.webp').write_bytes(b'photo')
    class Response: ok=False;status_code=403
    monkeypatch.setattr(cloud_files.requests,'request',lambda *a,**kw:Response())
    with pytest.raises(RuntimeError,match='HTTP 403'):cloud_files.upload(tmp_path,'photos/a.webp')

def test_private_download_caches_file(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','configured')
    monkeypatch.setenv('SUPABASE_URL','https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_SECRET_KEY','test-only')
    calls=[]
    class Response:ok=True;content=b'photo'
    def request(*args,**kwargs):calls.append((args,kwargs));return Response()
    monkeypatch.setattr(cloud_files.requests,'request',request)
    assert cloud_files.local(tmp_path,'photos/a.webp').read_bytes()==b'photo'
    cloud_files.local(tmp_path,'photos/a.webp')
    assert len(calls)==1
    assert '/object/authenticated/inventory-private/photos/a.webp' in calls[0][0][1]
