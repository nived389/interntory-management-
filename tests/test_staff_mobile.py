import uuid
from test_workflows import clients,new_item,photo
from test_access import login
import app as mod

def test_private_full_list_corrections_and_atomic_acceptance(clients):
    m,s,p=clients;i=new_item(m,p)
    ids=[]
    for qty in (2,3):
        res=p(s,'/movements',dict(type='PURCHASE',item_id=i,qty=qty,request_id=str(uuid.uuid4())))
        ids.append(res.json['reference'])
    entries=[dict(id=i,revision=1) for i in ids]
    assert p(m,'/reviews/list',dict(action='return',entries=entries,marked=[ids[0]],feedback='Check invoice')).status_code==200
    inbox=s.get('/api/corrections').json['submissions'];assert len(inbox)==2
    group=inbox[0]['correction_group'];assert group
    assert p(s,'/corrections/'+str(ids[1]),dict(action='resubmit',qty=100,note='changed')).status_code==403
    assert p(s,f'/corrections/list/{group}/submit',{}).status_code==409
    assert p(m,'/users',dict(name='Other',username='other',password='12345')).status_code==200
    other=login('other','12345')
    assert other.get('/api/corrections').json['submissions']==[]
    assert p(other,'/corrections/'+str(ids[0]),dict(action='resubmit',qty=4)).status_code==403
    assert p(other,f'/corrections/list/{group}/submit',{}).status_code==404
    assert p(s,'/corrections/'+str(ids[0]),dict(action='resubmit',qty=4,note='Verified invoice')).status_code==200
    assert p(s,f'/corrections/list/{group}/submit',{}).status_code==200
    assert s.get('/api/corrections').json['submissions']==[]
    rows=m.get('/api/reviews').json['submissions'];entries=[dict(id=r['id'],revision=r['revision']) for r in rows]
    assert p(m,'/reviews/list',dict(action='accept',entries=entries)).status_code==200
    assert next(r for r in m.get('/api/items').json if r['id']==i)['stock']==17
    assert p(m,'/reviews/list',dict(action='accept',entries=entries)).status_code==409

def test_staff_and_full_admin_cannot_review_or_export(clients):
    m,s,p=clients
    assert p(m,'/users',dict(name='Admin',username='admin',password='12345',role='ADMIN',full_access=True)).status_code==200
    admin=login('admin','12345')
    assert admin.get('/api/items').status_code==200
    for c in (s,admin):
        for path in ('/reviews','/reports','/export','/export/monthly-pack','/archives','/backup'):
            assert c.get('/api'+path).status_code==403,path
    assert s.get('/api/items').status_code==403

def test_monthly_count_file_private_and_multi_flag(clients):
    m,s,p=clients;i=new_item(m,p);j=new_item(m,p);month=mod.date.today().isoformat()[:7];path='/counts/1/'+month
    for iid in (i,j):assert p(s,path,dict(action='save',item_id=iid,actual=10)).status_code==200
    assert p(s,path,dict(action='submit')).status_code==200
    assert p(m,path,dict(action='return',item_ids=[i,j],reason='Please recount both')).status_code==200
    assert p(m,'/users',dict(name='Other',username='other',password='12345')).status_code==200
    other=login('other','12345')
    assert other.get('/api'+path).status_code==403
    assert not any(r['id']==1 for r in other.get('/api/counts?month='+month).json)
    assert other.get('/api/corrections').json['counts']==[]
    assert len(s.get('/api'+path).json['items'])==2
    assert all(r['needs_correction']==1 for r in s.get('/api'+path).json['items'])


def test_full_list_acceptance_rolls_back_if_total_exceeds_stock(clients):
    m,s,p=clients;i=new_item(m,p)
    entries=[]
    for _ in range(2):
        res=p(s,'/movements',dict(type='BREAKAGE',item_id=i,qty=6,reason='Broken',photo=photo(),request_id=str(uuid.uuid4())))
        assert res.status_code==200
        entries.append(dict(id=res.json['reference'],revision=1))
    assert p(m,'/reviews/list',dict(action='accept',entries=entries)).status_code==400
    assert next(r for r in m.get('/api/items').json if r['id']==i)['stock']==10
    assert all(r['status']=='PENDING' for r in m.get('/api/reviews').json['submissions'])
    assert len(m.get(f'/api/history/{i}').json)==1


def test_automatic_month_blind_complete_section_and_old_corrections(clients):
    m,s,p=clients;i=new_item(m,p);j=new_item(m,p);current=mod.date.today().isoformat()[:7]
    old=(mod.date.today().replace(day=1)-mod.timedelta(days=1)).isoformat()[:7]
    assert s.get('/api/counts?month='+old).status_code==403
    assert p(s,'/counts/1/'+old,dict(action='save',item_id=i,actual=10)).status_code==403
    path='/counts/1/'+current
    data=s.get('/api'+path).json
    assert {r['id'] for r in data['items']}=={i,j}
    for r in data['items']:
        assert not set(r)&{'stock','expected','previous','rate','difference','added','damage'}
        assert r['actual'] is None
    assert p(s,path,dict(action='save',item_id=i,actual=8)).status_code==200
    assert p(s,path,dict(action='submit')).status_code==400
    assert p(s,path,dict(action='save',item_id=j,actual=10)).status_code==200
    assert p(s,path,dict(action='submit')).status_code==200
    assert p(m,path,dict(action='return',item_ids=[i],reason='Recount')).status_code==200
    # Simulate month rollover: a returned file keeps its original month and author.
    with mod.app.app_context():
        mod.db().execute('UPDATE counts SET month=? WHERE section_id=1',(old,))
        mod.db().execute('UPDATE items SET created=? WHERE id IN (?,?)',(old+'-01T00:00:00',i,j));mod.db().commit()
    assert len(s.get('/api/counts/1/'+old).json['items'])==2
    assert p(s,'/counts/1/'+old,dict(action='save',item_id=i,actual=9)).status_code==200
    assert p(s,'/counts/1/'+old,dict(action='submit')).status_code==200


def test_unassigned_lists_visible_and_master_can_share(clients):
    m,s,p=clients;i=new_item(m,p);month=mod.date.today().isoformat()[:7];path='/counts/1/'+month
    with mod.app.app_context():
        cid=mod.db().execute("INSERT INTO counts(section_id,month,status) VALUES(1,?,'IN PROGRESS')",(month,)).lastrowid
        mod.db().execute('INSERT INTO lines(count_id,item_id,actual) VALUES(?,?,77)',(cid,i));mod.db().commit()
    assert any(r['id']==1 for r in s.get('/api/counts?month='+month).json)
    assert s.get('/api'+path).json['items'][0]['actual'] is None
    assert p(m,path,dict(action='share',staff_id=2)).status_code==200
    assert s.get('/api'+path).json['submitter']['id']==2
    assert p(s,path,dict(action='save',item_id=i,actual=8)).status_code==200
    assert p(s,path,dict(action='submit')).status_code==200
    assert p(m,path,dict(action='share',staff_id=2)).status_code==409
