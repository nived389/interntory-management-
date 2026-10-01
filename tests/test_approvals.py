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


def test_approved_hidden_from_reviews_and_present_in_audit(clients):
    m,s,p=clients;i=new_item(m,p);res=send(s,p,i);qid=res.json['reference']
    assert len(m.get('/api/reviews').json['submissions'])==1
    assert p(m,f'/reviews/{qid}',{'action':'accept','revision':1}).status_code==200
    # Approved items must NOT appear in review inbox
    assert len(m.get('/api/reviews').json['submissions'])==0
    # But must appear in audit log
    audit_events=m.get('/api/audit').json
    assert any(a['action']=='SUBMISSION_ACCEPT' for a in audit_events)


def test_delete_submission_and_permissions(clients):
    m,s,p=clients;i=new_item(m,p);res=send(s,p,i);qid=res.json['reference']
    # Staff cannot delete submission
    assert s.delete(f'/api/reviews/{qid}',headers={'X-CSRF-Token':s.csrf}).status_code==403
    assert p(s,f'/reviews/{qid}',{'action':'delete'}).status_code==403
    # Master can delete submission
    del_res=m.delete(f'/api/reviews/{qid}',headers={'X-CSRF-Token':m.csrf})
    assert del_res.status_code==200 and del_res.json['ok']
    assert len(m.get('/api/reviews').json['submissions'])==0
    # Deletion logged in audit
    audit_events=m.get('/api/audit').json
    assert any(a['action']=='SUBMISSION_DELETED' for a in audit_events)


def test_zero_stock_breakage_can_be_reported_and_approved(clients):
    m,s,p=clients
    # Item with 0 opening stock
    res=p(m,'/items',{'name':'Zero Stock Mug','specification':'Ceramic','section_id':1,'qty':0,'rate':'50','photo':photo()})
    assert res.status_code==200
    iid=res.json['id']
    # Staff reports breakage of 1
    res=p(s,'/movements',{'item_id':iid,'type':'BREAKAGE','qty':1,'photo':photo(),'reason':'Dropped','note':'accident','request_id':str(uuid.uuid4())})
    assert res.status_code==200 and res.json['pending']
    qid=res.json['reference']
    # Master approves it
    assert p(m,f'/reviews/{qid}',{'action':'accept','revision':1}).status_code==200
    # Disappears from reviews
    assert len(m.get('/api/reviews').json['submissions'])==0


def test_master_can_edit_submission_spelling_count_rate_and_section(clients):
    m,s,p=clients
    # Staff submits a new item with typos: "Teapot cupp", qty 2, rate 45, section 1
    res=p(s,'/items',{'name':'Teapot cupp','specification':'Ceramic','section_id':1,'qty':2,'rate':'45.00','photo':photo()})
    assert res.status_code==200 and res.json['pending']
    qid=res.json['reference']

    # Staff cannot edit via admin edit action
    assert p(s,f'/reviews/{qid}',{'action':'edit','name':'Hacked'}).status_code==403

    # Master edits submission: fixes spelling to "Teapot Cup", changes count to 5, rate to 55, section to 2
    edit_res=p(m,f'/reviews/{qid}',{'action':'edit','name':'Teapot Cup','qty':5,'rate':'55.00','section_id':2})
    assert edit_res.status_code==200 and edit_res.json['ok']

    # Check that inbox reflects the edits immediately
    sub=m.get('/api/reviews').json['submissions'][0]
    assert sub['section_id']==2
    assert sub['payload']['name']=='Teapot Cup'
    assert sub['payload']['qty']==5
    assert sub['payload']['rate']==5500

    # Audit log records the edit
    audit_events=m.get('/api/audit').json
    assert any(a['action']=='SUBMISSION_EDITED' for a in audit_events)

    # Master approves the edited submission
    assert p(m,f'/reviews/{qid}',{'action':'accept','revision':1}).status_code==200

    # Item is created in section 2 with corrected name, qty 5, and rate 55
    items=m.get('/api/items').json
    created=next(i for i in items if i['name']=='Teapot Cup')
    assert created['section_id']==2
    assert created['stock']==5
    assert created['rate']==5500


def test_in_progress_count_automatically_pushed_to_reviews_inbox(clients):
    m,s,p=clients;i=new_item(m,p);month=mod.date.today().isoformat()[:7];path='/counts/1/'+month
    # Initially no counts in progress or submitted
    initial_counts=[c for c in m.get('/api/reviews').json['counts'] if c['section_id']==1 and c['month']==month]
    assert len(initial_counts)==0

    # Staff saves a count for item i (marking it done)
    assert p(s,path,{'action':'save','item_id':i,'actual':10}).status_code==200

    # Automatically visible in review inbox under counts!
    rev_counts=[c for c in m.get('/api/reviews').json['counts'] if c['section_id']==1 and c['month']==month]
    assert len(rev_counts)==1
    assert rev_counts[0]['status']=='IN PROGRESS'
    assert rev_counts[0]['counted_count']==1
    assert rev_counts[0]['submitted_by']==2

    # Master can close the count directly since all items are counted
    assert p(m,path,{'action':'close'}).status_code==200



