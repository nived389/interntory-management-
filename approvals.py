"""Master review and private, author-owned correction lists."""
import json,uuid
from flask import g,request,jsonify
import access

def reviewer(): return access.owner()

def register(a):
    def load(qid):
        q=a.one('SELECT * FROM submissions WHERE id=?',(qid,))
        if not q:a.fail('Submission not found.',404)
        a.check_scope(q['section_id']);return q

    def open_period(q,p):
        a.section(q['section_id'])
        if a.one("SELECT id FROM counts WHERE section_id=? AND month>=? AND (status='CLOSED' OR (month>? AND status='SUBMITTED'))",(q['section_id'],p['date'][:7],p['date'][:7])):a.fail('Reopen finalized periods before reviewing this submission.',409)

    def approve(q):
        p=json.loads(q['payload']);open_period(q,p)
        if p['type']=='NEW_ITEM':
            code=a.next_item_code()
            iid=a.db().execute('INSERT INTO items(code,name,section_id,specification,category,unit,rate,photo,created) VALUES(?,?,?,?,?,?,?,?,?)',(code,p['name'],q['section_id'],p['specification'],p.get('category',''),p.get('unit','Nos'),p.get('rate'),p['photo'],p['date']+'T00:00:00')).lastrowid
            p['item_id']=iid;typ='OPENING'
        else:
            i=a.item(p['item_id']);iid=i['id'];typ=p['type']
            if i['section_id']!=q['section_id']:a.fail('Item moved. Return this report for correction.')
            r=next((r for r in a.report(q['section_id'],p['date'][:7]) if r['id']==iid),None)
            if not r or (r['expected']>0 and r['expected']+p['qty']<0):a.fail('Insufficient stock. Review purchases or correct this quantity.')
        mid=None
        if p['qty']:
            mid=a.db().execute('INSERT INTO movements(item_id,section_id,type,qty,rate,name,photo,reason,note,date,actor,request_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(iid,q['section_id'],typ,p['qty'],p.get('rate'),p['name'],p.get('photo'),p.get('reason',''),p.get('note',''),p['date'],q['actor'],'approved-'+str(q['id']))).lastrowid
        if typ in ('BREAKAGE','DAMAGE'):
            a.db().execute("INSERT INTO notifications(recipient_id,movement_id,created) SELECT id,?,? FROM users WHERE access_role='MASTER' AND active=1",(mid,a.now()))
        if typ=='PURCHASE' and p.get('rate') is not None:a.db().execute('UPDATE items SET rate=? WHERE id=?',(p['rate'],iid))
        a.db().execute("UPDATE submissions SET status='ACCEPTED',reviewer=?,movement_id=?,payload=?,updated=? WHERE id=?",(g.user['id'],mid,json.dumps(p),a.now(),q['id']))
        a.audit('SUBMISSION_ACCEPT',{'id':q['id'],'submitter':q['actor'],'revision':q['revision'],'item_id':iid})

    def inbox(private=False):
        rr=a.rows("SELECT q.*,u.username,u.name staff,s.name section FROM submissions q JOIN users u ON u.id=q.actor JOIN sections s ON s.id=q.section_id WHERE q.status!='ACCEPTED' ORDER BY q.id DESC")
        rr=[r for r in rr if access.allows(r['section_id']) and (not private or (r['actor']==g.user['id'] and r['status']=='RETURNED'))]
        for r in rr:
            r['payload']=json.loads(r['payload'])
            if private:r['payload'].pop('rate',None)
        cc=a.rows("SELECT c.*,u.username,u.name staff,s.name section FROM counts c LEFT JOIN users u ON u.id=c.submitted_by JOIN sections s ON s.id=c.section_id WHERE c.status IN ('SUBMITTED','RETURNED','CLOSED') ORDER BY c.month DESC")
        cc=[r for r in cc if access.allows(r['section_id']) and (not private or (r['submitted_by']==g.user['id'] and r['status']=='RETURNED'))]
        return jsonify(submissions=rr,counts=cc,reviewer=not private)

    @a.app.get('/api/reviews')
    @a.need()
    def review_inbox():
        if not reviewer():a.fail('Only the master admin can review submissions.',403)
        return inbox()

    @a.app.get('/api/corrections')
    @a.need()
    def correction_inbox():return inbox(private=True)

    @a.app.post('/api/reviews/list')
    @a.need()
    def review_list():
        if not reviewer():a.fail('Only the master admin can review submissions.',403)
        d=request.json;entries=d.get('entries',[]);marked=d.get('marked',[]);action=d.get('action')
        if not isinstance(entries,list) or not entries or len(entries)>500:a.fail('Select a valid list.')
        a.db().execute('BEGIN IMMEDIATE');qs=[load(x.get('id')) for x in entries]
        if len({q['id'] for q in qs})!=len(qs):a.fail('Duplicate entries.')
        if len({(q['actor'],q['section_id'],json.loads(q['payload'])['type'],json.loads(q['payload'])['date']) for q in qs})!=1:a.fail('A list must belong to one submitter, section, date and submission type.')
        for q,e in zip(qs,entries):
            if q['status']!='PENDING' or q['revision']!=e.get('revision'):a.fail('The list changed. Refresh before reviewing.',409)
            if q['correction_group']:
                others=a.rows('SELECT id FROM submissions WHERE correction_group=? AND status=?',(q['correction_group'],'PENDING'))
                if not {r['id'] for r in others}<={r['id'] for r in qs}:a.fail('Review the complete correction list.',409)
        if action=='accept':
            for q in qs:approve(q)
        elif action=='return':
            feedback=str(d.get('feedback','')).strip()
            if not feedback or not marked or not set(marked)<={q['id'] for q in qs}:a.fail('Mark items and explain what needs correcting.')
            group=uuid.uuid4().hex
            for q in qs:
                flagged=q['id'] in marked
                a.db().execute("UPDATE submissions SET status='RETURNED',correction_group=?,needs_correction=?,feedback=?,reviewer=?,updated=? WHERE id=?",(group,int(flagged),feedback if flagged else '',g.user['id'],a.now(),q['id']))
        elif action=='delete':
            for q in qs:
                a.db().execute('DELETE FROM submissions WHERE id=?',(q['id'],))
            a.audit('LIST_DELETED',{'submitter':qs[0]['actor'],'entries':[q['id'] for q in qs]})
        else:a.fail('Choose accept, return or delete.')
        a.db().commit();return jsonify(ok=True)

    @a.app.post('/api/corrections/list/<group>/submit')
    @a.need()
    def resubmit_list(group):
        a.db().execute('BEGIN IMMEDIATE');qs=a.rows('SELECT * FROM submissions WHERE correction_group=?',(group,))
        if not qs or any(q['actor']!=g.user['id'] for q in qs):a.fail('Correction list not found.',404)
        for q in qs:
            a.check_scope(q['section_id'])
            if q['status']!='RETURNED' or q['needs_correction']:a.fail('Correct every marked item before sending the list.',409)
            open_period(q,json.loads(q['payload']))
        a.db().execute("UPDATE submissions SET status='PENDING',revision=revision+1,updated=? WHERE correction_group=?",(a.now(),group))
        a.audit('LIST_RESUBMITTED',{'group':group,'submitter':g.user['id']});a.db().commit();return jsonify(ok=True)

    @a.app.post('/api/corrections/<int:qid>')
    @a.app.post('/api/reviews/<int:qid>')
    @a.app.delete('/api/reviews/<int:qid>')
    @a.app.patch('/api/reviews/<int:qid>')
    @a.need()
    def review_submission(qid):
        a.db().execute('BEGIN IMMEDIATE');q=load(qid);d=request.json if request.is_json else {};d=d or {};action=d.get('action');p=json.loads(q['payload'])
        if request.method=='DELETE' or action=='delete':
            if not reviewer():a.fail('Only the master admin can review submissions.',403)
            a.db().execute('DELETE FROM submissions WHERE id=?',(qid,))
            a.audit('SUBMISSION_DELETED',{'id':qid,'submitter':q['actor'],'section_id':q['section_id'],'payload':p})
            a.db().commit();return jsonify(ok=True)
        if request.method=='PATCH' or action=='edit':
            if not reviewer():a.fail('Only the master admin can edit submissions.',403)
            if q['status']=='ACCEPTED':a.fail('Cannot edit an already approved submission.',409)
            if d.get('section_id'):
                sid=a.number(d['section_id'],q['section_id'])
                a.section(sid)
                q['section_id']=sid
            if 'name' in d:
                name=str(d.get('name','')).strip()
                if not name:a.fail('Item name is required.')
                p['name']=name
                if p.get('item_id') and p['type']!='NEW_ITEM':
                    a.db().execute('UPDATE items SET name=? WHERE id=?',(name,p['item_id']))
            if d.get('item_id') and p['type']!='NEW_ITEM':
                i=a.item(d['item_id'])
                p['item_id']=i['id']
                if not d.get('name'):p['name']=i['name']
                q['section_id']=i['section_id']
            if 'qty' in d and d.get('qty') not in ('',None):
                qty=a.number(d.get('qty'),0 if p['type']=='NEW_ITEM' else 1)
                p['qty']=-abs(qty) if p['type'] in ('BREAKAGE','DAMAGE') else abs(qty)
            if 'rate' in d:
                if d.get('rate') in ('',None):
                    p['rate']=None
                else:
                    p['rate']=a.money(d['rate'])
            if 'specification' in d:p['specification']=str(d.get('specification','')).strip()
            if 'category' in d:p['category']=str(d.get('category','')).strip()
            if 'unit' in d:p['unit']=str(d.get('unit','Nos')).strip()
            if 'reason' in d:p['reason']=str(d.get('reason','')).strip()
            if 'note' in d:p['note']=str(d.get('note','')).strip()
            a.db().execute('UPDATE submissions SET payload=?,section_id=?,updated=? WHERE id=?',(json.dumps(p),q['section_id'],a.now(),qid))
            a.audit('SUBMISSION_EDITED',{'id':qid,'submitter':q['actor'],'before':json.loads(q['payload']),'after':p,'section_id':q['section_id']})
            a.db().commit();return jsonify(ok=True)
        if action=='resubmit':
            if q['actor']!=g.user['id']:a.fail('Only the original submitter can correct this report.',403)
            if q['status']=='PENDING':return jsonify(ok=True,status='PENDING')
            if q['status']!='RETURNED':a.fail('Only returned reports can be corrected.',409)
            if q['correction_group'] and not q['feedback']:a.fail('Only marked items may be changed.',403)
            open_period(q,p)
            permission='add_items' if p['type']=='NEW_ITEM' else 'purchases' if p['type']=='PURCHASE' else 'breakage' if p['type'] in ('BREAKAGE','DAMAGE') else 'adjustments'
            if not access.can(permission):a.fail('Submission permission has been removed.',403)
            if p['type']=='NEW_ITEM':
                p['name']=str(d.get('name',p['name'])).strip();p['specification']=str(d.get('specification',p.get('specification',''))).strip()
                if not p['name']:a.fail('Name is required.')
                p['category']=str(d.get('category',p.get('category','')));p['unit']=str(d.get('unit',p.get('unit','Nos')))
            else:
                i=a.item(d.get('item_id',p['item_id']))
                if i['section_id']!=q['section_id']:a.fail('Select an item from the original section.')
                p['item_id']=i['id'];p['name']=i['name']
            qty=a.number(d.get('qty'),0 if p['type']=='NEW_ITEM' else 1);p['qty']=-qty if p['type'] in ('BREAKAGE','DAMAGE') or p['qty']<0 else qty
            p['reason']=str(d.get('reason',p.get('reason',''))).strip();p['note']=str(d.get('note','')).strip()
            if p['type'] in ('BREAKAGE','DAMAGE') and not p['reason']:a.fail('A reason is required.')
            if len(p['reason'])>2000 or len(p['note'])>4000:a.fail('Please shorten the explanation.')
            if p['type'] in ('PURCHASE','NEW_ITEM') and d.get('rate') not in ('',None):p['rate']=a.money(d['rate'])
            if d.get('photo'):p['photo']=a.save_photo(d['photo'])
            status='RETURNED' if q['correction_group'] else 'PENDING'
            a.db().execute('UPDATE submissions SET payload=?,status=?,needs_correction=0,revision=revision+1,updated=? WHERE id=?',(json.dumps(p),status,a.now(),qid))
        else:
            if not reviewer():a.fail('Only the master admin can review submissions.',403)
            if action=='accept' and q['status']=='ACCEPTED':return jsonify(ok=True,status='ACCEPTED')
            if q['status']!='PENDING':a.fail('Report is not awaiting review.',409)
            if a.number(d.get('revision'),1)!=q['revision']:a.fail('Report changed. Refresh before reviewing.',409)
            if q['correction_group']:a.fail('Review this complete list together.',409)
            if action=='return':
                feedback=str(d.get('feedback','')).strip()
                if not feedback:a.fail('Explain what needs correcting.')
                a.db().execute("UPDATE submissions SET status='RETURNED',needs_correction=1,feedback=?,reviewer=?,updated=? WHERE id=?",(feedback,g.user['id'],a.now(),qid))
            elif action=='accept':approve(q)
            else:a.fail('Choose accept or return.')
        a.audit('SUBMISSION_'+action.upper(),{'id':qid,'submitter':q['actor'],'before':json.loads(q['payload']),'after':p,'feedback':d.get('feedback',''),'revision':q['revision']})
        a.db().commit();return jsonify(ok=True)
