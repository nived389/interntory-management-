import os, json, sqlite3, secrets, uuid, io, base64, hashlib, time, re, copy
from pathlib import Path
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Flask, request, jsonify, session, g, send_file, abort, has_request_context
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps, UnidentifiedImageError
import access
import credential_vault
import cloud_files

ROOT=Path(__file__).parent
DATA=Path(os.environ.get('INVENTORY_DATA', ROOT/'data')); DATA.mkdir(exist_ok=True,parents=True)
for folder in ('photos','reports'): (DATA/folder).mkdir(exist_ok=True)
if not os.environ.get('TURSO_DATABASE_URL') and os.environ.get('INVENTORY_SKIP_OWNER_SEED') != '1':
    _conn_file = DATA / 'turso-connection.json'
    if _conn_file.is_file():
        try:
            _t_cfg = json.loads(_conn_file.read_text())
            if _t_cfg.get('TURSO_DATABASE_URL') and _t_cfg.get('TURSO_AUTH_TOKEN'):
                os.environ['TURSO_DATABASE_URL'] = _t_cfg['TURSO_DATABASE_URL']
                os.environ['TURSO_AUTH_TOKEN'] = _t_cfg['TURSO_AUTH_TOKEN']
        except Exception:
            pass
secret=DATA/'session.key'
if not os.environ.get('SESSION_SECRET') and not secret.exists(): secret.write_text(secrets.token_hex(32)); secret.chmod(0o600)
app=Flask(__name__,static_folder='static')
app.config.update(SECRET_KEY=os.environ.get('SESSION_SECRET') or secret.read_text(),MAX_CONTENT_LENGTH=150*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.environ.get('HTTPS')=='1',PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
failures={}
REASONS=['Accidental drop / handling','Staff handling damage','Guest-related damage','Wear and tear','Kitchen / service operation','Missing / unable to locate','Unknown','Other']
def now(): return datetime.now().isoformat(timespec='seconds')
_SHARED_TURSO_DB = None
REPORT_CACHE = {}

def invalidate_report_cache():
    REPORT_CACHE.clear()

class DBWrapper:
    def __init__(self, conn):
        self._conn = conn
    def execute(self, sql, args=()):
        first_word = sql.strip().split(None, 1)[0].upper() if sql and sql.strip() else ''
        if first_word in ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER'):
            invalidate_report_cache()
        return self._conn.execute(sql, args)
    def executemany(self, sql, params):
        invalidate_report_cache()
        return self._conn.executemany(sql, params)
    def executescript(self, sql):
        invalidate_report_cache()
        return self._conn.executescript(sql)
    def commit(self):
        res = self._conn.commit()
        invalidate_report_cache()
        return res
    def rollback(self):
        res = self._conn.rollback()
        invalidate_report_cache()
        return res
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def __setattr__(self, name, value):
        if name == '_conn':
            super().__setattr__(name, value)
        else:
            setattr(self._conn, name, value)

def db():
    if 'db' not in g:
        if os.environ.get('TURSO_DATABASE_URL'):
            if os.environ.get('DATABASE_URL'): raise RuntimeError('Configure only one cloud database provider')
            global _SHARED_TURSO_DB
            if _SHARED_TURSO_DB is None:
                from turso_database import Database
                _SHARED_TURSO_DB = DBWrapper(Database(os.environ['TURSO_DATABASE_URL'], os.environ.get('TURSO_AUTH_TOKEN','')))
            g.db = _SHARED_TURSO_DB
        elif os.environ.get('DATABASE_URL'):
            from cloud_database import Database
            g.db = DBWrapper(Database(os.environ['DATABASE_URL']))
        else:
            conn = sqlite3.connect(DATA/'inventory.db', timeout=20)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            g.db = DBWrapper(conn)
    return g.db
def rows(sql,args=()): return [dict(r) for r in db().execute(sql,args).fetchall()]
def one(sql,args=()):
    r=db().execute(sql,args).fetchone(); return dict(r) if r else None
def audit(action,detail): db().execute('INSERT INTO audit(actor,action,detail,created) VALUES(?,?,?,?)',(g.user['id'] if getattr(g,'user',None) else None,action,json.dumps(detail),now()))
def fail(message,code=400): abort(code,description=message)
def number(v,minimum=0):
    if isinstance(v,bool): fail('Enter a whole number.')
    try:
        n=int(str(v))
        if n<minimum or abs(n)>10000000: raise ValueError()
        return n
    except (ValueError,TypeError): fail('Enter a valid whole quantity.')
def money(v):
    if v is None or v=='': return None
    try:
        n=Decimal(str(v))
        if not n.is_finite() or n<0 or n>10000000: raise InvalidOperation()
        return int((n*100).quantize(Decimal('1')))
    except (InvalidOperation,ValueError): fail('Enter a valid non-negative rate.')
def month(v):
    if not re.fullmatch(r'\d{4}-\d{2}',str(v)): fail('Choose a valid month.')
    try: date.fromisoformat(v+'-01')
    except ValueError: fail('Choose a valid month.')
    if v>date.today().isoformat()[:7]: fail('Future periods are not available.')
    return v
def need(role=None):
    def deco(f):
        @wraps(f)
        def wrapped(*args,**kw):
            g.user=one('SELECT * FROM users WHERE id=?',(session.get('uid',0),))
            if not g.user or not g.user['active'] or session.get('auth_version',0)!=g.user['auth_version']: fail('Please sign in.',401)
            required=access.policy(f.__name__,request.method,request.get_json(silent=True) or {})
            if required and not any(access.can(p) for p in required): fail('Your account does not have permission for this action.',403)
            if role and not required and not access.full(): fail('Full administrator access required.',403)
            return f(*args,**kw)
        return wrapped
    return deco
@app.teardown_appcontext
def teardown(e):
    if 'db' in g and not os.environ.get('TURSO_DATABASE_URL'):
        g.db.close()
    if has_request_context() and request.method != 'GET':
        invalidate_report_cache()
@app.errorhandler(Exception)
def errors(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e,HTTPException): return jsonify(error=e.description),e.code
    if isinstance(e,sqlite3.IntegrityError): return jsonify(error='This record already exists or conflicts with saved history.'),409
    app.logger.exception('Request failed')
    return jsonify(error='The operation could not be completed. No partial database changes were saved.'),500
@app.before_request
def csrf():
    if request.method in ('POST','PUT','DELETE','PATCH') and request.path.startswith('/api/'):
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','invalid')): fail('Session expired. Refresh and try again.',403)
@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options']='nosniff'; r.headers['Referrer-Policy']='same-origin'
    r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
    if request.path.startswith(('/api/','/photo/')): r.headers['Cache-Control']='no-store'
    return r

def init():
    if os.environ.get('DATABASE_URL') or os.environ.get('TURSO_DATABASE_URL'):
        with app.app_context():
            if not one('SELECT id FROM users LIMIT 1'): raise RuntimeError('Migrate existing data before starting cloud mode')
            if os.environ.get('TURSO_DATABASE_URL'):
                db().execute('SELECT path FROM stored_files LIMIT 1')
                ready=one("SELECT value FROM settings WHERE key='turso_migration_ready'")
                if ready and ready['value']!='true': raise RuntimeError('Turso migration is not complete')
        return
    with app.app_context():
        db().executescript((ROOT/'schema.sql').read_text())
        if 'auth_version' not in [r['name'] for r in rows('PRAGMA table_info(users)')]:
            db().execute('ALTER TABLE users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0'); db().commit()
        columns={r['name'] for r in rows('PRAGMA table_info(users)')}
        additions={'access_role':"TEXT NOT NULL DEFAULT 'STAFF'",'full_access':'INTEGER NOT NULL DEFAULT 0','permissions':"TEXT NOT NULL DEFAULT '[]'",'section_scope':'TEXT','login_provider':"TEXT NOT NULL DEFAULT 'password'",'google_sub':'TEXT','password_encrypted':'TEXT'}
        for name,definition in additions.items():
            if name not in columns: db().execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
        if 'access_role' not in columns:
            db().execute("UPDATE users SET access_role=role,permissions=?",(json.dumps(access.DEFAULT_STAFF),))
        for table, fields in {'submissions':{'correction_group':'TEXT','needs_correction':'INTEGER NOT NULL DEFAULT 0'},'counts':{'submitted_by':'INTEGER REFERENCES users(id)','submitted_at':'TEXT','reviewed_by':'INTEGER REFERENCES users(id)'},'lines':{'actor':'INTEGER REFERENCES users(id)','review_note':"TEXT NOT NULL DEFAULT ''",'needs_correction':'INTEGER NOT NULL DEFAULT 0'}}.items():
            existing={r['name'] for r in rows('PRAGMA table_info('+table+')')}
            for field,definition in fields.items():
                if field not in existing: db().execute(f'ALTER TABLE {table} ADD COLUMN {field} {definition}')
        # Accounts are provisioned once; never reset passwords or access at startup.
        db().commit()
        if not one('SELECT id FROM properties'):
            db().executemany('INSERT INTO properties(id,name,code) VALUES(?,?,?)',[(1,'Travelicious','TVL'),(2,'Travellers Cavern','TC')])
            for i,(p,n) in enumerate([(1,'Store'),(1,'Service'),(1,'Cafe'),(1,'Games'),(1,'Admin'),(2,'General')],1): db().execute('INSERT INTO sections(id,property_id,name,sort_order) VALUES(?,?,?,?)',(i,p,n,i))
            for sec,names in json.loads((ROOT/'seed-items.json').read_text()).items():
                sid=3 if sec=='Cafe' else 2
                for i,n in enumerate(names,1): db().execute('INSERT INTO items(code,name,section_id,created) VALUES(?,?,?,?)',(f'TVL-{sec[:3].upper()}-{i:04}',n,sid,now()))
            db().commit()

def review_admin():
    return access.owner()

def check_scope(sid):
    if getattr(g,'user',None) and not access.allows(sid): fail('You do not have access to this section.',403)

def visible_sections():
    return [s for s in rows('SELECT * FROM sections ORDER BY sort_order,name') if access.allows(s['id'])]

def section(sid):
    check_scope(sid)
    s=one('SELECT * FROM sections WHERE id=? AND active=1',(sid,))
    if not s: fail('Select an active section.')
    return s

def editable(sid,m):
    c=one('SELECT * FROM counts WHERE section_id=? AND month=?',(sid,m))
    if c and c['status'] in ('SUBMITTED','CLOSED'): fail('This section is submitted or closed. Master must reopen it first.',409)
    if one("SELECT id FROM counts WHERE section_id=? AND month>? AND status IN ('SUBMITTED','CLOSED')",(sid,m)): fail('A later period is already finalized. Reopen later periods first.',409)

def item(i):
    r=one('SELECT i.*,s.property_id,s.name section FROM items i JOIN sections s ON s.id=i.section_id WHERE i.id=? AND i.active=1 AND s.active=1',(i,))
    if not r: fail('Item is unavailable.',404)
    check_scope(r['section_id'])
    return r

def report(sid,m):
    cache_key = (sid, m)
    now_ts = time.time()
    can_cache = has_request_context() and request.method == 'GET'
    c=one('SELECT * FROM counts WHERE section_id=? AND month=?',(sid,m))
    if c and c['status']=='CLOSED':
        if cache_key in REPORT_CACHE:
            ts, cached = REPORT_CACHE[cache_key]
            if now_ts - ts < 60:
                return copy.deepcopy(cached)
        data = json.loads(one('SELECT data FROM snapshots WHERE count_id=? ORDER BY version DESC LIMIT 1',(c['id'],))['data'])
        REPORT_CACHE[cache_key] = (now_ts, data)
        return copy.deepcopy(data)
    if can_cache and cache_key in REPORT_CACHE:
        ts, cached = REPORT_CACHE[cache_key]
        if now_ts - ts < 30:
            return copy.deepcopy(cached)
    prev=one("SELECT c.id,c.month FROM counts c WHERE section_id=? AND month<? AND status='CLOSED' ORDER BY month DESC LIMIT 1",(sid,m))
    previous={}
    if prev: previous={r['id']:r for r in json.loads(one('SELECT data FROM snapshots WHERE count_id=? ORDER BY version DESC LIMIT 1',(prev['id'],))['data'])}
    allitems=rows('SELECT * FROM items WHERE section_id=? AND (active=1 OR id IN (SELECT item_id FROM movements WHERE section_id=? AND substr(date,1,7)=?)) AND substr(created,1,7)<=? ORDER BY name COLLATE NOCASE',(sid,sid,m,m))
    result=[]
    prior_by_item={r['item_id']:r['qty'] for r in rows('SELECT item_id,COALESCE(sum(qty),0) qty FROM movements WHERE section_id=? AND substr(date,1,7)<? AND substr(date,1,7)>? GROUP BY item_id',(sid,m,prev['month'] if prev else '0000-00'))}
    month_moves={}
    for movement in rows('SELECT * FROM movements WHERE section_id=? AND substr(date,1,7)=?',(sid,m)): month_moves.setdefault(movement['item_id'],[]).append(movement)
    count_lines={r['item_id']:r for r in rows('SELECT l.*,u.username FROM lines l LEFT JOIN users u ON u.id=l.actor WHERE l.count_id=?',(c['id'],))} if c else {}
    for i in allitems:
        opening=previous.get(i['id'],{}).get('actual',0) or 0
        prior=prior_by_item.get(i['id'],0)
        opening+=prior
        moves=month_moves.get(i['id'],[])
        added=sum(x['qty'] for x in moves if x['type'] in ('OPENING','PURCHASE'))
        damage=-sum(x['qty'] for x in moves if x['type'] in ('BREAKAGE','DAMAGE'))
        adjustment=sum(x['qty'] for x in moves if x['type']=='ADJUSTMENT')
        expected=opening+added-damage+adjustment
        line=count_lines.get(i['id'])
        actual=line['actual'] if line else None
        result.append(dict(i,submitted_by=(line.get('username') or '') if line else '',review_note=line.get('review_note','') if line else '',needs_correction=line.get('needs_correction',0) if line else 0,previous=opening,added=added,damage=damage,adjustment=adjustment,expected=expected,actual=actual,difference=actual-expected if actual is not None else None,note=line['note'] if line else '',flag=line['flag'] if line else '',purchase_value=sum(x['qty']*x['rate'] for x in moves if x['type'] in ('OPENING','PURCHASE') and x['rate'] is not None),breakage_qty=-sum(x['qty'] for x in moves if x['type']=='BREAKAGE'),breakage_value=sum(-x['qty']*x['rate'] for x in moves if x['type']=='BREAKAGE' and x['rate'] is not None),missing_rates=sum(x['rate'] is None for x in moves)))
    if can_cache:
        REPORT_CACHE[cache_key] = (now_ts, result)
    return copy.deepcopy(result)

def save_photo(encoded):
    if not encoded or not isinstance(encoded,str): fail('A photo is required.')
    try:
        raw=base64.b64decode(encoded.split(',')[-1],validate=True)
        if len(raw)>1024*1024: fail('Compressed photo must be smaller than 1 MB.')
        im=Image.open(io.BytesIO(raw))
        if im.format not in ('JPEG','PNG','WEBP') or im.width*im.height>30000000: fail('Use a JPEG, PNG or WebP photo under 30 megapixels.')
        im=ImageOps.exif_transpose(im).convert('RGB'); im.thumbnail((1600,1600))
        name=uuid.uuid4().hex+'.webp'; im.save(DATA/'photos'/name,'WEBP',quality=72)
        im.thumbnail((320,320)); im.save(DATA/'photos'/('thumb-'+name),'WEBP',quality=72)
        cloud_files.upload(DATA,'photos/'+name)
        cloud_files.upload(DATA,'photos/thumb-'+name)
        return name
    except (ValueError,UnidentifiedImageError,OSError): fail('This image could not be read. Choose another photo.')

@app.get('/')
def index(): return app.send_static_file('index.html')
@app.get('/sw.js')
def sw(): return app.send_static_file('sw.js')
@app.get('/api/session')
def who():
    session.setdefault('csrf',secrets.token_hex(24))
    u=one('SELECT * FROM users WHERE id=? AND active=1 AND auth_version=?',(session.get('uid',0),session.get('auth_version',0)))
    return jsonify(user=access.public_user(u) if u else None,csrf=session['csrf'],setup=False)
@app.post('/api/setup')
def setup():
    if os.environ.get('INVENTORY_SKIP_OWNER_SEED')!='1': fail('Accounts are created by your administrator. Please sign in.',403)
    d=request.json; db().execute('BEGIN IMMEDIATE')
    if one('SELECT id FROM users'): fail('Setup is already complete.',409)
    if len(d.get('password',''))<12 or not d.get('name','').strip() or not d.get('username','').strip(): fail('Name, username and a password of at least 12 characters are required.')
    cur=db().execute('INSERT INTO users(name,username,password,role,access_role) VALUES(?,?,?,?,?)',(d['name'].strip(),d['username'].lower().strip(),generate_password_hash(d['password'],method='pbkdf2:sha256:1000000'),'MASTER','MASTER'))
    db().commit(); session['uid']=cur.lastrowid; session['auth_version']=0; session.permanent=True
    return jsonify(ok=True)
@app.post('/api/login')
def login():
    d=request.json or {}; ident=d.get('username','').strip().lower()
    key=(request.remote_addr,ident)
    attempts=failures.get(key,[]); attempts=[t for t in attempts if time.time()-t<300]
    if len(attempts)>=5: fail('Too many attempts. Try again in five minutes.',429)
    u=one('SELECT * FROM users WHERE LOWER(username)=? AND active=1',(ident,))
    if not u or u['login_provider']!='password' or not check_password_hash(u['password'],d.get('password','')):
        failures[key]=attempts+[time.time()]; fail('Email/username or password is incorrect.',401)
    failures.pop(key,None); session.clear(); session['uid']=u['id']; session['auth_version']=u['auth_version']; session['csrf']=secrets.token_hex(24); session.permanent=True
    g.user=u; audit('LOGIN',{'username':u['username']}); db().commit()
    return jsonify(ok=True)
@app.post('/api/logout')
def logout(): session.clear(); return jsonify(ok=True)
@app.get('/api/context')
@need()
def context():
    ss=visible_sections(); pids={s['property_id'] for s in ss}
    return jsonify(properties=[p for p in rows('SELECT * FROM properties') if p['id'] in pids],sections=ss,reasons=REASONS,today=date.today().isoformat(),permission_labels=access.PERMISSIONS)
@app.get('/api/items')
@need()
def items():
    sid=request.args.get('section'); p=request.args.get('property'); search=request.args.get('search','')
    q='SELECT i.*,s.name section,s.property_id FROM items i JOIN sections s ON s.id=i.section_id WHERE i.active=1 AND s.active=1 AND i.name LIKE ?'; a=['%'+search+'%']
    if sid: q+=' AND i.section_id=?'; a.append(sid)
    if p: q+=' AND s.property_id=?'; a.append(p)
    result=[r for r in rows(q+' ORDER BY i.name COLLATE NOCASE',a) if access.allows(r['section_id'])]
    if not access.can('view_totals'):
        result=[{k:r[k] for k in ('id','code','name','section_id','specification','category','unit','photo','section','property_id')} for r in result]
    else:
        stocks={}
        current_m=date.today().isoformat()[:7]
        closed_sections={c['section_id'] for c in rows("SELECT section_id FROM counts WHERE month=? AND status='CLOSED'",(current_m,))}
        for s in set(r['section_id'] for r in result):
            is_closed=(s in closed_sections)
            for r_rep in report(s,current_m):
                stocks[r_rep['id']]=r_rep['actual'] if is_closed else r_rep['expected']
        for r in result: r['stock']=stocks.get(r['id'],0)
    return jsonify(result)
@app.get('/api/item-options')
@need()
def item_options():
    purpose=request.args.get('purpose')
    if purpose not in ('purchases','breakage','counts') or not access.can(purpose): fail('This form is not available.',403)
    candidates=rows('SELECT i.id,i.name,i.code,i.specification,i.photo,i.unit,i.section_id,s.name section,s.property_id FROM items i JOIN sections s ON s.id=i.section_id WHERE i.active=1 AND s.active=1 ORDER BY i.name')
    return jsonify([r for r in candidates if access.allows(r['section_id']) and (not request.args.get('property') or str(r['property_id'])==request.args['property'])])

@app.post('/api/items')
@need()
def create_item():
    d=request.json; sid=number(d.get('section_id'),1); section(sid); m=date.today().isoformat()[:7]
    if not d.get('name','').strip() or not d.get('specification','').strip(): fail('Item name and specification are required.')
    qty=number(d.get('qty',0)); rate=money(d.get('rate')); photo=save_photo(d.get('photo'))
    db().execute('BEGIN IMMEDIATE'); editable(sid,m)
    if g.user['access_role']=='STAFF':
        rid=d.get('request_id') or uuid.uuid4().hex
        if not re.fullmatch(r'[a-zA-Z0-9-]{16,80}',rid): fail('Invalid submission reference.')
        existing=one('SELECT id,actor FROM submissions WHERE request_id=?',(rid,))
        if existing:
            if existing['actor']!=g.user['id']: fail('Submission reference already used.',409)
            return jsonify(ok=True,pending=True,reference=existing['id'])
        payload=dict(type='NEW_ITEM',name=d['name'].strip(),specification=d['specification'].strip(),category=d.get('category',''),unit=d.get('unit','Nos'),qty=qty,rate=rate,photo=photo,note='',reason='',date=date.today().isoformat())
        cur=db().execute('INSERT INTO submissions(actor,section_id,payload,request_id,created,updated) VALUES(?,?,?,?,?,?)',(g.user['id'],sid,json.dumps(payload),rid,now(),now()))
        audit('NEW_ITEM_SUBMITTED',{'reference':cur.lastrowid,'payload':payload});db().commit()
        return jsonify(ok=True,pending=True,reference=cur.lastrowid)
    code='INV-'+uuid.uuid4().hex[:8].upper()
    cur=db().execute('INSERT INTO items(code,name,section_id,specification,category,unit,rate,photo,created) VALUES(?,?,?,?,?,?,?,?,?)',(code,d['name'].strip(),sid,d['specification'],d.get('category',''),d.get('unit','Nos'),rate,photo,now()))
    if qty and g.user['access_role']=='STAFF':
        payload=dict(item_id=cur.lastrowid,name=d['name'].strip(),type='PURCHASE',qty=qty,rate=rate,photo=None,reason='',note='New item received stock',date=date.today().isoformat())
        db().execute('INSERT INTO submissions(actor,section_id,payload,request_id,created,updated) VALUES(?,?,?,?,?,?)',(g.user['id'],sid,json.dumps(payload),uuid.uuid4().hex,now(),now()))
    elif qty: db().execute('INSERT INTO movements(item_id,section_id,type,qty,rate,name,note,date,actor,request_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(cur.lastrowid,sid,'OPENING',qty,rate,d['name'],'New item opening',date.today().isoformat(),g.user['id'],uuid.uuid4().hex))
    audit('ITEM_CREATED',{'code':code,'name':d['name'],'quantity':qty}); db().commit(); return jsonify(ok=True,id=cur.lastrowid)
@app.patch('/api/items/<int:iid>')
@need('MASTER')
def edit_item(iid):
    d=request.json; db().execute('BEGIN IMMEDIATE'); old=item(iid); editable(old['section_id'],date.today().isoformat()[:7])
    sid=number(d.get('section_id',old['section_id']),1); section(sid)
    if sid!=old['section_id']: fail('Use the admin Move section action to relocate an item.')
    if d.get('active') in (0,False,'0') and any(json.loads(r['payload']).get('item_id')==iid for r in rows("SELECT payload FROM submissions WHERE status IN ('PENDING','RETURNED')")): fail('Resolve outstanding reports before archiving this item.',409)
    name=d.get('name',old['name']).strip(); spec=d.get('specification',old['specification'])
    if not name: fail('Item name is required.')
    photo=save_photo(d['photo']) if d.get('photo') else old['photo']; rate=money(d['rate']) if 'rate' in d else old['rate']
    db().execute('UPDATE items SET name=?,specification=?,rate=?,photo=?,section_id=?,active=?,category=?,unit=? WHERE id=?',(name,spec,rate,photo,sid,number(d.get('active',1)),d.get('category',old['category']),d.get('unit',old['unit']),iid))
    audit('ITEM_UPDATED',{'before':old,'after':{**d,'photo':photo}}); db().commit(); return jsonify(ok=True)
@app.post('/api/items/<int:iid>/move')
@need()
def move_item(iid):
    if g.user.get('access_role') not in ('MASTER','ADMIN') or not access.can('edit_items'): fail('Only authorized admins can move items.',403)
    d=request.json; db().execute('BEGIN IMMEDIATE'); old=item(iid)
    if any(json.loads(r['payload']).get('item_id')==iid for r in rows("SELECT payload FROM submissions WHERE status IN ('PENDING','RETURNED')")): fail('Review outstanding reports before moving this item.',409)
    target=section(number(d.get('section_id'),1)); sid=target['id']; m=date.today().isoformat()[:7]
    if sid==old['section_id']: fail('Choose a different section.')
    editable(old['section_id'],m); editable(sid,m)
    stock=next(r['expected'] for r in report(old['section_id'],m) if r['id']==iid)
    if stock<0: fail('Resolve negative stock before moving this item.')
    # Keep the original record for historical counts and ledger; relocate its full balance.
    code=old['code']+'-M'+uuid.uuid4().hex[:8].upper()
    cur=db().execute('INSERT INTO items(code,name,section_id,specification,category,unit,rate,photo,created) VALUES(?,?,?,?,?,?,?,?,?)',(code,old['name'],sid,old['specification'],old['category'],old['unit'],old['rate'],old['photo'],now()))
    new_id=cur.lastrowid
    for item_id,section_id,quantity in ((iid,old['section_id'],-stock),(new_id,sid,stock)):
        db().execute('INSERT INTO movements(item_id,section_id,type,qty,rate,name,note,date,actor,request_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(item_id,section_id,'ADJUSTMENT',quantity,old['rate'],old['name'],f"Section transfer: {old['section']} to {target['name']} (items {iid} / {new_id})",date.today().isoformat(),g.user['id'],str(uuid.uuid4())))
    db().execute('UPDATE items SET active=0 WHERE id=?',(iid,))
    db().execute("DELETE FROM lines WHERE item_id=? AND count_id IN (SELECT id FROM counts WHERE month=? AND status='OPEN')",(iid,m))
    audit('ITEM_SECTION_MOVED',{'from_item':iid,'to_item':new_id,'from_section':old['section_id'],'to_section':sid,'quantity':stock})
    db().commit(); return jsonify(ok=True,id=new_id,quantity=stock)

@app.post('/api/items/bulk-move')
@need()
def bulk_move_items():
    if g.user.get('access_role') not in ('MASTER','ADMIN') or not access.can('edit_items'): fail('Only authorized admins can move items.',403)
    d=request.json or {}; item_ids=[number(x,1) for x in d.get('item_ids',[])]
    if not item_ids: fail('Select at least one item to move.')
    target=section(number(d.get('section_id'),1)); sid=target['id']; m=date.today().isoformat()[:7]
    editable(sid,m)
    queued=rows("SELECT payload FROM submissions WHERE status IN ('PENDING','RETURNED')")
    pending_ids={json.loads(r['payload']).get('item_id') for r in queued}
    conflicts=[iid for iid in item_ids if iid in pending_ids]
    if conflicts: fail(f'Review outstanding reports before moving items ({len(conflicts)} items pending review).',409)
    db().execute('BEGIN IMMEDIATE'); moved_count=0
    for iid in item_ids:
        old=one('SELECT i.*, s.name section FROM items i JOIN sections s ON s.id=i.section_id WHERE i.id=? AND i.active=1',(iid,))
        if not old or old['section_id']==sid: continue
        editable(old['section_id'],m)
        stock_list=[r['expected'] for r in report(old['section_id'],m) if r['id']==iid]
        stock=stock_list[0] if stock_list else 0
        if stock<0: db().execute('ROLLBACK'); fail(f"Resolve negative stock on '{old['name']}' before moving.",400)
        code=old['code']+'-M'+uuid.uuid4().hex[:8].upper()
        cur=db().execute('INSERT INTO items(code,name,section_id,specification,category,unit,rate,photo,created) VALUES(?,?,?,?,?,?,?,?,?)',(code,old['name'],sid,old['specification'],old['category'],old['unit'],old['rate'],old['photo'],now()))
        new_id=cur.lastrowid
        for item_id,section_id,quantity in ((iid,old['section_id'],-stock),(new_id,sid,stock)):
            if quantity!=0:
                db().execute('INSERT INTO movements(item_id,section_id,type,qty,rate,name,note,date,actor,request_id) VALUES(?,?,?,?,?,?,?,?,?,?)',(item_id,section_id,'ADJUSTMENT',quantity,old['rate'],old['name'],f"Section transfer: {old['section']} to {target['name']} (items {iid} / {new_id})",date.today().isoformat(),g.user['id'],str(uuid.uuid4())))
        db().execute('UPDATE items SET active=0 WHERE id=?',(iid,))
        db().execute("DELETE FROM lines WHERE item_id=? AND count_id IN (SELECT id FROM counts WHERE month=? AND status='OPEN')",(iid,m))
        audit('ITEM_SECTION_MOVED',{'from_item':iid,'to_item':new_id,'from_section':old['section_id'],'to_section':sid,'quantity':stock})
        moved_count+=1
    db().commit(); return jsonify(ok=True,moved=moved_count,target_section=target['name'])

@app.post('/api/items/bulk-delete')
@need()
def bulk_delete_items():
    if g.user.get('access_role') not in ('MASTER','ADMIN') or not access.can('edit_items'): fail('Only authorized admins can delete items.',403)
    d=request.json or {}; item_ids=[number(x,1) for x in d.get('item_ids',[])]
    if not item_ids: fail('Select at least one item to delete.')
    m=date.today().isoformat()[:7]
    queued=rows("SELECT payload FROM submissions WHERE status IN ('PENDING','RETURNED')")
    pending_ids={json.loads(r['payload']).get('item_id') for r in queued}
    conflicts=[iid for iid in item_ids if iid in pending_ids]
    if conflicts: fail(f'Review outstanding reports before deleting items ({len(conflicts)} items pending review).',409)
    db().execute('BEGIN IMMEDIATE'); deleted_count=0
    for iid in item_ids:
        old=one('SELECT * FROM items WHERE id=? AND active=1',(iid,))
        if not old: continue
        editable(old['section_id'],m)
        db().execute("DELETE FROM lines WHERE item_id=? AND count_id IN (SELECT id FROM counts WHERE month=? AND status='OPEN')",(iid,m))
        has_refs=one('SELECT 1 FROM movements WHERE item_id=? UNION ALL SELECT 1 FROM lines WHERE item_id=?',(iid,iid))
        if has_refs: db().execute('UPDATE items SET active=0 WHERE id=?',(iid,))
        else: db().execute('DELETE FROM items WHERE id=?',(iid,))
        deleted_count+=1
    audit('ITEMS_BULK_DELETED',{'item_ids':item_ids,'count':deleted_count})
    db().commit(); return jsonify(ok=True,deleted=deleted_count)


@app.get('/photo/<name>')
@need()
def photo(name):
    if not re.fullmatch(r'(thumb-)?[a-f0-9]{32}\.webp',name): fail('Photo unavailable.',404)
    original=name.removeprefix('thumb-')
    queued=rows('SELECT actor,section_id,payload FROM submissions')
    if any(json.loads(q['payload']).get('photo')==original and access.allows(q['section_id']) and (q['actor']==g.user['id'] or review_admin()) for q in queued):
        return send_file(cloud_files.local(DATA,'photos/'+name),mimetype='image/webp')
    references=rows('SELECT section_id FROM items WHERE photo=?',(original,))
    references+=rows('SELECT section_id FROM movements WHERE photo=?'+(' AND actor=?' if g.user['access_role']=='STAFF' else ''),(original,g.user['id']) if g.user['access_role']=='STAFF' else (original,))
    if not any(access.allows(r['section_id']) for r in references) or not any(access.can(p) for p in ('inventory','counts','review_counts','breakage','reports')): fail('Photo unavailable.',403)
    return send_file(cloud_files.local(DATA,'photos/'+name),mimetype='image/webp')
@app.post('/api/movements')
@need()
def movement():
    d=request.json; typ=d.get('type'); rid=d.get('request_id','')
    if not re.fullmatch(r'[a-zA-Z0-9-]{16,80}',rid): fail('A valid submission reference is required.')
    if typ not in ('PURCHASE','BREAKAGE','DAMAGE','ADJUSTMENT'): fail('Invalid stock action.')
    if typ=='ADJUSTMENT' and not access.can('adjustments'): fail('Master access required.',403)
    qty=number(d.get('qty'),1)
    if typ=='ADJUSTMENT' and d.get('direction')=='subtract': qty=-qty
    if typ in ('BREAKAGE','DAMAGE'): qty=-qty
    reason=d.get('reason',''); note=d.get('note','')
    if not isinstance(reason,str) or not isinstance(note,str): fail('Enter a written reason.')
    reason=reason.strip(); note=note.strip()
    if typ in ('BREAKAGE','DAMAGE') and (not reason or len(reason)>2000): fail('Type a reason between 1 and 2000 characters.')
    if typ=='ADJUSTMENT' and not note: fail('Adjustment reason is required.')
    dt=d.get('date') or date.today().isoformat()
    try: date.fromisoformat(dt)
    except ValueError: fail('Invalid transaction date.')
    if dt>date.today().isoformat(): fail('Future dates are not allowed.')
    if (typ in ('BREAKAGE','DAMAGE') or g.user['access_role']=='STAFF' or not access.can('adjustments')) and dt!=date.today().isoformat(): fail('Reports must use today’s date. Previous dates are not allowed.')
    db().execute('BEGIN IMMEDIATE')
    pending=one('SELECT id,actor FROM submissions WHERE request_id=?',(rid,))
    if pending:
        if pending['actor']!=g.user['id']: fail('Submission reference is already used.',409)
        return jsonify(ok=True,reference=pending['id'],pending=True)
    existing=one('SELECT id,actor FROM movements WHERE request_id=?',(rid,))
    if existing:
        if existing['actor']!=g.user['id']: fail('Submission reference is already used.',409)
        return jsonify(ok=True,reference=existing['id'])
    i=item(d.get('item_id'))
    if d.get('section_id') is not None and number(d['section_id'],1)!=i['section_id']: fail('Choose an item from the selected section.')
    editable(i['section_id'],dt[:7])
    r=next((r for r in report(i['section_id'],dt[:7]) if r['id']==i['id']),None)
    if not r: fail('Item did not exist in this period.')
    if qty<0 and r['expected']+qty<0: fail('This quantity cannot be processed. Please contact the Master.')
    rate=money(d.get('rate')) if typ=='PURCHASE' else i['rate']
    photo=save_photo(d.get('photo')) if typ in ('BREAKAGE','DAMAGE') else None
    if g.user['access_role']=='STAFF':
        payload=dict(item_id=i['id'],name=i['name'],type=typ,qty=qty,rate=rate,photo=photo,reason=reason,note=note,date=dt)
        cur=db().execute('INSERT INTO submissions(actor,section_id,payload,request_id,created,updated) VALUES(?,?,?,?,?,?)',(g.user['id'],i['section_id'],json.dumps(payload),rid,now(),now()))
        audit('SUBMISSION_SENT',{'id':cur.lastrowid,'payload':payload});db().commit()
        return jsonify(ok=True,reference=cur.lastrowid,pending=True)
    cur=db().execute('INSERT INTO movements(item_id,section_id,type,qty,rate,name,photo,reason,note,date,actor,request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(i['id'],i['section_id'],typ,qty,rate,i['name'],photo,reason,note,dt,g.user['id'],rid))
    if typ=='BREAKAGE':
        # Notification and stock deduction commit together; retries share the same movement.
        db().execute("INSERT INTO notifications(recipient_id,movement_id,created) SELECT id,?,? FROM users WHERE access_role='MASTER' AND active=1",(cur.lastrowid,now()))
    if typ=='PURCHASE' and rate is not None: db().execute('UPDATE items SET rate=? WHERE id=?',(rate,i['id']))
    audit(typ,{'item':i['name'],'quantity':qty,'reference':cur.lastrowid,'note':note}); db().commit()
    return jsonify(ok=True,reference=cur.lastrowid)
@app.get('/api/history/<int:iid>')
@need('MASTER')
def history(iid):
    r=one('SELECT section_id FROM items WHERE id=?',(iid,))
    if not r: fail('Item not found.',404)
    check_scope(r['section_id'])
    return jsonify(rows('SELECT m.*,u.name staff,u.username,u.id submitter_id FROM movements m JOIN users u ON u.id=m.actor WHERE item_id=? ORDER BY date DESC,id DESC',(iid,)))
@app.get('/api/counts')
@need()
def counts():
    m=month(request.args.get('month',date.today().isoformat()[:7])); result=[]
    if g.user['access_role']=='STAFF' and m!=date.today().isoformat()[:7]: fail('The count month is set automatically. Open older corrections from Corrections.',403)
    secs=[s for s in visible_sections() if s['active']]
    all_counts={c['section_id']:c for c in rows('SELECT * FROM counts WHERE month=?',(m,))}
    for s in secs:
        c=all_counts.get(s['id'])
        if c and c['submitted_by'] is not None and c['submitted_by']!=g.user['id'] and (g.user['access_role']=='STAFF' or (c['status']=='RETURNED' and not access.owner())): continue
        rr=report(s['id'],m)
        result.append(dict(s,count_id=c['id'] if c else None,status=c['status'] if c else 'OPEN',total=len(rr),completed=0 if g.user['access_role']=='STAFF' and c and c['submitted_by'] is None else sum(r['actual'] is not None for r in rr)))
    return jsonify(result)
@app.get('/api/counts/<int:sid>/<m>')
@need()
def count_detail(sid,m):
    month(m); section(sid); c=one('SELECT * FROM counts WHERE section_id=? AND month=?',(sid,m))
    if c and c['submitted_by'] is not None and c['submitted_by']!=g.user['id'] and (g.user['access_role']=='STAFF' or (c['status']=='RETURNED' and not access.owner())): fail('This count belongs to another person.',403)
    rr=report(sid,m)
    if not access.can('view_totals'): rr=[{k:r.get(k) for k in ('id','name','code','specification','photo','unit','actual','note','flag','submitted_by','review_note','needs_correction')} for r in rr]
    if g.user['access_role']=='STAFF' and c and c['submitted_by'] is None:
        for r in rr: r.update(actual=None,note='',flag='',submitted_by='',review_note='',needs_correction=0)
    owner=one('SELECT id,username FROM users WHERE id=?',(c['submitted_by'],)) if c and c['submitted_by'] else None
    return jsonify(status=c['status'] if c else 'OPEN',items=rr,submitter=owner,can_review=review_admin())
@app.post('/api/counts/<int:sid>/<m>')
@need()
def count_action(sid,m):
    month(m); section(sid); d=request.json; action=d.get('action'); db().execute('BEGIN IMMEDIATE')
    db().execute('INSERT OR IGNORE INTO counts(section_id,month) VALUES(?,?)',(sid,m)); c=one('SELECT * FROM counts WHERE section_id=? AND month=?',(sid,m))
    if g.user['access_role']=='STAFF' and m!=date.today().isoformat()[:7] and not (c['status']=='RETURNED' and c['submitted_by']==g.user['id']): fail('Staff can count only the current month, or correct a returned count.',403)
    if action in ('save','submit') and c['submitted_by'] and c['submitted_by']!=g.user['id'] and not review_admin(): fail('This count belongs to another staff member.',403)
    if action=='share':
        if not access.owner(): fail('Only master can share monthly counts.',403)
        if c['status'] in ('SUBMITTED','CLOSED','RETURNED'): fail('Submitted or returned files must stay with their original submitter.',409)
        current_owner=one('SELECT access_role FROM users WHERE id=?',(c['submitted_by'],)) if c['submitted_by'] else None
        if current_owner and current_owner['access_role']=='STAFF': fail('This section is already assigned to staff. Keep its existing counting work.',409)
        target=one('SELECT * FROM users WHERE id=? AND active=1',(d.get('staff_id'),))
        if not target or target['access_role']!='STAFF' or not access.can('counts',target) or not access.allows(sid,target): fail('Choose staff with count permission and access to this section.')
        audit('COUNT_SHARED',{'section':sid,'month':m,'assigned_to':target['id'],'previous_drafts':rows('SELECT * FROM lines WHERE count_id=?',(c['id'],))})
        db().execute('DELETE FROM lines WHERE count_id=?',(c['id'],))
        db().execute("UPDATE counts SET status='OPEN',submitted_by=?,submitted_at=NULL WHERE id=?",(target['id'],c['id']))
    elif action=='return':
        if not review_admin(): fail('Admin count review permission required.',403)
        if c['status'] not in ('SUBMITTED','RETURNED'): fail('Only submitted counts can be returned.',409)
        reason=str(d.get('reason','')).strip()
        if not reason: fail('Explain what needs correcting.')
        marked=d.get('item_ids') or [d.get('item_id')]
        if not isinstance(marked,list) or not marked: fail('Mark at least one item.')
        if c['status']=='SUBMITTED': db().execute("UPDATE lines SET review_note='',needs_correction=0 WHERE count_id=?",(c['id'],))
        for iid in marked:
            line=one('SELECT * FROM lines WHERE count_id=? AND item_id=?',(c['id'],iid))
            if not line: fail('Counted item not found.')
            db().execute('UPDATE lines SET review_note=?,needs_correction=1 WHERE count_id=? AND item_id=?',(reason,c['id'],iid))
        db().execute("UPDATE counts SET status='RETURNED',reviewed_by=? WHERE id=?",(g.user['id'],c['id']))
        audit('COUNT_RETURNED',{'section':sid,'month':m,'items':marked,'reason':reason,'submitter':c['submitted_by']})
    elif action=='reopen':
        if not review_admin(): fail('Admin count review permission required.',403)
        if c['status'] not in ('CLOSED','SUBMITTED'): fail('Only submitted or closed periods can be reopened.')
        if not d.get('reason','').strip(): fail('A reopening reason is required.')
        if one("SELECT id FROM counts WHERE section_id=? AND month>? AND status IN ('CLOSED','SUBMITTED')",(sid,m)): fail('Reopen later periods first to protect stock continuity.')
        db().execute("UPDATE counts SET status='REOPENED' WHERE id=?",(c['id'],)); audit('MONTH_REOPENED',{'section':sid,'month':m,'reason':d['reason']})
    elif action=='save':
        editable(sid,m); i=item(d.get('item_id'))
        if g.user['access_role']=='STAFF' and c['submitted_by'] is None:
            audit('COUNT_CLAIMED',{'section':sid,'month':m,'actor':g.user['id'],'previous_drafts':rows('SELECT * FROM lines WHERE count_id=?',(c['id'],))})
            db().execute('DELETE FROM lines WHERE count_id=?',(c['id'],))

        if i['section_id']!=sid or i['created'][:7]>m: fail('Item does not belong to this count.')
        previous_line=one('SELECT * FROM lines WHERE count_id=? AND item_id=?',(c['id'],i['id']))
        if c['status']=='RETURNED' and (not previous_line or not previous_line['review_note']): fail('Only flagged items can be corrected.',409)
        if c['status']=='RETURNED' and c['submitted_by']!=g.user['id']: fail('The original submitter must correct this count.',403)
        flag=d.get('flag',''); note=d.get('note','').strip()
        if flag not in ('','NOT_FOUND','NOT_APPLICABLE'): fail('Invalid count status.')
        if flag and not note: fail('A note is required for this count status.')
        actual=number(d.get('actual'))
        db().execute('INSERT INTO lines(count_id,item_id,actual,note,flag) VALUES(?,?,?,?,?) ON CONFLICT(count_id,item_id) DO UPDATE SET actual=excluded.actual,note=excluded.note,flag=excluded.flag',(c['id'],i['id'],actual,note,flag))
        db().execute('UPDATE lines SET actor=?,needs_correction=0 WHERE count_id=? AND item_id=?',(g.user['id'],c['id'],i['id']))
        db().execute("UPDATE counts SET status=?,submitted_by=COALESCE(submitted_by,?) WHERE id=?",('RETURNED' if c['status']=='RETURNED' else 'IN PROGRESS',g.user['id'],c['id'])); audit('COUNT_SAVED',{'section':sid,'month':m,'item':i['id'],'actual':actual,'note':note})
    elif action in ('submit','close'):
        if action=='close':
            if not review_admin(): fail('Admin count review permission required.',403)
            if c['status']!='SUBMITTED': fail('Submit the complete count before closing.')
        else: editable(sid,m)
        if one('SELECT item_id FROM lines WHERE count_id=? AND needs_correction=1',(c['id'],)): fail('Correct every flagged item before submitting.',409)
        if action=='close' and one("SELECT id FROM submissions WHERE section_id=? AND substr(json_extract(payload,'$.date'),1,7)<=? AND status IN ('PENDING','RETURNED')",(sid,m)): fail('Resolve pending or returned stock reports before accepting this count.',409)
        rr=report(sid,m)
        if not rr or any(r['actual'] is None for r in rr): fail('Count every item before submitting or closing.')
        if action=='close':
            version=one('SELECT COALESCE(MAX(version),0)+1 n FROM snapshots WHERE count_id=?',(c['id'],))['n']
            snap=db().execute('INSERT INTO snapshots(count_id,version,data,created) VALUES(?,?,?,?)',(c['id'],version,json.dumps(rr),now())).lastrowid
            from exports import make_export
            for kind in ('inventory','breakage'):
                data=rr if kind=='inventory' else event_rows(m,sid=sid,types=('BREAKAGE',))
                for fmt in ('xlsx','pdf'):
                    blob=make_export(data,kind,fmt,f'{section(sid)["name"]} · {m} · revision {version}',DATA)
                    path=f'{sid}_{m}_v{version}_{kind}.{fmt}'; (DATA/'reports'/path).write_bytes(blob); cloud_files.upload(DATA,'reports/'+path)
                    db().execute('INSERT INTO archives(snapshot_id,kind,format,path,sha256) VALUES(?,?,?,?,?)',(snap,kind,fmt,path,hashlib.sha256(blob).hexdigest()))
        if action=='submit': db().execute('UPDATE counts SET submitted_by=?,submitted_at=? WHERE id=?',(g.user['id'],now(),c['id']))
        else: db().execute('UPDATE counts SET reviewed_by=? WHERE id=?',(g.user['id'],c['id']))
        db().execute('UPDATE counts SET status=? WHERE id=?',('CLOSED' if action=='close' else 'SUBMITTED',c['id'])); audit('MONTH_'+action.upper(),{'section':sid,'month':m})
    else: fail('Unknown count action.')
    db().commit(); return jsonify(ok=True)

def event_rows(period,p=None,sid=None,types=None):
    sql='SELECT m.*,s.name section,s.property_id,p.name property,u.name staff,u.username,u.id submitter_id FROM movements m JOIN sections s ON s.id=m.section_id JOIN properties p ON p.id=s.property_id JOIN users u ON u.id=m.actor WHERE m.date LIKE ?'; args=[period+'%']
    if p: sql+=' AND s.property_id=?'; args.append(p)
    if sid: sql+=' AND m.section_id=?'; args.append(sid)
    if types: sql+=' AND m.type IN ('+','.join('?' for _ in types)+')'; args.extend(types)
    return [r for r in rows(sql+' ORDER BY m.date DESC,m.id DESC',args) if access.allows(r['section_id'])]
@app.get('/api/events')
@need()
def events():
    period=request.args.get('month',date.today().isoformat()[:7]); rr=event_rows(period,request.args.get('property'),request.args.get('section'))
    if not access.can('view_totals'): rr=[{k:r[k] for k in ('id','name','type','qty','date','photo','reason','note')} for r in rr if r['actor']==g.user['id']]
    return jsonify(rr)
@app.get('/api/reports')
@need('MASTER')
def reports(): return jsonify(report_data())
def selected_report_sections():
    raw=request.args.get('sections')
    if raw is None: return None
    if not raw.strip(): fail('Select at least one section.')
    ids={number(v,1) for v in raw.split(',')}
    valid={s['id'] for s in visible_sections()}
    if not ids<=valid: fail('A selected section is unavailable or outside your access.',403)
    return ids

def report_data(kind_override=None):
    m=request.args.get('month',date.today().isoformat()[:7]); p=request.args.get('property'); sid=request.args.get('section'); kind=kind_override or request.args.get('kind','inventory'); selected=selected_report_sections()
    if kind not in ('inventory','breakage','purchases','yearly'): fail('Choose a valid report.')
    if kind!='yearly': month(m)
    if kind in ('breakage','purchases'): return [r for r in event_rows(m,p,sid,('BREAKAGE','DAMAGE') if kind=='breakage' else ('PURCHASE','OPENING')) if selected is None or r['section_id'] in selected]
    if kind=='yearly':
        year=number(request.args.get('year',date.today().year),2000); result=[]
        if year>date.today().year: fail('Future years are not available.')
        for n in range(1,13):
            period=f'{year}-{n:02}'; rr=[]
            for s in visible_sections():
                if (p and str(s['property_id'])!=p) or (sid and str(s['id'])!=sid) or (selected is not None and s['id'] not in selected): continue
                if one("SELECT id FROM counts WHERE section_id=? AND month=? AND status='CLOSED'",(s['id'],period)): rr.extend(report(s['id'],period))
            result.append(dict(month=period,items=len(rr),purchase_value=sum(r['purchase_value'] for r in rr),breakage_qty=sum(r['breakage_qty'] for r in rr),breakage_value=sum(r['breakage_value'] for r in rr),difference=sum(r['difference'] or 0 for r in rr)))
        return result
    month(m); result=[]
    for s in [s for s in rows('SELECT s.*,p.name property FROM sections s JOIN properties p ON p.id=s.property_id') if access.allows(s['id'])]:
        if (p and str(s['property_id'])!=p) or (sid and str(s['id'])!=sid) or (selected is not None and s['id'] not in selected): continue
        c=one('SELECT status FROM counts WHERE section_id=? AND month=?',(s['id'],m))
        result.extend(dict(r,section=s['name'],property=s['property'],status=c['status'] if c else 'OPEN') for r in report(s['id'],m))
    return result
@app.get('/api/export')
@need('MASTER')
def export():
    from exports import make_export
    kind=request.args.get('kind','inventory'); fmt=request.args.get('format','xlsx')
    if fmt not in ('xlsx','pdf') or kind not in ('inventory','breakage','purchases','yearly'): fail('Invalid export format.')
    selected=selected_report_sections()
    sections=[s for s in visible_sections() if (selected is None or s['id'] in selected) and (not request.args.get('property') or str(s['property_id'])==request.args['property']) and (not request.args.get('section') or str(s['id'])==request.args['section'])]
    period=request.args.get('year',str(date.today().year)) if kind=='yearly' else request.args.get('month',date.today().isoformat()[:7])
    title=f"{kind.title()} | {period} | "+', '.join(s['name'] for s in sections)
    result=make_export(report_data(),kind,fmt,title,DATA)
    audit('REPORT_EXPORTED',dict(request.args)); db().commit()
    return send_file(io.BytesIO(result),as_attachment=True,download_name=f'{kind}_{period}.{fmt}')

@app.get('/api/export/monthly-pack')
@need()
def monthly_pack():
    if not access.can('reports'): fail('Report permission required.',403)
    import zipfile
    from exports import make_export
    fmt=request.args.get('format','pdf')
    if fmt not in ('pdf','xlsx'): fail('Choose PDF or Excel.')
    m=month(request.args.get('month',date.today().isoformat()[:7]));selected=selected_report_sections()
    names=[s['name'] for s in visible_sections() if (selected is None or s['id'] in selected) and (not request.args.get('property') or str(s['property_id'])==request.args['property'])]
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for kind in ('inventory','breakage','purchases'):
            z.writestr(f'{kind}_{m}.{fmt}',make_export(report_data(kind),kind,fmt,f"{kind.title()} | {m} | "+', '.join(names),DATA))
    audit('MONTHLY_REPORT_PACK_EXPORTED',dict(request.args));db().commit()
    return send_file(io.BytesIO(out.getvalue()),as_attachment=True,download_name=f'monthly_reports_{m}.zip')

@app.get('/api/archives')
@need('MASTER')
def archives(): return jsonify([r for r in rows('SELECT a.*,c.month,c.section_id,s.version,s.created FROM archives a JOIN snapshots s ON s.id=a.snapshot_id JOIN counts c ON c.id=s.count_id ORDER BY a.id DESC') if access.allows(r['section_id'])])
@app.get('/api/archives/<int:aid>')
@need('MASTER')
def archive_file(aid):
    a=one('SELECT a.*,c.section_id FROM archives a JOIN snapshots s ON s.id=a.snapshot_id JOIN counts c ON c.id=s.count_id WHERE a.id=?',(aid,))
    if not a: fail('Archive not found.',404)
    check_scope(a['section_id'])
    return send_file(cloud_files.local(DATA,'reports/'+a['path']),as_attachment=True,download_name=a['path'])
@app.get('/api/notifications')
@need()
def notifications():
    rr=rows('SELECT n.id,n.created,n.read_at,m.id reference,m.name,m.qty,m.reason,m.date,m.photo,m.section_id,s.property_id,s.name section,p.name property,u.name staff FROM notifications n JOIN movements m ON m.id=n.movement_id JOIN sections s ON s.id=m.section_id JOIN properties p ON p.id=s.property_id JOIN users u ON u.id=m.actor WHERE n.recipient_id=? ORDER BY n.id DESC LIMIT 50',(g.user['id'],))
    rr=[r for r in rr if access.allows(r['section_id'])]
    unread=one('SELECT count(*) total FROM notifications WHERE recipient_id=? AND read_at IS NULL',(g.user['id'],))['total']
    return jsonify(items=rr,unread=unread)

@app.post('/api/notifications/<int:nid>/read')
@need()
def read_notification(nid):
    n=one('SELECT n.*,m.section_id FROM notifications n JOIN movements m ON m.id=n.movement_id WHERE n.id=? AND n.recipient_id=?',(nid,g.user['id']))
    if not n: fail('Notification not found.',404)
    check_scope(n['section_id'])
    db().execute('UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=?',(now(),nid));db().commit()
    return jsonify(ok=True)

@app.get('/api/users')
@need('MASTER')
def users():
    if not access.owner(): fail('Only the main admin can manage members.',403)
    rr=rows('SELECT * FROM users')
    if not access.full():
        scope=access.scopes()
        rr=[u for u in rr if u['access_role']=='STAFF' and (scope is None or (access.scopes(u) is not None and set(access.scopes(u))<=set(scope)))]
    return jsonify([access.public_user(u) for u in rr])
@app.post('/api/users')
@need('MASTER')
def user_write():
    if not access.owner(): fail('Only the main admin can manage members.',403)
    d=request.json;db().execute('BEGIN IMMEDIATE')
    u=one('SELECT * FROM users WHERE id=?',(d['id'],)) if d.get('id') else None
    if d.get('id') and not u: fail('User not found.',404)
    if u and (u['access_role']=='MASTER' or u['id']==g.user['id']): fail('The Master account and your own access cannot be changed here.',403)
    import sys
    role,full_access,perms,scope=access.validate_assignment(sys.modules[__name__],g.user,u,d)
    name=d.get('name',u['name'] if u else '').strip(); username=d.get('username',u['username'] if u else '').strip().lower()
    if not name or not username or username==access.OWNER_EMAIL: fail('Enter a valid name and unique staff/admin username.')
    active=d.get('active',bool(u['active']) if u else True)
    if type(active) not in (int,bool) or active not in (0,1,False,True): fail('Invalid account status.')
    password=d.get('password','')
    if not isinstance(password,str) or ((not u or password) and len(password)<5): fail('Use a password with at least 5 characters.')
    values=(name,username,role,int(full_access),json.dumps(perms),json.dumps(scope) if scope is not None else None,int(active))
    before=access.public_user(u) if u else None
    if u:
        db().execute('UPDATE users SET name=?,username=?,access_role=?,full_access=?,permissions=?,section_scope=?,active=?,auth_version=auth_version+1 WHERE id=?',values+(u['id'],))
        if password: db().execute('UPDATE users SET password=? WHERE id=?',(generate_password_hash(password,method='pbkdf2:sha256:1000000'),u['id']))
        uid=u['id']
    else:
        uid=db().execute("INSERT INTO users(name,username,access_role,full_access,permissions,section_scope,active,password,role) VALUES(?,?,?,?,?,?,?,?,'STAFF')",values+(generate_password_hash(password,method='pbkdf2:sha256:1000000'),)).lastrowid
    if password: db().execute('UPDATE users SET password_encrypted=? WHERE id=?',(credential_vault.seal(DATA,password),uid))
    audit('USER_CHANGED',{'before':before,'after':access.public_user(one('SELECT * FROM users WHERE id=?',(uid,))),'password_changed':bool(password)})
    db().commit();return jsonify(ok=True)
@app.post('/api/users/<int:uid>/password/reveal')
@need()
def reveal_member_password(uid):
    if not access.owner(): fail('Only the main admin can view passwords.',403)
    u=one('SELECT * FROM users WHERE id=?',(uid,))
    if not u: fail('Member not found.',404)
    value=credential_vault.reveal(DATA,u.get('password_encrypted'))
    audit('PASSWORD_VIEWED',{'user_id':uid,'available':value is not None});db().commit()
    return jsonify(password=value,reset_required=value is None)

@app.post('/api/password')
@need()
def password():
    if not access.owner(): fail('Only the main admin can change passwords.',403)
    d=request.json; u=one('SELECT * FROM users WHERE id=?',(g.user['id'],))
    if u['login_provider']=='google': fail('Your password is managed by Google.',403)
    if not check_password_hash(u['password'],d.get('current','')) or not isinstance(d.get('password'),str) or len(d['password'])<5: fail('Check the current password and use at least 5 characters for the new password.')
    db().execute('UPDATE users SET password_encrypted=? WHERE id=?',(credential_vault.seal(DATA,d['password']),u['id']))
    db().execute('UPDATE users SET password=?,auth_version=auth_version+1 WHERE id=?',(generate_password_hash(d['password'],method='pbkdf2:sha256:1000000'),u['id'])); audit('PASSWORD_CHANGED',{}); db().commit(); session['auth_version']=u['auth_version']+1; return jsonify(ok=True)
@app.post('/api/sections')
@need('MASTER')
def section_write():
    d=request.json; name=d.get('name','').strip()
    if not name: fail('Section name is required.')
    if d.get('id'):
        if d.get('active')==0 and one('SELECT id FROM items WHERE section_id=? AND active=1',(d['id'],)): fail('Archive or move active items first.')
        db().execute('UPDATE sections SET name=?,active=?,sort_order=? WHERE id=?',(name,d.get('active',1),number(d.get('sort_order',0)),d['id']))
    else: db().execute('INSERT INTO sections(property_id,name,sort_order) VALUES(?,?,?)',(number(d.get('property_id'),1),name,number(d.get('sort_order',0))))
    audit('SECTION_CHANGED',d); db().commit(); return jsonify(ok=True)
@app.get('/api/audit')
@need('MASTER')
def audit_list():
    offset=number(request.args.get('offset',0)); q=request.args.get('search','')
    return jsonify(rows('SELECT a.*,u.name staff FROM audit a LEFT JOIN users u ON u.id=a.actor WHERE a.action LIKE ? OR a.detail LIKE ? ORDER BY a.id DESC LIMIT 100 OFFSET ?',('%'+q+'%','%'+q+'%',offset)))
@app.get('/api/backup')
@need('MASTER')
def backup():
    import zipfile,tempfile
    audit('BACKUP_EXPORTED',{}); db().commit()
    buffer=io.BytesIO()
    if os.environ.get('DATABASE_URL'):
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('inventory-postgres.json',json.dumps(db().dump()))
            for folder in ('photos','reports'):
                for relative in cloud_files.objects(folder): z.write(cloud_files.local(DATA,relative),relative)
        buffer.seek(0)
        return send_file(buffer,as_attachment=True,download_name=f'inventory-cloud-backup-{date.today()}.zip')
    if os.environ.get('TURSO_DATABASE_URL'):
        from turso_backup import archive
        archive(db(),buffer)
        buffer.seek(0)
        return send_file(buffer,as_attachment=True,download_name=f'inventory-turso-backup-{date.today()}.zip')
    with tempfile.TemporaryDirectory() as tmp:
        dest=sqlite3.connect(Path(tmp)/'inventory.db'); db().backup(dest); dest.close()
        with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(Path(tmp)/'inventory.db','inventory.db')
            for folder in ('photos','reports'):
                for f in (DATA/folder).glob('*'): z.write(f,str(f.relative_to(DATA)))
    buffer.seek(0); return send_file(buffer,as_attachment=True,download_name=f'inventory-backup-{date.today()}.zip')

init()
import sys
from importer import register
register(sys.modules[__name__])
from approvals import register as register_approvals
register_approvals(sys.modules[__name__])
if __name__=='__main__': app.run(host=os.environ.get('HOST','127.0.0.1'),port=int(os.environ.get('PORT','5055')),debug=False,threaded=True)
