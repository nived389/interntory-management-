import io,zipfile
from test_workflows import clients,new_item
from test_access import login
import app as mod
from openpyxl import load_workbook

def test_multi_section_reports_and_pack(clients):
    m,s,p=clients
    ids=[new_item(m,p,sid) for sid in (1,4,6)]
    month=mod.date.today().isoformat()[:7];q=f'month={month}&sections=1,4'
    rr=m.get('/api/reports?'+q).json
    assert {r['id'] for r in rr}==set(ids[:2])
    rr=m.get('/api/reports?kind=purchases&'+q).json
    assert {r['section_id'] for r in rr}=={1,4}
    response=m.get('/api/export/monthly-pack?'+q+'&format=xlsx')
    assert response.status_code==200
    z=zipfile.ZipFile(io.BytesIO(response.data));assert len(z.namelist())==3
    sheet=load_workbook(io.BytesIO(z.read(f'inventory_{month}.xlsx'))).active
    sections=[r[7] for r in list(sheet.values)[3:]]
    assert set(sections)=={'Store','Games'}
    assert m.get('/api/export?kind=breakage&format=pdf&'+q).data.startswith(b'%PDF')
    assert m.get('/api/reports?sections=').status_code==400
    assert m.get('/api/reports?sections=999').status_code==403
    assert m.get('/api/reports?kind=breakage&month=invalid').status_code==400
    assert p(m,'/users',dict(name='Scoped',username='scoped',password='12345',role='ADMIN',permissions=['reports'],section_scope=[1])).status_code==200
    scoped=login('scoped','12345')
    assert scoped.get('/api/export/monthly-pack?'+q).status_code==403
    assert s.get('/api/export/monthly-pack?'+q).status_code==403
