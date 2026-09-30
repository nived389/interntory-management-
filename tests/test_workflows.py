import os,tempfile,io,base64,uuid,json
os.environ['INVENTORY_DATA']=tempfile.mkdtemp(prefix='inventory-test-')
os.environ['INVENTORY_SKIP_OWNER_SEED']='1'
import pytest
from PIL import Image
import app as mod

@pytest.fixture()
def clients():
    with mod.app.app_context():
        # Fresh database per scenario, including immutable triggers.
        mod.db().close();mod.g.pop('db',None)
        (mod.DATA/'inventory.db').unlink(missing_ok=True)
    mod.init()
    master=mod.app.test_client(); staff=mod.app.test_client()
    def token(c): return c.get('/api/session').json['csrf']
    master.csrf=token(master)
    def post(c,p,d): return c.post('/api'+p,json=d,headers={'X-CSRF-Token':c.csrf})
    assert post(master,'/setup',{'name':'Owner','username':'traveliciousrestaurant@gmail.com','password':'test-password-123'}).status_code==200
    assert post(master,'/users',{'name':'Staff','username':'staff','password':'staff-password-123'}).status_code==200
    staff.csrf=token(staff); assert post(staff,'/login',{'username':'staff','password':'staff-password-123'}).status_code==200;staff.csrf=token(staff)
    return master,staff,post

def photo():
    b=io.BytesIO();Image.new('RGB',(20,20),'green').save(b,'PNG');return base64.b64encode(b.getvalue()).decode()
def new_item(c,p,section=1):
    res=p(c,'/items',{'name':'Test mug','specification':'Ceramic 200ml','section_id':section,'qty':10,'rate':'100.25','photo':photo()})
    assert res.status_code==200,res.json
    return res.json['id']
def move(c,p,i,**kw):return p(c,'/movements',dict(item_id=i,type='BREAKAGE',qty=2,photo=photo(),reason='Accidental drop / handling',request_id=str(uuid.uuid4()),**kw))

def test_permissions_and_validation(clients):
    m,s,p=clients;i=new_item(m,p)
    assert s.get('/api/items').status_code==403
    row=next(r for r in s.get('/api/item-options?purpose=breakage').json if r['id']==i)
    assert not any(k in row for k in ('rate','stock','expected','previous','difference'))
    for url in ['/api/reports','/api/users','/api/audit','/api/backup','/api/export','/api/history/1']:
        assert s.get(url).status_code==403
    assert p(s,'/sections',{'name':'Hack','property_id':1}).status_code==403
    assert m.post('/api/users',json={}).status_code==403
    assert p(s,'/movements',{'item_id':i,'type':'BREAKAGE','qty':100,'photo':photo(),'reason':'Other','note':'test','request_id':str(uuid.uuid4())}).status_code==400
    assert p(s,'/movements',{'item_id':i,'type':'BREAKAGE','qty':1,'reason':'Other','note':'test','request_id':str(uuid.uuid4())}).status_code==400
    assert len(m.get('/api/history/'+str(i)).json)==1

def test_idempotency_rate_snapshot_and_immutable_ledger(clients):
    m,s,p=clients;i=new_item(m,p);rid=str(uuid.uuid4())
    d={'item_id':i,'type':'BREAKAGE','qty':2,'photo':photo(),'reason':'Wear and tear','request_id':rid}
    a=p(s,'/movements',d);b=p(s,'/movements',d)
    assert a.status_code==b.status_code==200 and a.json==b.json
    assert m.patch('/api/items/'+str(i),json={'rate':'250'},headers={'X-CSRF-Token':m.csrf}).status_code==200
    assert len(m.get('/api/history/'+str(i)).json)==1
    assert p(m,'/reviews/'+str(a.json['reference']),{'action':'accept','revision':1}).status_code==200
    history=m.get('/api/history/'+str(i)).json;assert len(history)==2
    assert next(r for r in history if r['type']=='BREAKAGE')['rate']==10025
    with mod.app.app_context():
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):mod.db().execute('UPDATE movements SET qty=99')

