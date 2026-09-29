from datetime import timedelta
import uuid
from test_workflows import clients,new_item,photo
import app as mod

def payload(i,**extra):
    return dict(item_id=i,section_id=1,type='BREAKAGE',qty=2,reason='Dropped while clearing the dining table.',photo=photo(),request_id=str(uuid.uuid4()),**extra)

def test_breakage_reason_today_and_atomic_notification(clients):
    m,s,p=clients;i=new_item(m,p)
    data=payload(i);res=p(s,'/movements',data);assert res.status_code==200,res.json
    assert p(s,'/movements',data).json==res.json
    assert len(m.get('/api/history/'+str(i)).json)==1
    assert len(m.get('/api/reviews').json['submissions'])==1
    assert p(m,'/reviews/'+str(res.json['reference']),{'action':'accept','revision':1}).status_code==200
    inbox=m.get('/api/notifications').json
    assert inbox['unread']==1 and len(inbox['items'])==1
    n=inbox['items'][0];assert n['reason']==data['reason'] and n['staff']=='Staff' and n['date']==mod.date.today().isoformat()
    assert n['reference'] is not None
    assert s.get('/api/notifications').json=={'items':[],'unread':0}
    assert p(s,'/notifications/'+str(n['id'])+'/read',{}).status_code==404
    assert p(m,'/notifications/'+str(n['id'])+'/read',{}).status_code==200
    assert p(m,'/notifications/'+str(n['id'])+'/read',{}).status_code==200
    assert m.get('/api/notifications').json['unread']==0
    assert len(m.get('/api/history/'+str(i)).json)==2

def test_past_dates_denied_even_with_adjustment_permission(clients):
    m,s,p=clients;i=new_item(m,p)
    yesterday=(mod.date.today()-timedelta(days=1)).isoformat()
    assert p(s,'/movements',payload(i,date=yesterday)).status_code==400
    assert p(m,'/movements',payload(i,date=yesterday)).status_code==400
    for reason in ('', '  ', 'x'*2001):
        d=payload(i);d['reason']=reason
        assert p(s,'/movements',d).status_code==400
    d=payload(i);d['section_id']=6
    assert p(s,'/movements',d).status_code==400
    d=payload(i);d['photo']=None
    assert p(s,'/movements',d).status_code==400
    assert m.get('/api/notifications').json['items']==[]
    assert len(m.get('/api/history/'+str(i)).json)==1

def test_notification_failure_rolls_back_stock(clients):
    m,s,p=clients;i=new_item(m,p)
    with mod.app.app_context():
        mod.db().executescript("CREATE TRIGGER fail_notifications BEFORE INSERT ON notifications BEGIN SELECT RAISE(ABORT,'notification write failed'); END;")
    res=p(s,'/movements',payload(i));assert res.status_code==200
    assert p(m,'/reviews/'+str(res.json['reference']),{'action':'accept','revision':1}).status_code==409
    assert m.get('/api/reviews').json['submissions'][0]['status']=='PENDING'
    assert len(m.get('/api/history/'+str(i)).json)==1
    assert m.get('/api/notifications').json['unread']==0
    with mod.app.app_context():mod.db().execute('DROP TRIGGER fail_notifications');mod.db().commit()
