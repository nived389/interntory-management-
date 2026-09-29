import uuid
from test_workflows import clients,new_item,photo
from test_access import login
import app as mod

def stock(m,i):return next(r['stock'] for r in m.get('/api/items').json if r['id']==i)
def send(s,p,i,typ='PURCHASE',qty=3):
    return p(s,'/movements',dict(item_id=i,type=typ,qty=qty,photo=photo(),reason='Dropped item',request_id=str(uuid.uuid4())))

def test_return_correct_accept_idempotency_and_identity(clients):
    m,s,p=clients;i=new_item(m,p);res=send(s,p,i);qid=res.json['reference'];path=f'/reviews/{qid}'
    assert stock(m,i)==10
    q=m.get('/api/reviews').json['submissions'][0];assert q['username']=='staff' and q['actor']==2
    assert p(s,path,{'action':'accept','revision':1}).status_code==403
    assert p(m,path,{'action':'return','revision':1,'feedback':'Quantity on invoice is 4'}).status_code==200
    assert p(m,path,{'action':'resubmit','qty':4}).status_code==403
    assert p(s,path,{'action':'resubmit','qty':4,'note':'Rechecked invoice'}).status_code==200
    assert p(m,path,{'action':'accept','revision':1}).status_code==409
    assert stock(m,i)==10
    assert p(m,path,{'action':'accept','revision':2}).status_code==200
    assert p(m,path,{'action':'accept','revision':2}).status_code==200
    assert stock(m,i)==14
    assert m.get('/api/history/'+str(i)).json[0]['actor']==2
    assert p(s,path,{'action':'resubmit','qty':99}).status_code==409

def test_count_flag_correction_and_unexplained_difference(clients):
    m,s,p=clients;i=new_item(m,p);j=new_item(m,p);month=mod.date.today().isoformat()[:7];path='/counts/1/'+month
    for iid,n in ((i,8),(j,12)):assert p(s,path,{'action':'save','item_id':iid,'actual':n}).status_code==200
    assert p(s,path,{'action':'submit'}).status_code==200
    data=m.get('/api'+path).json
    assert data['submitter']['username']=='staff'
    assert {r['difference'] for r in data['items']}=={-2,2}
    assert p(m,path,{'action':'return','item_id':i,'reason':'Recount shelf'}).status_code==200
    assert p(m,path,{'action':'close'}).status_code==400
    assert p(s,path,{'action':'save','item_id':j,'actual':99}).status_code==409
    assert p(s,path,{'action':'submit'}).status_code==409
    assert p(s,path,{'action':'save','item_id':i,'actual':10,'note':'Found on shelf'}).status_code==200
    assert p(s,path,{'action':'submit'}).status_code==200
    assert p(m,path,{'action':'close'}).status_code==200
    assert m.get('/api'+path).json['items'][0]['submitted_by']=='staff'

def test_scoped_reviews_and_staff_permissions_cannot_approve(clients):
    m,s,p=clients;i=new_item(m,p,1);send(s,p,i)
    assert p(m,'/users',dict(name='Other',username='other',password='12345')).status_code==200
    other=login('other','12345');assert other.get('/api/corrections').json['submissions']==[]
    assert p(m,'/users',dict(name='Reviewer',username='reviewer',password='12345',role='ADMIN',permissions=['review_counts'],section_scope=[3])).status_code==200
    reviewer=login('reviewer','12345');assert reviewer.get('/api/reviews').status_code==403
    assert p(reviewer,'/reviews/1',{'action':'accept','revision':1}).status_code==403
    assert p(m,'/users',{'id':2,'permissions':['review_counts','counts']}).status_code==200
    s=login('staff');assert s.get('/api/reviews').status_code==403
    assert p(s,'/reviews/1',{'action':'accept','revision':1}).status_code==403

def test_staff_new_item_stock_requires_approval(clients):
    m,s,p=clients
    before=len(m.get('/api/items').json)
    res=p(s,'/items',{'name':'Pending mug','specification':'Ceramic','section_id':1,'qty':10,'photo':photo()})
    assert res.status_code==200 and res.json['pending']
    assert len(m.get('/api/items').json)==before
    q=m.get('/api/reviews').json['submissions'][0]
    assert q['payload']['type']=='NEW_ITEM'
    assert p(m,f"/reviews/{q['id']}",{'action':'accept','revision':1}).status_code==200
    items=m.get('/api/items').json
    assert len(items)==before+1
    assert next(r for r in items if r['name']=='Pending mug')['stock']==10


def test_next_month_40_baseline_variance(clients):
    m,s,p=clients;i=new_item(m,p);month=mod.date.today().isoformat()[:7];path='/counts/1/'+month
    assert p(s,path,{'action':'save','item_id':i,'actual':40}).status_code==200
    assert p(s,path,{'action':'submit'}).status_code==200
    assert p(m,path,{'action':'close'}).status_code==200
    year,mo=map(int,month.split('-'));following=f'{year+(mo==12)}-{1 if mo==12 else mo+1:02}'
    with mod.app.app_context():
        cid=mod.db().execute('INSERT INTO counts(section_id,month) VALUES(?,?)',(1,following)).lastrowid
        mod.db().execute('INSERT INTO lines(count_id,item_id,actual) VALUES(?,?,?)',(cid,i,38))
        r=mod.report(1,following)[0]
        assert (r['previous'],r['expected'],r['actual'],r['difference'])==(40,40,38,-2)
        mod.db().execute('UPDATE lines SET actual=43 WHERE count_id=?',(cid,))
        r=mod.report(1,following)[0];assert r['difference']==3
        mod.db().commit()