def test_count_close_reopen_and_rollover(clients):
    m,s,p=clients;i=new_item(m,p);month=mod.date.today().isoformat()[:7]
    assert move(s,p,i).status_code==200
    path='/counts/1/'+month
    assert p(s,path,{'action':'submit'}).status_code==400
    assert p(s,path,{'action':'save','item_id':i,'actual':7}).status_code==200
    r=s.get('/api'+path).json['items'][0];assert r['actual']==7 and 'expected' not in r
    assert p(s,path,{'action':'close'}).status_code==403
    assert p(s,path,{'action':'submit'}).status_code==200
    assert move(s,p,i).status_code==409
    assert p(m,path,{'action':'close'}).status_code==409
    q=m.get('/api/reviews').json['submissions'][0]
    assert p(m,'/reviews/'+str(q['id']),{'action':'accept','revision':q['revision']}).status_code==200
    assert p(m,path,{'action':'close'}).status_code==200
    closed=m.get('/api'+path).json;assert closed['status']=='CLOSED';assert closed['items'][0]['difference']==-1
    archives=m.get('/api/archives').json;assert len(archives)==4
    assert m.get('/api/archives/'+str(archives[0]['id'])).status_code==200
    year,mo=map(int,month.split('-'));nextmonth=f'{year+(mo==12)}-{1 if mo==12 else mo+1:02}'
    with mod.app.app_context():assert mod.report(1,nextmonth)[0]['previous']==7
    assert p(m,path,{'action':'reopen'}).status_code==400
    assert p(m,path,{'action':'reopen','reason':'Recount with supervisor'}).status_code==200
    assert p(m,path,{'action':'save','item_id':i,'actual':8}).status_code==200
    assert p(m,path,{'action':'submit'}).status_code==200
    assert p(m,path,{'action':'close'}).status_code==200
    assert len(m.get('/api/archives').json)==8
    with mod.app.app_context(): assert len(mod.rows('SELECT * FROM snapshots'))==2

def test_exports_disable_and_backup(clients):
    m,s,p=clients;i=new_item(m,p)
    for kind in ('inventory','breakage','purchases','yearly'):
        for fmt in ('xlsx','pdf'):
            res=m.get(f'/api/export?kind={kind}&format={fmt}&month={mod.date.today().isoformat()[:7]}&section=1')
            assert res.status_code==200,res.json if res.is_json else res.data[:100]
            assert res.data.startswith(b'PK' if fmt=='xlsx' else b'%PDF')
    assert p(m,'/users',{'id':2,'active':False}).status_code==200
    assert s.get('/api/items').status_code==401
    assert m.get('/api/backup').data.startswith(b'PK')

def test_workbook_preview_commit(clients):
    from openpyxl import Workbook
    m,s,p=clients;w=Workbook();ws=w.active;ws.title='Cafe report';ws.append(['SI.NO','ITEM','PICTURE','PREV MONTH STOCK','NEW STOCK','DAMAGE','ACTUAL']);ws.append([1,'COFFEE MUG',None,0,0,0,12]);b=io.BytesIO();w.save(b);b.seek(0)
    preview=m.post('/api/import/preview',data={'file':(b,'source.xlsx')},headers={'X-CSRF-Token':m.csrf})
    assert preview.status_code==200,preview.json
    d=preview.json;assert len(d['items'])==1 and d['items'][0]['existing']
    assert p(m,'/import/commit',{'token':d['token'],'values':[{'qty':12,'rate':'150'}]}).status_code==200
    row=next(r for r in m.get('/api/items?section=3').json if r['name']=='COFFEE MUG');assert row['stock']==12
    assert p(m,'/import/commit',{'token':d['token'],'values':[{'qty':12,'rate':'150'}]}).status_code==400

def test_password_reset_revokes_sessions_and_login_lockout(clients):
    m,s,p=clients
    assert p(m,'/users',{'id':2,'password':'replacement-password-123'}).status_code==200
    assert s.get('/api/items').status_code==401
    assert s.get('/api/session').json['user'] is None
    s.csrf=s.get('/api/session').json['csrf']
    for _ in range(5): assert p(s,'/login',{'username':'unknown-account','password':'bad'}).status_code==401
    assert p(s,'/login',{'username':'unknown-account','password':'bad'}).status_code==429

def test_monthly_dashboard_metrics(clients):
    m,s,p=clients; i=new_item(m,p)
    cur_month=mod.date.today().isoformat()[:7]
    events_now=m.get(f'/api/events?month={cur_month}').json
    assert any(e['item_id']==i and e['type']=='OPENING' for e in events_now)
    events_past=m.get('/api/events?month=2026-01').json
    assert not any(e['item_id']==i for e in events_past)
    counts_now=m.get(f'/api/counts?month={cur_month}').json
    sec1=next(c for c in counts_now if c['id']==1)
    assert sec1['total']>=1
    counts_past=m.get('/api/counts?month=2026-01').json
    sec1_past=next(c for c in counts_past if c['id']==1)
    assert sec1_past['total']==0
