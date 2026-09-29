import json,uuid
import pytest
from test_workflows import clients,new_item,photo
import app as mod
import access

def login(username,password='staff-password-123'):
    c=mod.app.test_client();c.csrf=c.get('/api/session').json['csrf']
    r=c.post('/api/login',json={'username':username,'password':password},headers={'X-CSRF-Token':c.csrf});assert r.status_code==200,r.json
    c.csrf=c.get('/api/session').json['csrf'];return c

def test_staff_scopes_and_revocation(clients):
    m,s,p=clients;i=new_item(m,p,section=1);j=new_item(m,p,section=6)
    month=mod.date.today().isoformat()[:7]
    assert p(m,'/users',{'id':2,'permissions':['inventory','counts'],'section_scope':[1]}).status_code==200
    assert s.get('/api/items').status_code==401
    s=login('staff');context=s.get('/api/context').json
    assert [r['id'] for r in context['sections']]==[1]
    assert [r['id'] for r in context['properties']]==[1]
    assert {r['section_id'] for r in s.get('/api/item-options?purpose=counts').json}=={1}
    assert s.get('/api/items').status_code==403
    assert s.get('/api/counts/6/'+month).status_code==403
    assert p(s,'/counts/6/'+month,{'action':'save','item_id':j,'actual':8}).status_code==403
    assert p(s,'/items',{'section_id':1,'name':'Denied','specification':'x','photo':photo()}).status_code==403
    assert p(s,'/movements',{'item_id':i,'type':'PURCHASE','qty':1,'request_id':str(uuid.uuid4())}).status_code==403
    mine=next(r for r in m.get('/api/items').json if r['id']==i)
    other=next(r for r in m.get('/api/items').json if r['id']==j)
    assert s.get('/photo/'+mine['photo']).status_code==200
    assert s.get('/photo/'+other['photo']).status_code==403
    assert s.get('/photo/thumb-'+other['photo']).status_code==403
    assert 'rate' not in s.get('/api/item-options?purpose=counts').json[0]
    # A count-only user has no catalogue read, but still sees scoped count metadata.
    assert p(m,'/users',{'id':2,'permissions':[],'section_scope':[]}).status_code==200
    s=login('staff');assert s.get('/api/items').status_code==403
    assert s.get('/api/context').json['sections']==[]

def test_only_main_admin_manages_members(clients):
    m,s,p=clients
    assert p(m,'/users',{'name':'Full admin','username':'admin','password':'staff-password-123','role':'ADMIN','full_access':True}).status_code==200
    admin=login('admin')
    assert admin.get('/api/session').json['user']['full_access'] is True
    assert admin.get('/api/users').status_code==403
    assert p(admin,'/users',{'name':'Blocked','username':'blocked','password':'12345'}).status_code==403
    assert p(admin,'/users',{'id':2,'password':'12345'}).status_code==403
    assert p(admin,'/users',{'id':2,'permissions':[]}).status_code==403
    assert p(admin,'/users/2/password/reveal',{}).status_code==403
    assert admin.get('/api/audit').status_code==200
    assert p(m,'/users',{'id':1,'active':False}).status_code==403

def test_scoped_reports_and_archive_downloads(clients):
    m,s,p=clients;i=new_item(m,p,1);j=new_item(m,p,6);month=mod.date.today().isoformat()[:7]
    for sid,iid in [(1,i),(6,j)]:
        for d in [{'action':'save','item_id':iid,'actual':10},{'action':'submit'},{'action':'close'}]: assert p(m,f'/counts/{sid}/{month}',d).status_code==200
    assert p(m,'/users',{'id':2,'permissions':['inventory','reports'],'section_scope':[1]}).status_code==200
    s=login('staff');assert s.get('/api/reports').status_code==403
    assert s.get('/api/archives').status_code==403
    other=next(r for r in m.get('/api/archives').json if r['section_id']==6)
    assert s.get('/api/archives/'+str(other['id'])).status_code==403
    assert s.get('/api/history/'+str(j)).status_code==403
    assert s.get('/api/reports?section=6').status_code==403
    assert s.get('/api/export?section=1&format=xlsx').status_code==403


def test_password_access_edits_survive_restart(clients):
    m,s,p=clients
    assert p(m,'/users',{'id':2,'username':'new-staff-name','password':'new-staff-password-123','permissions':['counts'],'section_scope':[3]}).status_code==200
    mod.init()
    c=login('new-staff-name','new-staff-password-123')
    assert c.get('/api/session').json['user']['section_scope']==[3]
    assert c.get('/api/session').json['user']['permissions']==['counts']
    assert s.get('/api/items').status_code==401
    info=mod.app.test_client().get('/api/session').json
    assert 'owner_email' not in info and info['setup'] is False


def test_five_character_password_and_owner_reveal(clients):
    m,s,p=clients
    base={'name':'Short staff','username':'x','password':'12345','role':'STAFF'}
    for password in ('','1234'):
        assert p(m,'/users',{**base,'password':password}).status_code==400
    assert p(m,'/users',base).status_code==200
    c=login('x','12345');uid=c.get('/api/session').json['user']['id']
    assert p(c,f'/users/{uid}/password/reveal',{}).status_code==403
    assert p(m,f'/users/{uid}/password/reveal',{}).json['password']=='12345'
    assert p(m,'/users',{'id':uid,'password':'abcde'}).status_code==200
    login('x','abcde')
    assert p(m,f'/users/{uid}/password/reveal',{}).json['password']=='abcde'
    c=login('x','abcde')
    assert p(c,'/password',{'current':'abcde','password':'vwxyz'}).status_code==403
    with mod.app.app_context():
        u=mod.one('SELECT * FROM users WHERE id=?',(uid,))
        assert u['password_encrypted']!='abcde' and u['password']!='abcde'
        audit=str(mod.rows('SELECT detail FROM audit'))
        assert 'abcde' not in audit and '12345' not in audit
    public=m.get('/api/users').json
    assert all('password' not in u and 'password_encrypted' not in u for u in public)
    assert p(m,'/users/1/password/reveal',{}).json['reset_required'] is True


def test_admin_section_transfer(clients):
    m,s,p=clients
    iid=new_item(m,p,section=2)
    original=next(i for i in m.get('/api/items').json if i['id']==iid)
    assert p(s,f'/items/{iid}/move',{'section_id':3}).status_code==403
    assert p(m,'/users',{'id':2,'permissions':['edit_items'],'section_scope':None}).status_code==200
    s=login('staff')
    assert p(s,f'/items/{iid}/move',{'section_id':3}).status_code==403
    result=p(m,f'/items/{iid}/move',{'section_id':3})
    assert result.status_code==200,result.json
    items=m.get('/api/items').json
    assert not any(i['id']==iid for i in items)
    moved=next(i for i in items if i['id']==result.json['id'])
    assert moved['section_id']==3
    assert moved['stock']==original['stock']
    assert moved['photo']==original['photo']
    assert moved['name']==original['name']
    assert m.get(f'/api/history/{iid}').status_code==200
    assert p(m,f'/items/{iid}/move',{'section_id':4}).status_code==404
