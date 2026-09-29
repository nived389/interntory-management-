"""Central authorization policy. Every endpoint and record scope is enforced server-side."""
import json
from flask import g

OWNER_EMAIL='traveliciousrestaurant@gmail.com'
PERMISSIONS={
 'inventory':'View item catalogue', 'add_items':'Create items', 'edit_items':'Edit / archive items',
 'purchases':'Receive stock / purchases', 'breakage':'Report breakage / damage',
 'counts':'Enter and submit physical counts', 'view_totals':'View stock, rates and financial totals',
 'review_counts':'Review, close and reopen months', 'adjustments':'Adjust stock / backdate transactions',
 'reports':'View and download reports / archived files', 'users':'Manage staff accounts and access',
}
DEFAULT_STAFF=['add_items','purchases','breakage','counts']
STAFF_ACTIONS=set(DEFAULT_STAFF)
GLOBAL_PERMISSIONS=['settings','audit','backups','import']
ALL_PERMISSIONS=list(PERMISSIONS)+GLOBAL_PERMISSIONS

def full(user=None):
    user=user or g.user
    return user.get('access_role',user.get('role'))=='MASTER' or (user.get('access_role')=='ADMIN' and bool(user.get('full_access')))
def owner(user=None):
    user=user or g.user
    return user.get('access_role',user.get('role'))=='MASTER' and user.get('username','').lower()==OWNER_EMAIL

def permissions(user=None):
    user=user or g.user
    if owner(user): return ALL_PERMISSIONS
    try: granted=set(ALL_PERMISSIONS if full(user) else json.loads(user.get('permissions') or '[]'))
    except (ValueError,TypeError): granted=set()
    if user.get('access_role',user.get('role'))=='STAFF': return sorted(granted & STAFF_ACTIONS)
    return sorted(granted-{'users','reports','review_counts','backups','import'})
def can(permission,user=None): return permission in permissions(user)
def scopes(user=None):
    user=user or g.user
    if full(user) or user.get('section_scope') is None: return None
    try: return json.loads(user['section_scope'])
    except (ValueError,TypeError): return []
def allows(sid,user=None):
    selected=scopes(user)
    return selected is None or int(sid) in selected
def public_user(u):
    return {k:u.get(k) for k in ('id','name','username','active','login_provider')} | {'role':u.get('access_role') or u['role'],'full_access':full(u),'permissions':permissions(u),'section_scope':scopes(u),'is_owner':owner(u)}

def policy(endpoint,method,data):
    """Permission alternatives; a tuple means any one suffices. None is authentication only."""
    fixed={'items':('inventory',),'create_item':('add_items',),'edit_item':('edit_items',),
           'history':('view_totals',),'counts':('counts','review_counts'),'count_detail':('counts','review_counts'),
           'events':('inventory','breakage','purchases','reports'),'reports':('reports',),'export':('reports',),
           'archives':('reports',),'archive_file':('reports',),'users':('users',),'user_write':('users',),
           'section_write':('settings',),'audit_list':('audit',),'backup':('backups',),
           'preview':('import',),'commit':('import',)}
    if endpoint=='movement': return ({'PURCHASE':'purchases','BREAKAGE':'breakage','DAMAGE':'breakage','ADJUSTMENT':'adjustments'}.get(data.get('type'),'invalid'),)
    if endpoint=='count_action': return ('review_counts',) if data.get('action') in ('close','reopen','return','share') else ('counts',)
    return fixed.get(endpoint)

def validate_assignment(a,actor,target,d):
    """Only full admins can delegate admin powers; restricted admins can grant subsets to staff."""
    role=d.get('role',target.get('access_role','STAFF') if target else 'STAFF')
    if role not in ('STAFF','ADMIN'): a.fail('Choose Staff or Admin. The Master account is reserved.')
    raw=d.get('permissions',json.loads(target.get('permissions') or '[]') if target else DEFAULT_STAFF)
    if not isinstance(raw,list) or any(not isinstance(v,str) or v not in PERMISSIONS for v in raw): a.fail('Select valid permissions.')
    requested_full=d.get('full_access',bool(target.get('full_access')) if target else False)
    if not isinstance(requested_full,bool): a.fail('Full access must be true or false.')
    if role=='STAFF' and requested_full: a.fail('Only an Admin may have full access.')
    selected=d.get('section_scope',scopes(target) if target else scopes(actor))
    if selected is not None:
        if not isinstance(selected,list) or any(type(v) is not int for v in selected): a.fail('Choose valid sections.')
        valid={r['id'] for r in a.rows('SELECT id FROM sections')}
        if not set(selected)<=valid: a.fail('A selected section does not exist.')
        selected=sorted(set(selected))
    # Finance-bearing features are explicit, coherent grants rather than indirect data leaks.
    chosen=set(raw)
    if chosen & {'reports','review_counts','adjustments','edit_items'}: chosen.add('view_totals')
    if chosen & {'add_items','purchases','breakage','counts','edit_items','adjustments'}: chosen.add('inventory')
    if role=='STAFF': chosen &= STAFF_ACTIONS
    else: chosen -= {'users','reports','review_counts','backups','import'}
    if role=='STAFF' and 'users' in chosen: a.fail('Only an Admin may manage staff accounts.')
    if not full(actor):
        if role!='STAFF' or requested_full or (target and target.get('access_role')!='STAFF'): a.fail('Only a full-access Admin can manage Admin accounts.',403)
        if not chosen<=set(permissions(actor)): a.fail('You cannot grant permissions beyond your own access.',403)
        allowed=scopes(actor)
        if allowed is not None and (selected is None or not set(selected)<=set(allowed)): a.fail('You cannot grant sections outside your own access.',403)
        if target and (scopes(target) is None or not set(scopes(target))<=set(allowed or scopes(target))) and allowed is not None: a.fail('This staff account has access outside your management scope.',403)
    return role,requested_full,sorted(chosen),selected
