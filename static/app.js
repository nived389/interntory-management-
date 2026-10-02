'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons={home:'M3 10l9-7 9 7v10H3z M9 20v-7h6v7',box:'M3 7l9-4 9 4v13H3z M3 7l9 5 9-5 M12 12v8',count:'M8 4H5v17h14V4h-3 M9 2h6v5H9z M8 12h8 M8 16h5',break:'M13 2l-3 7 5 3-5 10 M5 4H2v17h7 M16 4h6v17h-9',report:'M4 3h12l4 4v14H4z M8 16v-3 M12 16V9 M16 16v-5',users:'M16 21v-3a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v3 M9 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-3a4 4 0 0 0-3-4 M17 2a4 4 0 0 1 0 8',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',audit:'M4 4h16v16H4z M8 8h8 M8 12h8 M8 16h4',arrow:'M5 12h14 M13 6l6 6-6 6',plus:'M12 5v14 M5 12h14',photo:'M3 6h5l2-3h4l2 3h5v15H3z M12 9a4 4 0 1 0 0 8 4 4 0 0 0 0-8',logout:'M9 3H3v18h6 M9 12h12 M17 8l4 4-4 4',asset:'M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'};
const icon=n=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${icons[n]||icons.box}"/></svg>`;
const state={user:null,csrf:'',page:'dashboard',property:'1',assetProperty:'1',assetSearch:'',selectedAssets:new Set(),month:'',section:'',items:[],context:null,reportKind:'inventory',countSection:null,countTab:'remaining',countSearch:'',reviewTab:'breakage',search:'',auditOffset:0};
let renderVersion=0;
const can=p=>!!state.user?.permissions?.includes(p);
const master=()=>can('view_totals');
const staffMode=()=>state.user?.role==='STAFF';
const itemOptions=purpose=>api(staffMode()?'/item-options?purpose='+purpose+'&property='+state.property:'/items?property='+state.property);
const fullAdmin=()=>!!state.user?.full_access;
const rupees=v=>v===null||v===undefined?'Rate missing':new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(v/100);
const qty=v=>v===null||v===undefined?'—':Number(v).toLocaleString('en-IN');
function toast(msg){$('#toast').textContent=msg;$('#toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('show'),4000)}
async function api(path,method='GET',data){const res=await fetch('/api'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:data===undefined?undefined:JSON.stringify(data)});const body=await res.json();if(!res.ok){if(res.status===401&&state.user){state.user=null;await boot()}throw new Error(body.error||'Request failed')}return body}
const prop=()=>state.context.properties.find(p=>String(p.id)===state.property)?.name||'All properties';
const sections=()=>state.context.sections.filter(s=>s.active&&(!state.property||String(s.property_id)===state.property));
const monthLabel=()=>new Date(state.month+'-01T12:00:00').toLocaleDateString('en-IN',{month:'long',year:'numeric'});
function shiftMonth(m,delta){const [y,mon]=(m||state.context.today.slice(0,7)).split('-').map(Number);const d=new Date(Date.UTC(y,mon-1+delta,1));return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}`}
const statusBadge=s=>`<span class="badge ${s==='CLOSED'?'green':s==='SUBMITTED'?'amber':''}">${esc(s.toLowerCase().replace('in progress','In progress'))}</span>`;
const thumb=r=>r&&r.photo?`<img class="thumb" src="/photo/thumb-${esc(r.photo)}" data-full-photo="${esc(r.photo)}" data-item-name="${esc(r.name||'')}" alt="${esc(r.name||'')}" title="Click to view photo" loading="lazy">`:`<span class="thumb" title="${esc(r?.name||'No image')}">${icon('box')}</span>`;
const itemCell=r=>`<div class="item-cell">${thumb(r)}<div><strong>${esc(r.name)}</strong><small>${esc(r.code?(r.code+' · '):'')}${esc(r.section||'')}</small></div></div>`;
document.addEventListener('click',e=>{const t=e.target.closest('img.thumb, [data-full-photo]');if(t&&t.dataset.fullPhoto){e.stopPropagation();const name=t.dataset.itemName||t.alt||'Item Photo';showModal(name,`<div style="text-align:center"><img class="preview-full" src="/photo/${esc(t.dataset.fullPhoto)}" alt="${esc(name)}"><p style="margin-top:12px;font-weight:600;font-size:14px;color:var(--ink)">${esc(name)}</p></div>`)}});
function field(label,name,type='text',value='',required=false,extra=''){return `<div class="field"><label for="f-${name}">${label}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${required?'required':''} ${extra}></div>`}
function selectField(label,name,options,value=''){return `<div class="field"><label for="f-${name}">${label}</label><select name="${name}" id="f-${name}">${options.map(o=>`<option value="${esc(o[0])}" ${String(o[0])===String(value)?'selected':''}>${esc(o[1])}</option>`).join('')}</select></div>`}
function showModal(title,body,onSubmit){const d=$('#modal');d.innerHTML=`<div class="modal-head"><h2>${title}</h2><button class="ghost" type="button" data-close aria-label="Close dialog">✕</button></div><div class="modal-body">${onSubmit?'<form id="dialog-form"><div class="modal-content">':''}${body}<div class="error" role="alert"></div>${onSubmit?'</div><div class="modal-actions"><button type="button" data-close>Cancel</button><button type="submit" class="primary">Save changes</button></div></form>':''}</div>`;$$('[data-close]',d).forEach(b=>b.onclick=()=>d.close());if(!d.open)d.showModal();if(onSubmit)$('#dialog-form').onsubmit=async e=>{e.preventDefault();const btn=$('[type=submit]',e.target);btn.disabled=true;try{await onSubmit(Object.fromEntries(new FormData(e.target)),e.target);d.close();await render()}catch(err){$('.error',d).textContent=err.message;$('.error',d).classList.add('visible')}finally{btn.disabled=false}};}
async function boot(){try{const s=await api('/session');state.csrf=s.csrf;state.user=s.user;if(!s.user)return auth(s);state.context=await api('/context');if(!state.context.properties.some(p=>String(p.id)===state.property))state.property=String(state.context.properties[0]?.id||'');state.month=state.context.today.slice(0,7);await render();await syncDrafts()}catch(e){$('#app').innerHTML=`<div class="empty">${esc(e.message)}<br><button id="retry">Try again</button></div>`;$('#retry').onclick=boot}}
function auth(info){
 clearTimeout(toast.timer);$("#toast").classList.remove("show");state.notifications=null;state.page="dashboard";state.items=[];state.countData=null;state.countSection=null;state.section="";state.month="";if($("#modal").open)$("#modal").close();$("#modal").replaceChildren();
 const error=new URLSearchParams(location.search).get('login_error');
 const errors={};
 $('#app').innerHTML=`<div class="auth"><section class="auth-story"><div class="brand"><img src="/static/travelicious-logo.png" alt="Travelicious logo"><div><strong>Travelicious</strong><small>Inventory Management</small></div></div><div><div class="eyebrow">TRAVELLERS CAVERN × TRAVELICIOUS</div><h1>A place for<br>everything.<br>A record of it all.</h1><p>Your properties. Your team. The right access for every person.</p></div><small>Thoughtful hospitality starts behind the scenes.</small></section><section class="auth-box"><div class="auth-form"><div class="eyebrow">YOUR OPERATIONS, TOGETHER</div><h2>Welcome back</h2><p>Sign in with your email or username to access your workspace.</p>${error?`<div class="error visible" role="alert">${esc(errors[error]||'Sign-in failed. Try again.')}</div>`:''}<form id="password-login">${field('Email or Username','username','text','',true,'autocomplete="username" placeholder="Enter email or username"')}${field('Password','password','password','',true,'autocomplete="current-password" placeholder="Enter password"')}<label><input id="show-password" type="checkbox"> Show password</label><div class="error" role="alert"></div><button class="primary" type="submit">Sign in →</button></form></div></section></div>`;
 $('#show-password').onchange=e=>$('#f-password').type=e.target.checked?'text':'password';
 $('#password-login').onsubmit=async e=>{e.preventDefault();const b=$('[type=submit]',e.target);b.disabled=true;try{await api('/login','POST',Object.fromEntries(new FormData(e.target)));history.replaceState(null,'','/');await boot()}catch(err){$('.error',e.target).textContent=err.message;$('.error',e.target).classList.add('visible');b.disabled=false}};
}
const pageNames={addstock:'Add items / purchases',corrections:'Corrections',reviews:'Reports & approvals',dashboard:'Overview',inventory:'Inventory',assets:'Property assets',counts:'Monthly count',breakage:'Breakage',reports:'Reports',users:'Team members',settings:'Settings',audit:'Audit trail'};
function shell(){if(staffMode())return staffShell();const nav=[['dashboard','home','Overview'],...(state.user.is_owner?[['reviews','audit','Reports & approvals']]:[]),...(can('inventory')?[['inventory','box','Inventory']]:[]),...(can('assets')?[['assets','asset','Assets']]:[]),...((can('counts')||can('review_counts'))?[['counts','count','Monthly count']]:[]),...(can('breakage')?[['breakage','break','Breakage']]:[]),...(can('reports')?[['reports','report','Reports']]:[]),...(can('users')?[['users','users','Team & access']]:[]),['settings','settings',fullAdmin()?'Settings':'Account'],...(can('audit')?[['audit','audit','Audit trail']]:[])];$('#app').innerHTML=`<div class="shell"><aside class="sidebar"><div class="brand"><img src="/static/travelicious-logo.png" alt="Travelicious logo"><div><strong>Travelicious</strong><small>Inventory Management</small></div></div><div class="navlabel">WORKSPACE</div><nav class="nav" aria-label="Main navigation">${nav.map(([p,i,l])=>`<button data-page="${p}" class="${p===state.page?'active':''}">${icon(i)}<span>${l}</span></button>`).join('')}</nav><div class="sidebar-foot"><div class="workspace-note"><strong>Every item, accounted for.</strong>One workspace. Two properties.<br>A clearer picture of your operations.</div><div class="profile"><span class="avatar">${esc(state.user.name[0].toUpperCase())}</span><div><strong>${esc(state.user.name)}</strong><small>${state.user.role==='MASTER'?'Master':state.user.role==='ADMIN'?(fullAdmin()?'Admin · full access':'Admin · restricted'):'Staff member'}</small></div><button class="ghost small" id="logout" aria-label="Log out">Log out</button></div></div></aside><div class="main"><header class="topbar"><div class="breadcrumbs">Workspace <span>/</span> <strong>${pageNames[state.page]}</strong></div><div class="topfilters"><span class="connection ${navigator.onLine?'':'offline'}">${navigator.onLine?'Workspace connected':'Offline · drafts saved'}</span><select id="property" aria-label="Property">${master()?'<option value="">All properties</option>':''}${state.context.properties.map(p=>`<option value="${p.id}" ${String(p.id)===state.property?'selected':''}>${p.name}</option>`).join('')}</select><span id="workspace-month" class="badge ${state.month===state.context.today.slice(0,7)?'green':'amber'}" aria-label="Reporting month">${monthLabel()}${state.month===state.context.today.slice(0,7)?' · automatic':''}</span><div class="account-controls">${state.user.role==='MASTER'?`<button type="button" id="notifications-button" class="notification-button" aria-label="Notifications">${icon('audit')}<span class="notification-label">Notifications</span><span id="notification-count" class="notification-count" hidden>0</span></button>`:''}<button id="profile-button" class="profile-button" aria-haspopup="dialog" aria-label="Open profile"><span class="avatar">${esc(state.user.name[0].toUpperCase())}</span><span class="profile-label">Profile</span><span aria-hidden="true">⌄</span></button></div></div></header><main id="main"></main></div></div>`;$$('[data-page]').forEach(b=>b.onclick=()=>{state.page=b.dataset.page;state.countSection=null;if(!['dashboard','reports','breakage'].includes(state.page))state.month=state.context.today.slice(0,7);render()});$('#property').value=state.property;$('#property').onchange=e=>{state.property=e.target.value;state.section='';state.countSection=null;render()};$('#logout').onclick=logout;$('#profile-button').onclick=profileMenu;if($('#notifications-button'))$('#notifications-button').onclick=notificationInbox;refreshNotifications();}
async function logout(){if(Object.keys(drafts()).length&&!confirm('There are unsynced count drafts on this device. Sign out and keep them for your next login?'))return;await api('/logout','POST',{});state.user=null;boot()}
function pageHead(title,subtitle,actions=''){return `<div class="page-head"><div><div class="eyebrow">${esc(prop())} / ${monthLabel()}</div><h1>${title}</h1><p>${subtitle}</p></div><div class="actions">${actions}</div></div>`}
async function render(){if(staffMode()&&!['dashboard','counts','addstock','corrections','settings'].includes(state.page))state.page='dashboard';if(!state.user.is_owner&&['reviews','reports'].includes(state.page))state.page='dashboard';if(!can('assets')&&state.page==='assets')state.page='dashboard';const version=++renderVersion;shell();const mainEl=$('#main');if(mainEl)mainEl.innerHTML=`<div class="loading"><div class="spinner"></div>Loading ${pageNames[state.page]||'workspace'}…</div>`;try{const html=await ({corrections:reviewsPage,addstock:staffAddPage,reviews:reviewsPage,dashboard:dashboard,inventory:inventory,assets:assetsPage,counts:countsPage,breakage:breakagePage,reports:reportsPage,users:usersPage,settings:settingsPage,audit:auditPage}[state.page])();if(version!==renderVersion)return;$('#main').innerHTML=html;bindPage();refreshReviewBadge();}catch(e){if(version===renderVersion)$('#main').innerHTML=`<div class="empty">${esc(e.message)}<br><button id="page-retry">Try again</button></div>`;if($('#page-retry'))$('#page-retry').onclick=render}}
const empty=(text,i='box')=>`<div class="empty">${icon(i)}<br>${text}</div>`;
async function dashboard(){if(staffMode())return staffDashboard();const [items,counts,events]=await Promise.all([can('inventory')?(state.items?.length&&(!state.property||String(state.items[0]?.property_id)===state.property)?Promise.resolve(state.items):api('/items?property='+state.property)):Promise.resolve([]),(can('counts')||can('review_counts'))?api('/counts?month='+state.month):Promise.resolve([]),(can('inventory')||can('purchases')||can('breakage')||can('reports'))?api('/events?property='+state.property+'&month='+state.month):Promise.resolve([])]);state.items=items;const cs=counts.filter(c=>!state.property||String(c.property_id)===state.property),pending=cs.filter(c=>c.total&&c.status!=='CLOSED');const br=events.filter(e=>['BREAKAGE','DAMAGE'].includes(e.type));const purchase=events.filter(e=>['OPENING','PURCHASE'].includes(e.type));const purchaseVal=purchase.reduce((a,r)=>a+Math.abs(r.qty)*(r.rate||0),0);const breakageVal=br.reduce((a,r)=>a+Math.abs(r.qty)*(r.rate||0),0);const breakageQty=br.reduce((a,r)=>a+Math.abs(r.qty),0);const isCurrentMonth=state.month===state.context.today.slice(0,7);const monthBar=master()?`<div class="dashboard-month-bar"><div class="month-indicator"><span class="eyebrow" style="margin:0">MONTHLY METRICS</span><strong class="month-title">${monthLabel()}</strong>${isCurrentMonth?'<span class="badge green">Current month (automatic)</span>':'<span class="badge amber">Historical month</span>'}</div><div class="month-controls"><label for="dashboard-month-select" class="month-select-label">Change month:</label><div class="month-nav-group"><button type="button" id="dashboard-prev-month" class="ghost small" title="Previous month">‹ Previous</button><input type="month" id="dashboard-month-select" value="${state.month}" max="${state.context.today.slice(0,7)}" aria-label="Reporting month"><button type="button" id="dashboard-next-month" class="ghost small" title="Next month" ${state.month>=state.context.today.slice(0,7)?'disabled':''}>Next ›</button>${!isCurrentMonth?'<button type="button" id="dashboard-today-btn" class="small ghost">↺ Today’s month</button>':''}</div></div></div>`:'';return pageHead(master()?'Inventory overview':'Your daily workspace',master()?'A little clarity for everything behind the scenes.':'Choose an action to keep your property running smoothly.',`<button data-additem class="primary">+ Add item</button>`)+`<section class="welcome"><div><div class="eyebrow">A WELL-KEPT WORKSPACE</div><h2>${master()?'Small details. Smooth operations.':'Let’s get everything accounted for.'}</h2><p>${master()?`Your ${monthLabel()} inventory is ready. Review section counts, record new purchases, and keep your team on the same page.`:'Count what you see, record stock as it arrives, and capture any damage with a photo.'}</p></div><button class="lime" data-nav="counts">${master()?'Review monthly counts':'Start a monthly count'} &nbsp; →</button></section>`+monthBar+(master()?`<div class="stats">${stat('Active items',items.length,'Across '+cs.length+' sections','box','inventory')}${stat('Counts pending',pending.length,pending.length?`${pending.length} section${pending.length===1?'':'s'} awaiting ${monthLabel()} close`:`All sections closed for ${monthLabel()}`,'count','counts')}${stat('Purchase value',rupees(purchaseVal),`${purchase.length} stock addition${purchase.length===1?'':'s'} in ${monthLabel()}`,'report','reports','purchases')}${stat('Breakage value',rupees(breakageVal),`${breakageQty} item${breakageQty===1?'':'s'} recorded in ${monthLabel()}`,'break','breakage')}</div>`:`<div class="actions" style="margin-bottom:24px"><button class="primary" data-move="PURCHASE">+ Add stock / purchase</button><button data-move="BREAKAGE">Report breakage</button><button data-nav="counts">Monthly count</button></div>`)+`<div class="dashboard-grid"><div><section class="panel"><div class="panel-head"><div><h2>Monthly inventory</h2><p>Section-by-section progress · ${monthLabel()}</p></div><button class="ghost small" data-nav="counts">View all →</button></div>${cs.map(c=>`<div class="section-row"><span class="section-icon">${icon('box')}</span><div class="section-title"><strong>${esc(c.name)}</strong><small>${c.completed} of ${c.total} items counted</small></div><div>${statusBadge(c.total?c.status:'EMPTY')}<div class="progress"><span style="width:${c.total?c.completed/c.total*100:0}%"></span></div></div><button class="ghost small" data-count="${c.id}" aria-label="Open ${esc(c.name)} count">→</button></div>`).join('')}</section>${master()&&items.some(i=>!i.photo)?`<div class="notice"><strong>Your catalogue is ready for its finishing touches.</strong><br>${items.filter(i=>!i.photo).length} items need reference photos. Add specifications, opening stock and rates before your first count. <button class="ghost small" data-nav="inventory">Review items →</button></div>`:''}</div><div><section class="panel"><div class="panel-head"><div><h2>Quick actions</h2><p>The everyday essentials, one click away.</p></div></div><div class="panel-body"><div class="nav"><button data-move="PURCHASE">${icon('plus')} Add stock / purchase <span class="spacer"></span>→</button><button data-move="BREAKAGE">${icon('break')} Report breakage <span class="spacer"></span>→</button><button data-nav="${master()?'reports':'counts'}">${icon('report')} ${master()?'Download a report':'Continue counting'} <span class="spacer"></span>→</button></div></div></section><section class="panel"><div class="panel-head"><div><h2>Recent activity</h2><p>${master()?'Stock movements · '+monthLabel():'Your recent submissions'}</p></div><span class="badge">${events.length} records</span></div>${events.length?events.slice(0,5).map(e=>`<div class="activity"><span class="dot"></span><div><strong>${esc(e.name)}</strong><p>${esc(e.type.toLowerCase())} · ${Math.abs(e.qty)} items ${master()?'· '+esc(e.staff):''}</p><small>${esc(e.date)}</small></div></div>`).join(''):empty('No stock movements recorded for '+monthLabel()+'.','audit')}</section></div></div><div class="footer-note">TRAVELLERS CAVERN × TRAVELICIOUS &nbsp; · &nbsp; EVERY ITEM HAS A PLACE.</div>`}
function stat(label,value,foot,i,nav,reportKind){return `<div class="stat ${nav?'clickable':''}" ${nav?`data-nav="${nav}" ${reportKind?`data-report-kind="${reportKind}"`:''} tabindex="0" role="button" aria-label="View ${label}"`:''}><div class="stat-top">${label}${icon(i)}</div><div class="stat-value">${value}</div><div class="stat-foot">${foot}</div></div>`}
function bulkToolbar(){
 if(!can('edit_items'))return '';
 const n=state.selectedItems?.size||0;
 return `<div id="bulk-toolbar" class="bulk-toolbar" style="display:${n?'flex':'none'}"><span class="bulk-count"><strong>${n}</strong> item${n===1?'':'s'} selected</span><div class="actions"><button type="button" id="bulk-move-btn" class="primary small">📦 Move selected</button><button type="button" id="bulk-delete-btn" class="danger small">🗑 Delete selected</button><button type="button" id="bulk-clear-btn" class="ghost small">✕ Clear</button></div></div>`;
}
async function inventory(){
 state.items=await api('/items?property='+state.property);
 if(!state.selectedItems)state.selectedItems=new Set();
 return pageHead('Item catalogue','A home for every item, across every section.',`<button class="primary" data-addinventory>+ Add inventory</button>`)+`<section class="panel"><div class="toolbar"><input type="search" id="item-search" placeholder="Search item name, serial number or code…" aria-label="Search items" value="${esc(state.search)}">${master()?`<select id="inventory-property-filter" aria-label="Property filter"><option value="" ${state.property===''?'selected':''}>All properties</option>${state.context.properties.map(p=>`<option value="${p.id}" ${String(p.id)===state.property?'selected':''}>${esc(p.name)}</option>`).join('')}</select>`:''}<select id="section-filter" aria-label="Section"><option value="">All sections</option>${sections().map(s=>`<option value="${s.id}" ${String(s.id)===state.section?'selected':''}>${esc(s.name)}</option>`).join('')}</select><span class="badge">${state.items.length} items</span></div>${bulkToolbar()}<div id="item-table">${inventoryTable()}</div></section>`
}
function inventoryTable(){
 const canEdit=can('edit_items');
 if(!state.selectedItems)state.selectedItems=new Set();
 const items=state.items.filter(r=>(!state.section||String(r.section_id)===state.section)&&(!state.search||`${r.name} ${r.code}`.toLowerCase().includes(state.search.toLowerCase())));
 const allSelected=items.length>0&&items.every(r=>state.selectedItems.has(r.id));
 return items.length?`<div class="table-wrap"><table><thead><tr>${canEdit?`<th style="width:40px;text-align:center"><input type="checkbox" id="select-all-items" ${allSelected?'checked':''} aria-label="Select all visible items"></th>`:''}<th>Serial No.</th><th>Item</th><th>Section</th><th>Specification</th>${master()?'<th>Stock</th><th>Unit rate</th>':''}<th>Readiness</th><th></th></tr></thead><tbody>${items.map(r=>{const isSel=state.selectedItems.has(r.id);return `<tr class="${isSel?'selected':''}" data-item-row="${r.id}">${canEdit?`<td style="text-align:center"><input type="checkbox" data-select-item="${r.id}" ${isSel?'checked':''} aria-label="Select ${esc(r.name)}"></td>`:''}<td><span class="badge" style="font-family:monospace;font-weight:600;letter-spacing:0.5px">${esc(r.code||'—')}</span></td><td class="name">${itemCell(r)}</td><td>${esc(r.section)}</td><td>${esc(r.specification)||'<span class="badge">Needs details</span>'}</td>${master()?`<td>${qty(r.stock)} <small>${esc(r.unit)}</small></td><td>${r.rate==null?'<span class="badge amber">Rate missing</span>':rupees(r.rate)}</td>`:''}<td>${r.photo?'<span class="badge green">Photo added</span>':'<span class="badge amber">Photo needed</span>'}</td><td><button class="small ghost" data-item="${r.id}">${master()?'View item':can('purchases')?'Add stock':'View details'} →</button></td></tr>`}).join('')}</tbody></table></div><div class="table-footer">Showing ${items.length} items · ${master()?'Stock is calculated from ledger and closed counts.':'Counted quantities remain private to your Master.'}</div>`:empty('No matching items. Try another section or add an item.')
}
async function countsPage(){if(state.countSection)return countView();if(!state.context)state.context=await api('/context');state.month=state.context.today.slice(0,7);if($('#staff-count-month'))$('#staff-count-month').textContent=monthLabel()+' · automatic';if($('#workspace-month'))$('#workspace-month').textContent=monthLabel()+' · automatic';const cc=(await api('/counts?month='+state.month)).filter(c=>!state.property||String(c.property_id)===state.property);return pageHead('Monthly inventory','Count each item, review your entries, then submit the section.')+`<div class="notice"><strong>${master()?'A clear close, a reliable start.':'Blind counting is on.'}</strong> ${master()?'Once closed, actual quantities become the next period’s opening stock. Submitted sections are locked until reopened.':'Enter the quantities you physically see. Expected stock and differences are only available to authorized reviewers.'}</div><div class="section-cards">${cc.map(c=>`<section class="section-card"><div class="row"><span class="section-icon">${icon('count')}</span><span class="spacer"></span>${statusBadge(c.status)}</div><h3>${esc(c.name)}</h3><p>${state.context.properties.find(p=>p.id===c.property_id)?.name} · ${c.total} items</p><div class="progress"><span style="width:${c.total?100*c.completed/c.total:0}%"></span></div><div class="row"><span class="help">${c.completed} of ${c.total} counted</span><span class="spacer"></span><button data-count="${c.id}" class="small primary">${c.status==='CLOSED'?'View count':'Open count'} →</button></div></section>`).join('')}</div>`}
function drafts(){try{return JSON.parse(localStorage.getItem('count-drafts-'+state.user.id)||'{}')}catch{return {}}}
function writeDraft(k,v){const d=drafts();if(v===null)delete d[k];else d[k]=v;localStorage.setItem('count-drafts-'+state.user.id,JSON.stringify(d))}
function isItemCounted(r){return r.actual!==null&&r.actual!==''&&r.actual!==undefined}

function updateCountBadges(data){
 if(!data||!data.items)return;
 const counted=data.items.filter(isItemCounted).length;
 const uncounted=data.items.length-counted;
 const bu=$('#badge-uncounted'),bc=$('#badge-counted'),ba=$('#badge-all'),cp=$('#count-progress');
 if(bu){bu.textContent=uncounted;bu.classList.toggle('amber',uncounted>0)}
 if(bc)bc.textContent=counted;
 if(ba)ba.textContent=data.items.length;
 if(cp)cp.textContent=counted;
}

function countItemsTable(data,locked){
 if(!data.items.length)return empty('There are no items in this section yet.','count');
 const q=(state.countSearch||'').trim().toLowerCase();
 let visible=data.items;
 if(state.countTab==='remaining')visible=visible.filter(r=>!isItemCounted(r));
 else if(state.countTab==='counted')visible=visible.filter(isItemCounted);
 if(q)visible=visible.filter(r=>`${r.name} ${r.code||''} ${r.specification||''}`.toLowerCase().includes(q));

 if(!visible.length){
  if(state.countTab==='remaining'&&data.items.every(isItemCounted)){
   return `<div class="empty" style="padding:40px 20px;text-align:center"><div style="font-size:36px;margin-bottom:10px">🎉</div><h3 style="font-size:17px;font-weight:700;margin-bottom:6px">All items counted!</h3><p class="help" style="max-width:440px;margin:0 auto 16px">Every item in this section has been marked Done and saved.</p><div class="actions" style="justify-content:center;gap:10px">${!locked?'<button type="button" class="primary" id="submit-from-empty">Submit full section to master →</button>':''}<button type="button" class="ghost" data-count-filter="counted">Review counted items</button></div></div>`;
  }
  if(state.countTab==='remaining')return empty('No uncounted items remaining'+(q?' matching your search':'')+'.','count');
  if(state.countTab==='counted')return empty('No items have been counted yet. Enter actual counts and click Done.','count');
  return empty('No matching items found.','count');
 }

 return `<div class="table-wrap"><table class="count-table"><thead><tr><th>Serial No.</th><th>Item</th>${master()?'<th>Previous</th><th>Added</th><th>Damage</th><th>Expected</th>':''}<th>Actual count</th>${master()?'<th>Difference</th>':''}<th>Status / note</th></tr></thead><tbody>${visible.map(r=>{
  const counted=isItemCounted(r);
  return `<tr data-line="${r.id}" class="${counted?'counted-row':''}"><td><span class="badge" style="font-family:monospace;font-weight:600;letter-spacing:0.5px">${esc(r.code||'—')}</span></td><td class="name">${itemCell(r)}<small>${esc(r.specification||'')}</small><small>Counted by: ${esc(r.submitted_by||'Not yet counted')}</small></td>${master()?`<td>${qty(r.previous)}</td><td>${qty(r.added)}</td><td>${qty(r.damage)}</td><td>${qty(r.expected)}</td>`:''}<td><div class="count-input-group"><input class="count-input" data-actual type="number" min="0" step="1" value="${counted?r.actual:''}" ${locked||(data.status==='RETURNED'&&(!r.review_note||data.submitter?.id!==state.user.id))?'disabled':''} aria-label="Actual ${esc(r.name)}" placeholder="0">${!locked?`<button type="button" class="primary small count-done-btn" data-done-line="${r.id}" title="Save count and mark done">✓ Done</button>${counted?`<button type="button" class="ghost small count-undone-btn" data-uncount-line="${r.id}" title="Reset to uncounted">↺ Reset</button>`:''}`:''}</div><small data-saved class="saved"></small></td>${master()?`<td class="${(r.difference||0)<0?'negative':''}" data-difference>${counted?qty(r.difference):'—'}${counted&&r.difference?'<small>Unexplained difference</small>':''}</td>`:''}<td><select data-flag ${locked||(data.status==='RETURNED'&&(!r.review_note||data.submitter?.id!==state.user.id))?'disabled':''} aria-label="Count status ${esc(r.name)}"><option value="">Counted</option><option value="NOT_FOUND" ${r.flag==='NOT_FOUND'?'selected':''}>Not found</option><option value="NOT_APPLICABLE" ${r.flag==='NOT_APPLICABLE'?'selected':''}>Not applicable</option></select><input data-note class="count-note" placeholder="Note / exception reason" value="${esc(r.note||'')}" ${locked||(data.status==='RETURNED'&&(!r.review_note||data.submitter?.id!==state.user.id))?'disabled':''} aria-label="Note ${esc(r.name)}">${r.review_note?`<p class="notice">${r.needs_correction?'Correction needed':'Review note'}: ${esc(r.review_note)}</p>`:''}${data.can_review&&['SUBMITTED','RETURNED'].includes(data.status)?`<label class="count-mark"><input type="checkbox" data-mark-count value="${r.id}"> Mark for recheck</label>`:''}</td></tr>`;
 }).join('')}</tbody></table></div>`;
}

function bindCountRows(data,locked){
 if(!data)return;
 const container=$('#count-items-container');
 if(!container)return;

 const submitEmpty=$('#submit-from-empty',container);
 if(submitEmpty)submitEmpty.onclick=()=>$('#submit-count')?.click();

 $$('[data-count-filter]',container).forEach(b=>{
  b.onclick=()=>{
   state.countTab=b.dataset.countFilter;
   $$('[data-count-filter]').forEach(btn=>btn.classList.toggle('active',btn.dataset.countFilter===state.countTab));
   container.innerHTML=countItemsTable(data,locked);
   bindCountRows(data,locked);
  };
 });

 $$('[data-actual]',container).forEach(input=>{
  input.onkeydown=e=>{
   if(e.key==='Enter'){
    e.preventDefault();
    const row=input.closest('tr');
    $('[data-done-line]',row)?.click();
   }
  };
 });

 $$('[data-flag],[data-note]',container).forEach(input=>{
  input.onchange=async()=>{
   const row=input.closest('tr');
   const itemId=Number(row?.dataset.line);
   const r=data.items.find(i=>i.id===itemId);
   if(!r)return;
   r.flag=$('[data-flag]',row)?.value||'';
   r.note=$('[data-note]',row)?.value||'';
   if(isItemCounted(r)){
    const key=`${state.countSection}/${state.month}/${r.id}`;
    writeDraft(key,{item_id:r.id,actual:r.actual,note:r.note,flag:r.flag});
    await syncDrafts();
   }
  };
 });

 $$('[data-done-line]',container).forEach(btn=>{
  btn.onclick=async()=>{
   const row=btn.closest('tr');
   const itemId=Number(btn.dataset.doneLine);
   const r=data.items.find(i=>i.id===itemId);
   const a=$('[data-actual]',row);
   if(!a||a.value.trim()===''){toast('Enter a quantity of 0 or more before clicking Done.');a?.focus();return}
   const val=a.value.trim();
   if(!Number.isInteger(Number(val))||Number(val)<0){toast('Enter a whole quantity of zero or more.');a.focus();return}
   const flag=$('[data-flag]',row)?.value||'';
   const note=$('[data-note]',row)?.value||'';
   if(flag&&!note.trim()){toast('Add a note for this exception.');return}

   r.actual=Number(val);
   r.flag=flag;
   r.note=note;
   if(r.expected!=null)r.difference=Number(val)-Number(r.expected);

   const key=`${state.countSection}/${state.month}/${r.id}`;
   writeDraft(key,{item_id:r.id,actual:r.actual,note,flag});
   const savedEl=$('[data-saved]',row);
   if(savedEl)savedEl.textContent='Saving…';
   await syncDrafts();
   if(savedEl)savedEl.textContent=drafts()[key]?'Saved on device':'Saved';

   updateCountBadges(data);
   toast(`Recorded: ${r.name} = ${r.actual}`);
   if(data.items.every(isItemCounted)){
    try{
     await api('/counts/'+state.countSection+'/'+state.month,'POST',{action:'submit'});
     data.status='SUBMITTED';
     toast('All items counted! Count list automatically pushed to master for approval.');
    }catch(e){}
   }

   if(state.countTab==='remaining'){
    row.classList.add('count-row-fade');
    setTimeout(()=>{
     container.innerHTML=countItemsTable(data,locked);
     bindCountRows(data,locked);
    },200);
   }else{
    container.innerHTML=countItemsTable(data,locked);
    bindCountRows(data,locked);
   }
  };
 });

 $$('[data-uncount-line]',container).forEach(btn=>{
  btn.onclick=()=>{
   const itemId=Number(btn.dataset.uncountLine);
   const r=data.items.find(i=>i.id===itemId);
   if(!r)return;
   r.actual=null;
   r.flag='';
   r.note='';
   if(r.expected!=null)r.difference=null;
   const key=`${state.countSection}/${state.month}/${r.id}`;
   writeDraft(key,null);
   updateCountBadges(data);
   toast(`Reset ${r.name} to uncounted`);
   container.innerHTML=countItemsTable(data,locked);
   bindCountRows(data,locked);
  };
 });
}

async function countView(){
 const data=await api(`/counts/${state.countSection}/${state.month}`);
 state.countData=data;
 if(!state.countTab)state.countTab='remaining';
 const sec=state.context.sections.find(s=>s.id===state.countSection);
 const locked=['SUBMITTED','CLOSED'].includes(data.status)||!can('counts')||(data.submitter&&data.submitter.id!==state.user.id&&!data.can_review);
 const local=drafts();
 for(const r of data.items){const d=local[`${state.countSection}/${state.month}/${r.id}`];if(d&&!locked)Object.assign(r,d)}
 const countedCount=data.items.filter(isItemCounted).length;
 const uncountedCount=data.items.length-countedCount;

 return pageHead(esc(sec.name)+' · Physical count',staffMode()?'Enter the quantity you physically counted for each item. Click Done to submit an item.':'Expected = previous accepted count + approved stock − approved breakage. Differences need admin review.',`<button id="back-counts">← All sections</button>`)+`<section class="panel"><div class="panel-head"><div><h2>${monthLabel()} ${statusBadge(data.status)}</h2><p>${data.submitter?`Submitted by ${esc(data.submitter.username)} · ID ${data.submitter.id} · `:''}<span id="count-progress">${countedCount}</span> / ${data.items.length} items counted · <span id="sync-status">${Object.keys(local).length?'Pending drafts':'All changes saved'}</span></p></div><div class="actions">${state.user.is_owner&&!['SUBMITTED','CLOSED','RETURNED'].includes(data.status)?'<button id="share-count">Share with staff</button>':''}${!locked?'<button id="submit-count" class="primary">Submit full section</button>':''}${data.can_review&&data.status==='SUBMITTED'?'<button id="close-count" class="primary">Accept & close month</button>':''}${data.can_review&&['SUBMITTED','RETURNED'].includes(data.status)?'<button id="return-count-list">Return marked items</button>':''}${data.can_review&&['SUBMITTED','CLOSED'].includes(data.status)?'<button id="reopen-count">Reopen</button>':''}</div></div>${data.items.some(r=>r.needs_correction)?`<div class="notice"><strong>Items to recheck</strong>${data.items.filter(r=>r.needs_correction).map(r=>`<p>${esc(r.name)}: ${esc(r.review_note)}</p>`).join('')}</div>`:''}<div class="count-filter-bar"><div class="count-filter-tabs" role="tablist"><button type="button" class="count-tab ${state.countTab==='remaining'?'active':''}" data-count-filter="remaining" role="tab" aria-selected="${state.countTab==='remaining'}"><span>To Count (Remaining)</span><span class="count-badge ${uncountedCount>0?'amber':''}" id="badge-uncounted">${uncountedCount}</span></button><button type="button" class="count-tab ${state.countTab==='counted'?'active':''}" data-count-filter="counted" role="tab" aria-selected="${state.countTab==='counted'}"><span>Already Counted</span><span class="count-badge" id="badge-counted">${countedCount}</span></button><button type="button" class="count-tab ${state.countTab==='all'?'active':''}" data-count-filter="all" role="tab" aria-selected="${state.countTab==='all'}"><span>All Items</span><span class="count-badge" id="badge-all">${data.items.length}</span></button></div><div class="count-search-box"><input type="search" id="count-search-input" placeholder="Search item name or serial number…" value="${esc(state.countSearch||'')}" aria-label="Search items in section"></div></div><div id="count-items-container">${countItemsTable(data,locked)}</div></section><p class="help">${locked?'This count is read-only. Reopening requires review permission and a recorded reason.':'Enter count and click Done. Counted items move out of the uncounted view so you can focus on remaining items. You can view or reset already counted items in the "Already Counted" tab.'}</p>`;
}
let syncRunning=false;
async function syncDrafts(){if(!state.user||syncRunning||!navigator.onLine)return;syncRunning=true;let progressed=false;try{for(const [k,v]of Object.entries(drafts())){try{await api('/counts/'+k.split('/').slice(0,2).join('/'),'POST',{...v,action:'save'});const current=drafts()[k];if(JSON.stringify(current)===JSON.stringify(v))writeDraft(k,null);progressed=true}catch(e){if($('#sync-status'))$('#sync-status').textContent=e.message;break}}if($('#sync-status'))$('#sync-status').textContent=Object.keys(drafts()).length?'Drafts pending — reconnect or resolve count lock':'All changes saved'}finally{syncRunning=false;if(progressed&&Object.keys(drafts()).length)setTimeout(syncDrafts,300)}}
async function breakagePage(){
 const events=(await api('/events?month='+state.month+'&property='+state.property)).filter(e=>['BREAKAGE','DAMAGE'].includes(e.type));
 return pageHead('Breakage','Photograph the item, explain what happened, and send your report.',`<button class="primary" data-move="BREAKAGE">Report breakage</button>`)+`<div class="breakage-guide"><div><span>1</span><strong>Take a photo</strong><small>Capture the broken item</small></div><div><span>2</span><strong>Select section & item</strong><small>Enter quantity and reason</small></div><div><span>3</span><strong>Send report</strong><small>Master gets a notification</small></div></div>`+(master()?`<div class="stats breakage-stats">${stat('Reported items',events.reduce((a,r)=>a+Math.abs(r.qty),0),'Recorded this month','break')}${stat('Recorded loss',rupees(events.reduce((a,r)=>a+Math.abs(r.qty)*(r.rate||0),0)),'Event-time rates preserved','report')}${stat('Missing rates',events.filter(r=>r.rate===null).length,'Excluded from loss totals','audit')}</div>`:'')+`<section class="panel"><div class="panel-head"><h2>${master()?'Breakage reports':'Your reports'}</h2><span class="badge">${events.length} records</span></div>${events.length?eventTable(events):empty('No breakage reports this month.','break')}</section>`;
}
function eventTable(events){return `<div class="table-wrap"><table><thead><tr><th>Item / evidence</th><th>Type</th><th>Quantity</th><th>Reason</th>${master()?'<th>Rate</th><th>Value</th><th>Staff</th>':''}<th>Date</th></tr></thead><tbody>${events.map(r=>`<tr data-event-id="${r.id}"><td class="name"><div class="item-cell">${r.photo?`<button class="ghost small" data-photo="${esc(r.photo)}">${thumb(r)}</button>`:thumb(r)}<div><strong>${esc(r.name)}</strong><small>${esc(r.code?(r.code+' · '):'')}${esc(r.section||'')}</small></div></div></td><td>${esc(r.type.toLowerCase())}</td><td>${Math.abs(r.qty)}</td><td>${esc(r.reason||'Stock received')}<small>${esc(r.note)}</small></td>${master()?`<td>${rupees(r.rate)}</td><td>${r.rate===null?'Rate missing':rupees(Math.abs(r.qty)*r.rate)}</td><td>${esc(r.staff)}</td>`:''}<td>${esc(r.date)}</td></tr>`).join('')}</tbody></table></div>`}
function inventoryReport(rr){if(!rr||!rr.length)return empty('No inventory records found for this period and section.');return `<div class="table-wrap"><table><thead><tr><th>Serial No.</th><th>Item</th><th>Section</th><th>Prev Stock</th><th>Added</th><th>Damage</th><th>Counted</th><th>Expected</th><th>Difference</th><th>Rate</th><th>Status</th></tr></thead><tbody>${rr.map(r=>`<tr><td><span class="badge" style="font-family:monospace;letter-spacing:0.5px;font-weight:600">${esc(r.code||'—')}</span></td><td class="name"><div class="item-cell">${thumb(r)}<div><strong>${esc(r.name)}</strong></div></div></td><td>${esc(r.section||'')}</td><td>${qty(r.previous)}</td><td>${qty(r.added)}</td><td>${qty(r.damage)}</td><td>${r.actual!=null?qty(r.actual):'—'}</td><td>${qty(r.expected)}</td><td class="${(r.difference||0)<0?'negative':''}">${r.difference!=null?qty(r.difference):'—'}</td><td>${r.rate!=null?rupees(r.rate):'—'}</td><td>${statusBadge(r.status||(r.actual!=null?'IN PROGRESS':'OPEN'))}</td></tr>`).join('')}</tbody></table></div>`}
function reportSelection(){return sections().filter(s=>state.reportSections==null||state.reportSections.includes(s.id)).map(s=>s.id)}
function reportQuery(){return new URLSearchParams({kind:state.reportKind,month:state.month,property:state.property,sections:reportSelection().join(','),year:state.reportYear||state.month.slice(0,4)}).toString()}
async function reportsPage(){
 const yearly=state.reportKind==='yearly',archive=state.reportKind==='archives',selected=reportSelection();
 const rr=selected.length&&!archive?await api('/reports?'+reportQuery()):[];state.reportRows=rr;
 const archives=archive?(await api('/archives')).filter(a=>a.month===state.month&&selected.includes(a.section_id)):[];
 const filters=`<section class="panel report-builder"><div><h2>1. ${yearly?'Choose year':'Choose month'}</h2>${yearly?field('Report year','report_year','number',state.reportYear||state.month.slice(0,4),true,`min="2000" max="${state.context.today.slice(0,4)}"`):field('Report month','report_month','month',state.month,true,`max="${state.context.today.slice(0,7)}"`)}</div><div><h2>2. Choose sections</h2><label class="report-all"><input type="checkbox" id="report-all" ${selected.length===sections().length?'checked':''}> All sections</label><div class="report-section-options">${sections().map(s=>`<label><input type="checkbox" data-report-section="${s.id}" ${selected.includes(s.id)?'checked':''}> ${esc(state.context.properties.find(p=>p.id===s.property_id)?.name)} / ${esc(s.name)}</label>`).join('')}</div><p class="help">${selected.length} sections selected. Select one, several, or all.</p></div>${!yearly&&!archive?`<div><h2>3. Choose report</h2><div class="tabs">${[['inventory','Monthly inventory'],['breakage','Breakage'],['purchases','Purchases']].map(([k,l])=>`<button data-report="${k}" class="${state.reportKind===k?'active':''}">${l}</button>`).join('')}</div></div>`:''}</section>`;
 let preview=archive?(archives.length?`<div class="table-wrap"><table><thead><tr><th>Month</th><th>Section</th><th>Report</th><th>Revision</th><th>File</th></tr></thead><tbody>${archives.map(a=>`<tr><td>${esc(a.month)}</td><td>${esc(state.context.sections.find(s=>s.id===a.section_id)?.name)}</td><td>${esc(a.kind)}</td><td>${a.version}</td><td><a href="/api/archives/${a.id}">Download ${a.format.toUpperCase()}</a></td></tr>`).join('')}</tbody></table></div>`:empty('No closed files for this month and these sections.')):state.reportKind==='inventory'?inventoryReport(rr):yearly?`<div class="table-wrap"><table><thead><tr><th>Month</th><th>Closed item counts</th><th>Purchase value</th><th>Breakage quantity</th><th>Breakage value</th><th>Difference</th></tr></thead><tbody>${rr.map(r=>`<tr><td>${r.month}</td><td>${r.items}</td><td>${rupees(r.purchase_value)}</td><td>${r.breakage_qty}</td><td>${rupees(r.breakage_value)}</td><td>${qty(r.difference)}</td></tr>`).join('')}</tbody></table></div>`:rr.length?eventTable(rr):empty('No approved transactions for this month and these sections.');
 return pageHead('Download reports','Choose a period and sections. Preview and downloads use the same selection.')+`<div class="tabs">${[['inventory','Monthly reports'],['yearly','Year-end reports'],['archives','Saved closed reports']].map(([k,l])=>`<button data-report="${k}" class="${k==='inventory'?!yearly&&!archive?'active':'':state.reportKind===k?'active':''}">${l}</button>`).join('')}</div>`+filters+(selected.length?`<section class="panel"><div class="panel-head"><div><h2>${esc({inventory:'Monthly inventory',breakage:'Monthly breakage',purchases:'Monthly purchases',yearly:'Year-end summary',archives:'Saved closed reports'}[state.reportKind])}</h2><p>${yearly?'Closed monthly snapshots only. Months without accepted counts have no closed totals.':archive?'Original files saved when counts were accepted.':'Accepted stock transactions only. Unclosed inventory counts are marked as live previews.'}</p></div>${!archive?`<div class="actions"><button data-export="pdf">Download PDF</button><button class="primary" data-export="xlsx">Download Excel</button></div>`:''}</div>${preview}</section>${!yearly&&!archive?`<section class="panel"><div class="panel-body"><h2>Download monthly report pack</h2><p>Inventory, breakage and purchases for the selected month and sections, together in one ZIP file.</p><div class="actions"><button data-report-pack="pdf">All monthly PDFs</button><button data-report-pack="xlsx">All monthly Excel files</button></div></div></section>`:''}`:empty('Select at least one section to preview or download reports.'));
}
function assetBulkToolbar(){
 return `<div id="asset-bulk-toolbar" class="bulk-toolbar" style="display:none"><span class="bulk-count"><strong>0</strong> assets selected</span><div class="actions"><button type="button" class="small ghost" id="asset-bulk-clear-btn">Clear</button><button type="button" class="small danger" id="asset-bulk-delete-btn">Delete selected</button></div></div>`;
}

async function assetsPage(){
 if(!can('assets'))return empty('Access restricted.');
 if(!state.assetProperty)state.assetProperty='1';
 if(!state.selectedAssets)state.selectedAssets=new Set();
 const allAssets=await api('/assets');
 state.allAssets=allAssets;
 const countTvl=allAssets.filter(a=>String(a.property_id)==='1').length;
 const countTc=allAssets.filter(a=>String(a.property_id)==='2').length;
 const activePropName=state.assetProperty==='1'?'Travelicious':'Travellers Cavern';
 const propAssets=allAssets.filter(a=>String(a.property_id)===state.assetProperty);
 const totalQty=propAssets.reduce((s,a)=>s+(a.qty||0),0);
 const totalVal=propAssets.reduce((s,a)=>s+((a.qty||0)*(a.rate||0)),0);
 const withPhoto=propAssets.filter(a=>a.photo).length;

 return pageHead('Property assets',
  'Annual physical asset inventory — separate from monthly counts.',
  `<button class="primary" id="add-asset-btn">+ Add asset</button>`
 )+
 `<div class="asset-property-tabs" role="tablist">
    <button type="button" class="asset-tab ${state.assetProperty==='1'?'active':''}" data-asset-prop="1" role="tab" aria-selected="${state.assetProperty==='1'}">
      ${icon('asset')}
      <span>Travelicious</span>
      <span class="tab-badge">${countTvl} assets</span>
    </button>
    <button type="button" class="asset-tab ${state.assetProperty==='2'?'active':''}" data-asset-prop="2" role="tab" aria-selected="${state.assetProperty==='2'}">
      ${icon('asset')}
      <span>Travellers Cavern</span>
      <span class="tab-badge">${countTc} assets</span>
    </button>
  </div>
  <div class="asset-notice">
    <div class="asset-notice-text">
      <strong>Annual Physical Asset Register · ${esc(activePropName)}</strong>
      These property assets are checked and counted once a year. They are completely separate from operational monthly counts and invisible to regular staff.
    </div>
    <div class="actions">
      <button type="button" class="small" id="export-asset-pdf">Export PDF</button>
      <button type="button" class="small primary" id="export-asset-xlsx">Export Excel</button>
    </div>
  </div>
  <div class="stats" style="grid-template-columns:repeat(4,1fr)">
    ${stat('Asset items',propAssets.length,activePropName,'asset')}
    ${stat('Total quantity',totalQty,'Physical units counted','box')}
    ${stat('Total valuation',rupees(totalVal),'Based on recorded rates','report')}
    ${stat('Photographed',`${withPhoto} / ${propAssets.length}`,'Documented assets','photo')}
  </div>
  <section class="panel">
    <div class="toolbar">
      <input type="search" id="asset-search" placeholder="Search asset name, serial number, location or notes…" aria-label="Search assets" value="${esc(state.assetSearch||'')}">
      <span class="badge">${propAssets.length} assets</span>
    </div>
    ${assetBulkToolbar()}
    <div id="asset-table">${assetTable()}</div>
  </section>`;
}

function assetTable(){
 if(!state.selectedAssets)state.selectedAssets=new Set();
 const q=(state.assetSearch||'').trim().toLowerCase();
 const items=(state.allAssets||[]).filter(a=>String(a.property_id)===state.assetProperty&&(!q||`${a.name} ${a.code||''} ${a.location||''} ${a.notes||''}`.toLowerCase().includes(q)));
 const allSelected=items.length>0&&items.every(a=>state.selectedAssets.has(a.id));
 return items.length?`<div class="table-wrap"><table><thead><tr><th style="width:40px;text-align:center"><input type="checkbox" id="select-all-assets" ${allSelected?'checked':''} aria-label="Select all assets"></th><th>Serial No.</th><th>Asset</th><th>Location</th><th>Count (Qty)</th><th>Unit rate</th><th>Total value</th><th>Notes</th><th style="text-align:right">Actions</th></tr></thead><tbody>${items.map(a=>{
  const isSel=state.selectedAssets.has(a.id);
  const total=a.rate!=null?(a.qty*(a.rate||0)):null;
  return `<tr class="${isSel?'selected':''}" data-asset-row="${a.id}"><td style="text-align:center"><input type="checkbox" data-select-asset="${a.id}" ${isSel?'checked':''} aria-label="Select ${esc(a.name)}"></td><td><span class="badge" style="font-family:monospace;font-weight:600;letter-spacing:0.5px">${esc(a.code||'—')}</span></td><td class="name"><div class="item-cell">${thumb(a)}<div><strong>${esc(a.name)}</strong></div></div></td><td>${a.location?`<span class="badge">${esc(a.location)}</span>`:'<small class="help">Not set</small>'}</td><td><strong>${qty(a.qty)}</strong></td><td>${a.rate!=null?rupees(a.rate):'<small class="help">—</small>'}</td><td>${total!=null?rupees(total):'<small class="help">—</small>'}</td><td>${esc(a.notes||'—')}</td><td style="text-align:right"><div class="actions" style="justify-content:flex-end"><button type="button" class="small ghost" data-edit-asset="${a.id}">Edit</button><button type="button" class="small ghost danger" data-delete-asset="${a.id}">Delete</button></div></td></tr>`;
 }).join('')}</tbody></table></div><div class="table-footer">Showing ${items.length} assets · ${state.assetProperty==='1'?'Travelicious':'Travellers Cavern'} · Reviewed once a year</div>`:empty('No assets found. Add an asset to start tracking.');
}

function updateAssetBulkUI(){
 const n=state.selectedAssets?.size||0;
 const tb=$('#asset-bulk-toolbar');
 if(tb){
  tb.style.display=n?'flex':'none';
  const label=$('.bulk-count',tb);
  if(label)label.innerHTML=`<strong>${n}</strong> asset${n===1?'':'s'} selected`;
 }
 const q=(state.assetSearch||'').trim().toLowerCase();
 const visible=(state.allAssets||[]).filter(a=>String(a.property_id)===state.assetProperty&&(!q||`${a.name} ${a.code||''} ${a.location||''} ${a.notes||''}`.toLowerCase().includes(q)));
 const allCb=$('#select-all-assets');
 if(allCb)allCb.checked=visible.length>0&&visible.every(a=>state.selectedAssets?.has(a.id));
 $$('[data-select-asset]').forEach(cb=>{
  const isChecked=!!state.selectedAssets?.has(Number(cb.dataset.selectAsset));
  cb.checked=isChecked;
  const row=cb.closest('tr');
  if(row)row.classList.toggle('selected',isChecked);
 });
}

function bindAssetRowEvents(){
 $$('[data-select-asset]').forEach(cb=>{
  cb.onchange=()=>{
   const id=Number(cb.dataset.selectAsset);
   if(cb.checked)state.selectedAssets.add(id);
   else state.selectedAssets.delete(id);
   updateAssetBulkUI();
  };
 });
 if($('#select-all-assets'))$('#select-all-assets').onchange=e=>{
  const q=(state.assetSearch||'').trim().toLowerCase();
  const visible=(state.allAssets||[]).filter(a=>String(a.property_id)===state.assetProperty&&(!q||`${a.name} ${a.code||''} ${a.location||''} ${a.notes||''}`.toLowerCase().includes(q)));
  if(e.target.checked)visible.forEach(a=>state.selectedAssets.add(a.id));
  else visible.forEach(a=>state.selectedAssets.delete(a.id));
  updateAssetBulkUI();
 };
 $$('[data-edit-asset]').forEach(b=>b.onclick=()=>{
  const id=Number(b.dataset.editAsset);
  const a=(state.allAssets||[]).find(x=>x.id===id);
  if(a)assetForm(a);
 });
 $$('[data-delete-asset]').forEach(b=>b.onclick=()=>{
  const id=Number(b.dataset.deleteAsset);
  const a=(state.allAssets||[]).find(x=>x.id===id);
  if(!a)return;
  showModal('Delete asset?',
    `<div class="notice" style="border-color:#eac4b8;background:#fff5f2;color:#9b442b"><strong>Delete “${esc(a.name)}”?</strong><br>This asset will be permanently removed from the property asset inventory.</div>`,
    async()=>{
      await api('/assets/'+id,'DELETE');
      state.selectedAssets.delete(id);
      toast('Asset deleted');
    }
  );
 });
}

function bindAssets(){
 $$('[data-asset-prop]').forEach(btn=>btn.onclick=()=>{
  state.assetProperty=btn.dataset.assetProp;
  state.selectedAssets.clear();
  render();
 });
 if($('#add-asset-btn'))$('#add-asset-btn').onclick=()=>assetForm();
 if($('#export-asset-pdf'))$('#export-asset-pdf').onclick=()=>{
  window.location.href='/api/assets/export?property='+state.assetProperty+'&format=pdf';
 };
 if($('#export-asset-xlsx'))$('#export-asset-xlsx').onclick=()=>{
  window.location.href='/api/assets/export?property='+state.assetProperty+'&format=xlsx';
 };
 if($('#asset-search'))$('#asset-search').oninput=e=>{
  state.assetSearch=e.target.value;
  $('#asset-table').innerHTML=assetTable();
  bindAssetRowEvents();
  updateAssetBulkUI();
 };
 if($('#asset-bulk-clear-btn'))$('#asset-bulk-clear-btn').onclick=()=>{
  state.selectedAssets.clear();
  updateAssetBulkUI();
 };
 if($('#asset-bulk-delete-btn'))$('#asset-bulk-delete-btn').onclick=()=>{
  const ids=Array.from(state.selectedAssets||[]);
  if(!ids.length)return toast('Select at least one asset to delete.');
  showModal(`Delete ${ids.length} selected asset(s)?`,
    `<div class="notice" style="border-color:#eac4b8;background:#fff5f2;color:#9b442b"><strong>Are you sure?</strong><br>These ${ids.length} asset(s) will be permanently deleted from the asset inventory.</div>`,
    async()=>{
      const res=await api('/assets/bulk-delete','POST',{asset_ids:ids});
      toast(`${res.deleted} asset(s) deleted`);
      state.selectedAssets.clear();
    }
  );
  const submitBtn=$('#dialog-form [type="submit"]');
  if(submitBtn){submitBtn.textContent=`Delete ${ids.length} asset(s)`;submitBtn.className='danger';}
 };
 bindAssetRowEvents();
 updateAssetBulkUI();
}

function assetForm(a){
 const props=state.context.properties.map(p=>[p.id,p.name]);
 let getPhoto;
 showModal(a?'Edit asset':'Add new asset',
   `<div class="form-grid">
     ${a?.code?`<div class="field full"><label>Asset Serial Number (Fixed)</label><input type="text" value="${esc(a.code)}" disabled style="background:var(--bg,#f4f6f8);font-family:monospace;font-weight:700;color:var(--text,#173f35)"></div>`:`<div class="field full"><label>Asset Serial Number</label><input type="text" value="Automatic (assigned upon saving)" disabled style="background:var(--bg,#f4f6f8);font-style:italic;color:var(--muted,#666)"></div>`}
     ${uploadField(false)}
     ${field('Asset name *','name','text',a?.name||'',true)}
     ${selectField('Property *','property_id',props,a?.property_id||state.assetProperty)}
     ${field('Asset location','location','text',a?.location||'',false,'placeholder="e.g. Room 101, Lobby, Kitchen, Lawn"')}
     ${field('Asset count (Quantity) *','qty','number',a?.qty!=null?a.qty:'1',true,'min="0" step="1"')}
     ${field('Asset rate (Unit rate INR)','rate','number',a?.rate!=null?a.rate/100:'',false,'min="0" step="0.01"')}
     <div class="field full"><label for="f-notes">Notes / specifications</label><textarea id="f-notes" name="notes" placeholder="Brand, model, serial no, condition…">${esc(a?.notes||'')}</textarea></div>
   </div>`,
   async d=>{
     const photo=getPhoto();
     await api('/assets'+(a?'/'+a.id:''),a?'PATCH':'POST',{
       ...d,
       qty:Number(d.qty),
       rate:d.rate===''?null:Number(d.rate),
       ...(photo?{photo}:{})
     });
     toast(a?'Asset updated':'Asset added');
   }
 );
 getPhoto=photoBinding();
 if(a&&a.photo){
   const preview=$('#photo-preview');
   if(preview){preview.src='/photo/thumb-'+a.photo;preview.classList.add('visible');}
 }
}

async function usersPage(){
 const users=await api('/users');state.users=users;
 return pageHead('Team & access','Decide who can do what, and which sections they can access.',`<button class="primary" id="add-user">+ Add team member</button>`)+`<div class="notice"><strong>Main admin controls all member accounts.</strong><br>Other admins keep their assigned operational access; member management belongs only to the main admin.</div><section class="panel"><div class="table-wrap"><table><thead><tr><th>Person / login</th><th>Role</th><th>Section access</th><th>Permissions</th><th>Status</th><th>Actions</th></tr></thead><tbody>${users.map(u=>`<tr><td><strong>${esc(u.name)}</strong><small>${esc(u.username)} · ${u.login_provider==='google'?'Google sign-in':'Username & password'}</small></td><td><span class="badge ${u.full_access?'green':''}">${u.role}${u.full_access?' · full access':''}</span></td><td>${u.section_scope===null?'All properties & sections':u.section_scope.length?u.section_scope.map(id=>esc(state.context.sections.find(s=>s.id===id)?.name||'Section '+id)).join(', '):'No sections assigned'}</td><td>${u.full_access?'All modules and files':u.permissions.length+' granted actions'}</td><td>${statusBadge(u.active?'ACTIVE':'DISABLED')}</td><td>${u.role!=='MASTER'&&u.id!==state.user.id?`<button class="small primary" data-editaccess="${u.id}">Edit access</button> <button class="small" data-reset="${u.id}">Reset password</button> <button class="small ghost" data-disable="${u.id}">${u.active?'Disable':'Enable'}</button>`:u.is_owner?'Protected Master account':'Your account'}</td></tr>`).join('')}</tbody></table></div></section><p class="help">Permission or password changes sign the affected user out immediately. Private photos and downloadable reports follow the same section restrictions as the app.</p>`;
}
async function settingsPage(){return pageHead('Workspace settings','Keep your property structure and account in order.')+`<div class="report-grid"><section class="panel"><div class="panel-head"><h2>Your account</h2></div><div class="panel-body"><p><strong>${esc(state.user.name)}</strong></p><p class="help">${esc(state.user.username)} · ${esc(state.user.role)}</p><div class="actions">${!state.user.is_owner?'<p class="help">Contact the main admin to change your password.</p>':state.user.login_provider==='google'?'<span class="badge">Account secured by Google</span>':'<button id="change-password">Change password</button>'}<button id="sign-out">Log out</button></div></div></section>${fullAdmin()?`<section class="panel"><div class="panel-head"><h2>Data & retention</h2></div><div class="panel-body"><p class="help">Ledger entries, photos, closed snapshots and audit events have no automatic deletion. Download a complete backup and store a copy outside this computer.</p><a href="/api/backup" class="primary" style="display:inline-block;padding:12px;border-radius:8px;text-decoration:none">↓ Download full backup</a><p class="help">Currency: INR · Image limit: 1600px · Local database</p></div></section>`:''}</div>${fullAdmin()?`<section class="panel"><div class="panel-head"><div><h2>Properties & sections</h2><p>Add or rename sections as your operations grow.</p></div><button id="add-section" class="primary small">+ Add section</button></div>${state.context.sections.map(s=>`<div class="section-row"><span class="section-icon">${icon('box')}</span><div class="section-title"><strong>${esc(s.name)}</strong><small>${esc(state.context.properties.find(p=>p.id===s.property_id)?.name)}</small></div>${statusBadge(s.active?'ACTIVE':'ARCHIVED')}<button class="small" data-editsection="${s.id}">Edit</button></div>`).join('')}</section><section class="panel"><div class="panel-head"><h2>Workbook migration</h2></div><div class="panel-body"><p class="help">The 184 item labels from your development plan are already loaded, with no invented quantities, rates or photos. Import the original workbook to attach available images and review opening quantities.</p><button id="import-workbook">Preview Excel import</button></div></section>`:''}`}
async function auditPage(){const rr=await api('/audit?offset='+state.auditOffset);return pageHead('Audit trail','An append-only record of the changes that matter.')+`<section class="panel"><div class="panel-head"><h2>Workspace activity</h2><span class="badge">Latest 100 records</span></div>${rr.length?`<div class="table-wrap"><table><thead><tr><th>Time</th><th>Action</th><th>By</th><th>Details</th></tr></thead><tbody>${rr.map(r=>`<tr><td>${esc(r.created.replace('T',' '))}</td><td>${esc(r.action.replaceAll('_',' '))}</td><td>${esc(r.staff||'System')}</td><td style="white-space:normal;max-width:460px;word-break:break-word">${esc(r.detail)}</td></tr>`).join('')}</tbody></table></div>`:empty('No recorded activity yet.','audit')}<div class="panel-body actions"><button id="audit-prev" ${state.auditOffset===0?'disabled':''}>← Newer</button><button id="audit-next" ${rr.length<100?'disabled':''}>Older →</button></div></section>`}
function bindPage(){
 if(!can('backups'))$$('a[href="/api/backup"]').forEach(e=>e.remove());if(!can('import')&&$('#import-workbook'))$('#import-workbook').remove();
 const hide=(selector,permission)=>{if(!can(permission))$$(selector).forEach(el=>el.remove())};
 hide('[data-additem]','add_items');hide('[data-move="PURCHASE"]','purchases');hide('[data-move="BREAKAGE"],[data-move="DAMAGE"]','breakage');
 if(!can('counts')&&!can('review_counts'))$$('[data-nav="counts"],[data-count]').forEach(el=>el.remove());
 hide('[data-nav="reports"]','reports');

 $$('[data-nav]').forEach(b=>b.onclick=()=>{state.page=b.dataset.nav;if(b.dataset.reportKind)state.reportKind=b.dataset.reportKind;state.countSection=null;render()});
 if($('#dashboard-month-select'))$('#dashboard-month-select').onchange=e=>{if(e.target.value&&e.target.value<=state.context.today.slice(0,7)){state.month=e.target.value;render()}};
 if($('#dashboard-prev-month'))$('#dashboard-prev-month').onclick=()=>{state.month=shiftMonth(state.month,-1);render()};
 if($('#dashboard-next-month'))$('#dashboard-next-month').onclick=()=>{const n=shiftMonth(state.month,1);if(n<=state.context.today.slice(0,7)){state.month=n;render()}};
 if($('#dashboard-today-btn'))$('#dashboard-today-btn').onclick=()=>{state.month=state.context.today.slice(0,7);render()};
 $$('.stat[data-nav]').forEach(b=>b.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();b.click()}});
 $$('[data-addinventory]').forEach(b=>{if(!can('add_items')&&!can('purchases'))b.remove();else b.onclick=()=>inventoryEntry()});
 $$('[data-additem]').forEach(b=>b.onclick=()=>itemForm());
 $$('[data-move]').forEach(b=>b.onclick=()=>movementForm(b.dataset.move));
 $$('[data-count]').forEach(b=>b.onclick=()=>{state.page='counts';state.countSection=Number(b.dataset.count);state.countTab='remaining';state.countSearch='';render()});
 bindItems();
 bindReviews();
 if(state.page==='assets')bindAssets();
 if($('#item-search'))$('#item-search').oninput=e=>{state.search=e.target.value;$('#item-table').innerHTML=inventoryTable();bindItems()};
 if($('#section-filter'))$('#section-filter').onchange=e=>{state.section=e.target.value;$('#item-table').innerHTML=inventoryTable();bindItems()};
 if($('#inventory-property-filter'))$('#inventory-property-filter').onchange=e=>{state.property=e.target.value;state.section='';state.selectedItems?.clear();if($('#property'))$('#property').value=state.property;render()};
 if($('#share-count'))$('#share-count').onclick=async()=>{try{const users=(await api('/users')).filter(u=>u.active&&u.role==='STAFF'&&u.permissions.includes('counts')&&(u.section_scope===null||u.section_scope.includes(state.countSection)));if(!users.length)return toast('Give a staff member count permission and section access first.');showModal('Share section with staff',`<p>The complete item list will be sent with blank count fields. Existing draft entries are kept in the audit history. Staff cannot see stock balances.</p>${selectField('Staff member','staff_id',users.map(u=>[u.id,u.name+' / '+u.username]))}`,async d=>{await api(`/counts/${state.countSection}/${state.month}`,'POST',{action:'share',staff_id:Number(d.staff_id)});toast('Section shared with staff')})}catch(e){toast(e.message)}};
 if($('#back-counts'))$('#back-counts').onclick=()=>{state.countSection=null;render()};
 if(state.page==='counts'&&state.countSection&&state.countData){
  const locked=['SUBMITTED','CLOSED'].includes(state.countData.status)||!can('counts')||(state.countData.submitter&&state.countData.submitter.id!==state.user.id&&!state.countData.can_review);
  bindCountRows(state.countData,locked);
  $$('[data-count-filter]').forEach(b=>{
   b.onclick=()=>{
    state.countTab=b.dataset.countFilter;
    $$('[data-count-filter]').forEach(btn=>btn.classList.toggle('active',btn.dataset.countFilter===state.countTab));
    $('#count-items-container').innerHTML=countItemsTable(state.countData,locked);
    bindCountRows(state.countData,locked);
   };
  });
  if($('#count-search-input'))$('#count-search-input').oninput=e=>{
   state.countSearch=e.target.value;
   $('#count-items-container').innerHTML=countItemsTable(state.countData,locked);
   bindCountRows(state.countData,locked);
  };
 }
  for(const [id,action]of [['submit-count','submit'],['close-count','close'],['reopen-count','reopen']])if($('#'+id))$('#'+id).onclick=async()=>{
   if(action==='close'){
    const btn=$('#close-count');
    if(btn){btn.disabled=true;btn.textContent='Accepting & closing…';}
    try{
     await syncDrafts();
     if(Object.keys(drafts()).some(k=>k.startsWith(`${state.countSection}/${state.month}/`)))throw new Error('Sync pending count drafts before closing.');
     await api(`/counts/${state.countSection}/${state.month}`,'POST',{action:'close'});
     toast('Month count accepted and closed');
     await render();
    }catch(e){
     if(btn){btn.disabled=false;btn.textContent='Accept & close month';}
     toast(e.message);
    }
    return;
   }
   const uncounted=state.countData?.items.filter(r=>!isItemCounted(r)).length||0;
   showModal(action==='reopen'?'Reopen this count?':'Submit your count?',`<p class="help">${action==='reopen'?'Reopening unlocks this section. Previous snapshots and exports remain in the archive.':'Check all physical quantities before submitting. An authorized reviewer will review the differences.'}</p>${action==='submit'&&uncounted>0?`<div class="notice" style="margin-top:10px"><strong>Note:</strong> ${uncounted} item${uncounted===1?' is':'s are'} still uncounted in this section.</div>`:''}${action==='reopen'?field('Reason for reopening','reason','text','',true):''}`,async d=>{await syncDrafts();if(Object.keys(drafts()).some(k=>k.startsWith(`${state.countSection}/${state.month}/`)))throw new Error('Sync pending count drafts before submitting.');await api(`/counts/${state.countSection}/${state.month}`,'POST',{action,...d});toast('Count '+(action==='submit'?'submitted':'reopened'))});
  };
 $$('[data-report]').forEach(b=>b.onclick=()=>{state.reportKind=b.dataset.report;render()});
 if($('#f-report_month'))$('#f-report_month').onchange=e=>{if(e.target.checkValidity()&&e.target.value){state.month=e.target.value;render()}};
 if($('#f-report_year'))$('#f-report_year').onchange=e=>{if(e.target.checkValidity()&&e.target.value){state.reportYear=e.target.value;render()}};
 if($('#report-all'))$('#report-all').onchange=e=>{state.reportSections=e.target.checked?null:[];render()};
 $$('[data-report-section]').forEach(b=>b.onchange=()=>{state.reportSections=$$('[data-report-section]:checked').map(e=>Number(e.dataset.reportSection));render()});
 $$('[data-report-pack]').forEach(b=>b.onclick=()=>{window.location.href='/api/export/monthly-pack?'+reportQuery()+'&format='+b.dataset.reportPack});
 $$('[data-export]').forEach(b=>b.onclick=()=>{if(state.reportKind==='archives')return toast('Choose a saved file in the archive list.');window.location.href='/api/export?'+reportQuery()+'&format='+b.dataset.export});
 if($('#add-user'))$('#add-user').onclick=()=>accessForm();
 $$('[data-editaccess]').forEach(b=>b.onclick=()=>accessForm(state.users.find(u=>u.id===Number(b.dataset.editaccess))));
 $$('[data-reset]').forEach(b=>b.onclick=()=>showModal('Reset staff password',field('New password (minimum 5 characters)','password','password','',true,'minlength="5" autocomplete="new-password"'),async d=>{await api('/users','POST',{id:Number(b.dataset.reset),...d});toast('Password reset')}));
 $$('[data-disable]').forEach(b=>b.onclick=async()=>{try{const u=state.users.find(u=>u.id===Number(b.dataset.disable));await api('/users','POST',{id:u.id,active:!u.active});toast('Account updated');render()}catch(e){toast(e.message)}});
 if($('#change-password'))$('#change-password').onclick=()=>showModal('Change your password',field('Current password','current','password','',true)+field('New password (minimum 5 characters)','password','password','',true,'minlength="5" autocomplete="new-password"'),async d=>{await api('/password','POST',d);toast('Password changed')});
 if($('#sign-out'))$('#sign-out').onclick=logout;
 if($('#add-section'))$('#add-section').onclick=()=>sectionForm();
 $$('[data-editsection]').forEach(b=>b.onclick=()=>sectionForm(state.context.sections.find(s=>s.id===Number(b.dataset.editsection))));
 if($('#audit-prev'))$('#audit-prev').onclick=()=>{state.auditOffset=Math.max(0,state.auditOffset-100);render()};if($('#audit-next'))$('#audit-next').onclick=()=>{state.auditOffset+=100;render()};
 if($('#import-workbook'))$('#import-workbook').onclick=importForm;
}
function updateBulkUI(){
 const n=state.selectedItems?.size||0;
 const tb=$('#bulk-toolbar');
 if(tb){
  tb.style.display=n?'flex':'none';
  const label=$('.bulk-count',tb);
  if(label)label.innerHTML=`<strong>${n}</strong> item${n===1?'':'s'} selected`;
 }
 const visible=state.items.filter(r=>(!state.section||String(r.section_id)===state.section)&&(!state.search||`${r.name} ${r.code}`.toLowerCase().includes(state.search.toLowerCase())));
 const allCb=$('#select-all-items');
 if(allCb)allCb.checked=visible.length>0&&visible.every(r=>state.selectedItems?.has(r.id));
 $$('[data-select-item]').forEach(cb=>{
  const isChecked=!!state.selectedItems?.has(Number(cb.dataset.selectItem));
  cb.checked=isChecked;
  const row=cb.closest('tr');
  if(row)row.classList.toggle('selected',isChecked);
 });
}
function bindBulkSelection(){
 if(!can('edit_items'))return;
 if($('#select-all-items'))$('#select-all-items').onchange=e=>{
  const visible=state.items.filter(r=>(!state.section||String(r.section_id)===state.section)&&(!state.search||`${r.name} ${r.code}`.toLowerCase().includes(state.search.toLowerCase())));
  if(e.target.checked)visible.forEach(r=>state.selectedItems.add(r.id));
  else visible.forEach(r=>state.selectedItems.delete(r.id));
  updateBulkUI();
 };
 $$('[data-select-item]').forEach(cb=>{
  cb.onchange=()=>{
   const id=Number(cb.dataset.selectItem);
   if(cb.checked)state.selectedItems.add(id);
   else state.selectedItems.delete(id);
   updateBulkUI();
  };
 });
 if($('#bulk-clear-btn'))$('#bulk-clear-btn').onclick=()=>{
  state.selectedItems.clear();
  updateBulkUI();
 };
 if($('#bulk-move-btn'))$('#bulk-move-btn').onclick=()=>{
  const ids=Array.from(state.selectedItems||[]);
  if(!ids.length)return toast('Select at least one item.');
  const selected=state.items.filter(i=>ids.includes(i.id));
  const secChoices=sections().map(s=>[s.id,(state.context.properties.find(p=>p.id===s.property_id)?.name||'')+' / '+s.name]);
  const previewList=`<div class="bulk-preview-list">${selected.slice(0,10).map(i=>`<div class="bulk-preview-item">${thumb(i)}<div><strong>${esc(i.name)}</strong><small>${esc(i.section)} · Stock: ${qty(i.stock)} ${esc(i.unit)}</small></div></div>`).join('')}${selected.length>10?`<p style="text-align:center;font-size:11px;color:var(--muted);margin:6px 0">+ ${selected.length-10} more item(s)</p>`:''}</div>`;
  showModal(`Move ${ids.length} item(s)`,
   `<p class="help">Move ${ids.length} selected item(s) to another section. All current stock balances will be transferred with an audit adjustment record.</p>${selectField('Target section *','section_id',secChoices)}${previewList}`,
   async d=>{
    const targetId=Number(d.section_id);
    const res=await api('/items/bulk-move','POST',{item_ids:ids,section_id:targetId});
    toast(`${res.moved} item(s) moved to ${res.target_section}`);
    state.selectedItems.clear();
    state.items=await api('/items?property='+state.property);
    $('#item-table').innerHTML=inventoryTable();
    bindItems();
    updateBulkUI();
   }
  );
 };
 if($('#bulk-delete-btn'))$('#bulk-delete-btn').onclick=()=>{
  const ids=Array.from(state.selectedItems||[]);
  if(!ids.length)return toast('Select at least one item.');
  const selected=state.items.filter(i=>ids.includes(i.id));
  const previewList=`<div class="bulk-preview-list">${selected.slice(0,10).map(i=>`<div class="bulk-preview-item">${thumb(i)}<div><strong>${esc(i.name)}</strong><small>${esc(i.section)} · Stock: ${qty(i.stock)} ${esc(i.unit)}</small></div></div>`).join('')}${selected.length>10?`<p style="text-align:center;font-size:11px;color:var(--muted);margin:6px 0">+ ${selected.length-10} more item(s)</p>`:''}</div>`;
  showModal(`Delete ${ids.length} item(s)?`,
   `<div class="notice" style="border-color:#eac4b8;background:#fff5f2;color:#9b442b"><strong>Are you sure?</strong><br>Selected items will be removed from your active catalogue and monthly counts. Items with transaction history will be safely archived to preserve ledger audit integrity.</div>${previewList}`,
   async()=>{
    const res=await api('/items/bulk-delete','POST',{item_ids:ids});
    toast(`${res.deleted} item(s) deleted`);
    state.selectedItems.clear();
    state.items=await api('/items?property='+state.property);
    $('#item-table').innerHTML=inventoryTable();
    bindItems();
    updateBulkUI();
   }
  );
  const submitBtn=$('#dialog-form [type="submit"]');
  if(submitBtn){submitBtn.textContent=`Delete ${ids.length} item(s)`;submitBtn.className='danger';}
 };
}
function bindItems(){
 $$('[data-item]').forEach(b=>b.onclick=()=>{const r=state.items.find(i=>i.id===Number(b.dataset.item));master()?itemDetail(r):can('purchases')?movementForm('PURCHASE',r.id):showModal(esc(r.name),`<div class="row">${thumb(r)}<p>${esc(r.specification||'No specifications recorded.')}</p></div>`)});
 $$('[data-photo]').forEach(b=>b.onclick=()=>showModal('Incident photo',`<img class="preview-full" src="/photo/${esc(b.dataset.photo)}" alt="Recorded incident evidence">`));
 bindBulkSelection();
}
function uploadField(required=true){return `<div class="field full"><label for="camera-input">${required?'Photo *':'Update photo'}</label><div class="row"><button type="button" id="camera-button" class="primary">Take photo</button><input id="camera-input" type="file" accept="image/*" capture="environment" hidden></div><small>Photo is automatically resized to fit 1600px and compressed below 1 MB before upload. Review the preview before saving.</small><img id="photo-preview" class="upload-preview" alt="Photo preview"></div>`}
function photoBinding(onReady=()=>{}){
 let encoded=null,version=0;
 const root=$('#modal'),camera=$('#camera-input',root),preview=$('#photo-preview',root),button=$('#camera-button',root);
 const compress=async file=>{
  if(!file)return;const current=++version;encoded=null;preview.removeAttribute('src');preview.classList.remove('visible');onReady(false);button.disabled=true;button.textContent='Processing photo…';
  try{
   const image=await createImageBitmap(file);const canvas=document.createElement('canvas');let edge=1600,data;
   try{
    do{
     const scale=Math.min(1,edge/Math.max(image.width,image.height));canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
     let quality=.8;data=canvas.toDataURL('image/jpeg',quality);
     while(data.length>1300000&&quality>.35){quality-=.1;data=canvas.toDataURL('image/jpeg',quality)}
     edge=Math.floor(edge*.75);
    }while(data.length>1300000&&edge>=100);
   }finally{image.close()}
   if(data.length>1300000)throw new Error('Photo is too large.');
   if(current!==version||!root.contains(preview))return;encoded=data;preview.src=data;preview.classList.add('visible');onReady(true);
  }catch(e){if(current===version){encoded=null;onReady(false);toast('Could not process photo. Please take another photo.')}}
  finally{if(current===version&&root.contains(button)){button.disabled=false;button.textContent='Take photo'}}
 };
 camera.onchange=()=>compress(camera.files[0]);button.onclick=()=>{camera.value='';camera.click()};return ()=>encoded;
}
async function inventoryEntry(){
 if(!can('add_items'))return can('purchases')?movementForm('PURCHASE'):undefined;
 if(!can('purchases'))return itemForm();
 try{
  state.items=await api('/items?property='+state.property);
  if(!state.items.length)return itemForm();
  showModal('Add inventory',`<p class="help">Select an existing item to receive stock, or create a new item with its starting quantity.</p>${selectField('Item','inventory_choice',[['new','New item'],...state.items.map(i=>[i.id,i.section+' / '+i.name])])}<div class="modal-actions"><button type="button" id="inventory-continue" class="primary">Continue</button></div>`);
  $('#inventory-continue').onclick=()=>{const choice=$('#f-inventory_choice').value;choice==='new'?itemForm():movementForm('PURCHASE',Number(choice))};
 }catch(e){toast(e.message)}
}
function bindItemNameCaution(isEditId=null,cautionContainerId='item-name-caution',nameInputId='f-name',sectionInputId='f-section_id',excludeSubId=null){
 const cautionEl=$('#'+cautionContainerId);
 const nameInput=$('#'+nameInputId);
 const secInput=$('#'+sectionInputId);
 if(!cautionEl||!nameInput||!secInput)return;
 let timer=null;
 let checkSeq=0;
 async function performCheck(){
  const rawName=nameInput.value.trim();
  const sid=secInput.value;
  if(!rawName||!sid){
   cautionEl.style.display='none';
   cautionEl.innerHTML='';
   return;
  }
  const currentSeq=++checkSeq;
  try{
   const q=`/items/check-name?name=${encodeURIComponent(rawName)}&section_id=${encodeURIComponent(sid)}${isEditId?`&exclude_id=${isEditId}`:''}${excludeSubId?`&exclude_sub_id=${excludeSubId}`:''}`;
   const res=await api(q);
   if(currentSeq!==checkSeq)return;
   if(res.in_section){
    cautionEl.className='field full item-caution-banner caution-warning';
    cautionEl.style.display='flex';
    cautionEl.innerHTML=`<span class="caution-icon">⚠️</span><div class="caution-content"><strong>Caution: Item name is repeating in this section</strong><p>An item named "<strong>${esc(res.item.name)}</strong>" already exists in <strong>${esc(res.item.section)}</strong> (Serial No: <code>${esc(res.item.code||'Assigned')}</code>${res.item.unit?` · Unit: ${esc(res.item.unit)}`:''}). Adding it will create a duplicate in this section.</p></div>`;
   }else if(res.is_pending){
    cautionEl.className='field full item-caution-banner caution-warning';
    cautionEl.style.display='flex';
    cautionEl.innerHTML=`<span class="caution-icon">⏳</span><div class="caution-content"><strong>Caution: Item already submitted for this section</strong><p>An item named "<strong>${esc(res.item.name)}</strong>" has already been submitted for <strong>${esc(res.item.section)}</strong> and is awaiting Master approval.</p></div>`;
   }else if(res.other_section){
    cautionEl.className='field full item-caution-banner caution-info';
    cautionEl.style.display='flex';
    cautionEl.innerHTML=`<span class="caution-icon">ℹ️</span><div class="caution-content"><strong>Notice: Item exists in another section</strong><p>An item named "<strong>${esc(res.other_section.name)}</strong>" already exists in <strong>${esc(res.other_section.section)}</strong> (Serial No: <code>${esc(res.other_section.code||'Assigned')}</code>). If this is separate stock for this section, you may continue.</p></div>`;
   }else{
    cautionEl.style.display='none';
    cautionEl.innerHTML='';
   }
  }catch(e){
   console.warn('Name check error:',e);
  }
 }
 nameInput.addEventListener('input',()=>{
  clearTimeout(timer);
  timer=setTimeout(performCheck,180);
 });
 secInput.addEventListener('change',performCheck);
 if(nameInput.value.trim())performCheck();
}
function itemForm(r){
 const requestId=crypto.randomUUID();
 const opts=state.context.sections.filter(s=>s.active).map(s=>[s.id,state.context.properties.find(p=>p.id===s.property_id).name+' / '+s.name]);
 let getPhoto;
 showModal(r?'Edit item':'Add a new item',`<div class="form-grid">${r?.code?`<div class="field full"><label>Serial Number (Fixed)</label><input type="text" value="${esc(r.code)}" disabled style="background:var(--bg,#f4f6f8);font-family:monospace;font-weight:700;color:var(--text,#173f35)"></div>`:`<div class="field full"><label>Serial Number</label><input type="text" value="Automatic (assigned upon saving)" disabled style="background:var(--bg,#f4f6f8);font-style:italic;color:var(--muted,#666)"></div>`}${uploadField(!r)}${field('Item name *','name','text',r?.name||'',true)}${selectField('Property / section','section_id',opts,r?.section_id||state.section||sections()[0]?.id)}<div id="item-name-caution" class="field full item-caution-banner" style="display:none" role="alert"></div>${selectField('Unit','unit',[['Nos','Nos'],['Set','Set'],['Pair','Pair'],['Piece','Piece']],r?.unit||'Nos')}${field('Unit rate (INR, if known)','rate','number',r?.rate==null?'':r.rate/100,false,'min="0" step="0.01"')}${!r?field('Opening / received quantity','qty','number','0',true,'min="0" step="1"'):''}${r?`${field('Specification','specification','text',r?.specification||'')}${field('Category','category','text',r?.category||'')}`:''}</div>`,async d=>{
  const photo=getPhoto();
  if(!r&&!photo)throw new Error('Add and review a photo before saving.');
  const sid=d.section_id;
  const rawName=(d.name||'').trim();
  const check=await api(`/items/check-name?name=${encodeURIComponent(rawName)}&section_id=${encodeURIComponent(sid)}${r?`&exclude_id=${r.id}`:''}`);
  if(check.in_section){
   const proceed=confirm(`⚠️ CAUTION: An item named "${check.item.name}" already exists in ${check.item.section} (Serial No: ${check.item.code}).\n\nAre you sure you want to add another item with the exact same name to this section?`);
   if(!proceed)throw new Error('Cancelled: Item name already exists in this section.');
  }else if(check.is_pending){
   const proceed=confirm(`⚠️ CAUTION: An item named "${check.item.name}" has already been submitted for ${check.item.section} and is waiting for Master review.\n\nAre you sure you want to submit another item with the same name?`);
   if(!proceed)throw new Error('Cancelled: A duplicate submission is already pending review in this section.');
  }
  await api('/items'+(r?'/'+r.id:''),r?'PATCH':'POST',{...d,request_id:requestId,...(photo?{photo}:{})});
  toast(r?'Item updated':state.user.role==='STAFF'?'Sent to master. Item appears only after acceptance.':'Item created')
 });
 getPhoto=photoBinding();
 bindItemNameCaution(r?.id||null,'item-name-caution','f-name','f-section_id');
}
function moveItemForm(r){
 const choices=state.context.sections.filter(s=>s.active&&s.id!==r.section_id).map(s=>[s.id,state.context.properties.find(p=>p.id===s.property_id).name+' / '+s.name]);
 if(!choices.length)return toast('No other accessible sections.');
 showModal('Move section',`<p><strong>${esc(r.name)}</strong> · ${esc(r.section)}</p><p class="help">Move this item and all its current stock. Photo and details follow it; previous records stay in their original section.</p>${selectField('Destination section','section_id',choices)}`,async d=>{await api('/items/'+r.id+'/move','POST',d);toast('Item moved to the selected section')});
 $('#dialog-form [type="submit"]').textContent='Move item';
}
async function itemDetail(r){try{const ledger=await api('/history/'+r.id);showModal(esc(r.name),`<div class="row">${thumb(r)}<div><div class="eyebrow">${esc(r.code)}</div><p>${esc(r.specification)||'Add specifications for your team.'}</p></div></div><div class="stats" style="grid-template-columns:1fr 1fr;margin-top:20px">${stat('Current stock',qty(r.stock),r.unit,'box')}${stat('Default rate',rupees(r.rate),'INR per unit','report')}</div><div class="actions"><button id="edit-item">Edit details</button><button id="move-item">Move section</button><button id="item-purchase" class="primary">+ Add stock</button><button id="item-adjust">Adjustment</button><button id="archive-item" class="danger">Archive</button></div><h3>Transaction ledger</h3>${ledger.length?eventTable(ledger):'<p class="help">No stock has been entered yet. Add your opening quantity to start the ledger.</p>'}`);$('#move-item').hidden=!(['MASTER','ADMIN'].includes(state.user.role)&&can('edit_items'));$('#move-item').onclick=()=>moveItemForm(r);$('#edit-item').hidden=!can('edit_items');$('#item-purchase').hidden=!can('purchases');$('#item-adjust').hidden=!can('adjustments');$('#archive-item').hidden=!can('edit_items');$('#edit-item').onclick=()=>itemForm(r);$('#item-purchase').onclick=()=>movementForm('PURCHASE',r.id);$('#item-adjust').onclick=()=>movementForm('ADJUSTMENT',r.id);$('#archive-item').onclick=async()=>{if(confirm('Archive this item? Its ledger and snapshots will remain in history.')){try{await api('/items/'+r.id,'PATCH',{active:0});$('#modal').close();toast('Item archived');render()}catch(e){toast(e.message)}}};bindItems()}catch(e){toast(e.message)}}
async function movementForm(type,itemId){if(type==='BREAKAGE'||type==='DAMAGE')return breakageForm();try{state.items=await itemOptions(type==='PURCHASE'?'purchases':'breakage');if(!state.items.length){toast('Add an item to this property first.');return}let getPhoto;const loss=['BREAKAGE','DAMAGE'].includes(type);const selected=state.items.find(i=>i.id===itemId)||state.items[0];const rid=crypto.randomUUID();showModal(type==='PURCHASE'?'Receive stock':type==='ADJUSTMENT'?'Record an adjustment':'Report breakage',`<div class="form-grid">${selectField('Item','item_id',state.items.map(i=>[i.id,i.section+' / '+i.name]),itemId||state.items[0]?.id)}<div class="field full item-preview-card" id="movement-item-preview"></div>${field('Quantity *','qty','number','',true,'min="1" step="1"')}${type==='PURCHASE'?field('Purchase rate per unit (INR)','rate','number',selected?.rate==null?'':selected.rate/100,false,'min="0" step="0.01"'):''}${master()?field('Date','date','date',state.context.today,true,`max="${state.context.today}"`):''}${loss?selectField('Reason','reason',state.context.reasons.map(r=>[r,r])):''}${type==='ADJUSTMENT'?selectField('Direction','direction',[['add','Add stock'],['subtract','Subtract stock']]):''}<div class="field full"><label for="f-note">${type==='ADJUSTMENT'?'Adjustment reason *':'Note / invoice reference'}</label><textarea id="f-note" name="note" ${type==='ADJUSTMENT'?'required':''}></textarea></div>${loss?uploadField(true):''}</div><p class="help">${loss?'Saving this report immediately deducts the quantity and preserves the photo and event-time rate.':'Staff submissions wait for admin approval before stock changes.'}</p>`,async d=>{const photo=loss?getPhoto():undefined;if(loss&&!photo)throw new Error('Add and review an incident photo before saving.');const result=await api('/movements','POST',{...d,type,request_id:rid,photo});toast(result.pending?'Sent for admin review · #'+result.reference:'Saved · Reference #'+result.reference)});const updatePreview=()=>{const itm=state.items.find(i=>String(i.id)===$('#f-item_id')?.value);const prev=$('#movement-item-preview');if(itm&&prev)prev.innerHTML=`${thumb(itm)}<div><strong>${esc(itm.name)}</strong><small>${esc(itm.code||'')} · ${esc(itm.specification||itm.section||'')}${itm.unit?' · Unit: '+esc(itm.unit):''}</small></div>`};if($('#f-item_id')){$('#f-item_id').onchange=updatePreview;updatePreview()};if(loss)getPhoto=photoBinding()}catch(e){toast(e.message)}}
function sectionForm(s){showModal(s?'Edit section':'Add section',selectField('Property','property_id',state.context.properties.map(p=>[p.id,p.name]),s?.property_id||state.property)+field('Section name','name','text',s?.name||'',true)+field('Display order','sort_order','number',s?.sort_order||0,true,'min="0"')+(s?selectField('Status','active',[[1,'Active'],[0,'Archived']],s.active):''),async d=>{await api('/sections','POST',{...d,active:Number(d.active??1),...(s?{id:s.id}:{})});state.context=await api('/context');toast('Section saved')})}
function importForm(){showModal('Preview workbook import',`<p class="help">Upload the original Excel workbook. The preview shows source labels and linked photos. Existing exact-name items are matched; source labels remain unchanged.</p><div class="field"><label for="workbook">Excel workbook</label><input id="workbook" type="file" accept=".xlsx" required></div><p class="help">This preview does not change inventory.</p>`,async()=>{const fd=new FormData();fd.append('file',$('#workbook').files[0]);const r=await fetch('/api/import/preview',{method:'POST',headers:{'X-CSRF-Token':state.csrf},body:fd});const b=await r.json();if(!r.ok)throw new Error(b.error);setTimeout(()=>importPreview(b),0)})}
function importPreview(b){showModal('Review workbook import',`<div class="notice"><strong>${b.items.length} source items · ${b.items.filter(i=>i.has_photo).length} linked photos</strong><br>Only matched Cafe / Service sheets are included. Confirm each opening quantity in the preview before importing.</div><div class="table-wrap" style="max-height:45vh"><table><thead><tr><th>Section / item</th><th>Photo</th><th>Opening</th><th>Rate INR</th></tr></thead><tbody>${b.items.map((r,n)=>`<tr><td class="name">${esc(r.name)}<small>${esc(r.section)} · ${r.existing?'Match found':'New item'}</small></td><td>${r.has_photo?'Available':'Needed'}</td><td><input type="number" data-import-qty="${n}" min="0" step="1" value="${r.qty??''}" style="width:85px" aria-label="Opening ${esc(r.name)}"></td><td><input type="number" data-import-rate="${n}" min="0" step="0.01" value="${r.rate??''}" style="width:90px" aria-label="Rate ${esc(r.name)}"></td></tr>`).join('')}</tbody></table></div><p class="help">Blank quantities import the catalogue only. Stock is never overwritten. Items with ledger history can receive photos/details but cannot receive another imported opening balance.</p>`,async()=>{await api('/import/commit','POST',{token:b.token,values:b.items.map((r,n)=>({qty:$(`[data-import-qty="${n}"]`).value,rate:$(`[data-import-rate="${n}"]`).value}))});toast('Workbook imported')})}
window.addEventListener('online',()=>{syncDrafts();toast('Back online. Syncing count drafts…')});
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
$('#modal').addEventListener('close',()=>{if(!$('#modal').open)$('#modal').replaceChildren()});
boot();

function accessForm(u){
 const allowedLabels=Object.entries(state.context.permission_labels).filter(([key])=>key!=='users').filter(([p])=>fullAdmin()||can(p));
 const grants=u?.permissions||['inventory','add_items','purchases','breakage','counts'];
 const scope=u?u.section_scope:state.user.section_scope;
 let originalPassword='',passwordEdited=false;
 showModal(u?'Edit account & access':'Add a team member',`<div class="form-grid">${field('Full name','name','text',u?.name||'',true)}${field('Username','username','text',u?.username||'',true)}<div class="field"><label for="f-password">Password</label><div class="member-password-control"><input id="f-password" name="password" type="password" ${u?'':'required'} minlength="5" autocomplete="new-password" aria-describedby="member-password-help"><button type="button" id="reveal-member-password" aria-controls="f-password" aria-pressed="false">Show</button></div><small id="member-password-help">${u?'Loading saved password…':'Use at least 5 characters.'}</small></div>${selectField('Account role','role',fullAdmin()?[['STAFF','Staff'],['ADMIN','Admin']]:[['STAFF','Staff']],u?.role||'STAFF')}</div>${fullAdmin()?`<label class="permission-full"><input type="checkbox" id="grant-full" ${u?.full_access?'checked':''}> Full administrator access</label><p class="help">Full admins can access operational sections and files, export backups and change settings. Only the main admin manages members and passwords. The Master account stays protected.</p>`:''}<div id="granular-access"><h3>Allowed actions</h3><div class="permission-grid">${allowedLabels.map(([key,label])=>`<label><input type="checkbox" data-permission="${key}" ${grants.includes(key)?'checked':''}>${esc(label)}</label>`).join('')}</div><p class="help">Reports, month review, item editing and adjustments also grant stock/rate visibility. Staff are blind by default. Only the main admin can manage members.</p><h3>Properties & sections</h3>${state.user.section_scope===null?`<label><input type="checkbox" id="all-sections" ${scope===null?'checked':''}> All current and future sections in both properties</label>`:''}<div class="scope-grid">${state.context.properties.map(p=>`<fieldset><legend>${esc(p.name)}</legend>${state.context.sections.filter(s=>s.property_id===p.id).map(s=>`<label><input type="checkbox" data-scope="${s.id}" ${scope===null||scope?.includes(s.id)?'checked':''}>${esc(s.name)}${s.active?'':' (archived)'}</label>`).join('')}</fieldset>`).join('')}</div></div>${u?selectField('Account status','active',[[1,'Active'],[0,'Disabled']],u.active):''}`,async(d,form)=>{
 const isFull=!!$('#grant-full',form)?.checked;
 const permissions=$$('[data-permission]:checked',form).map(e=>e.dataset.permission);
 const section_scope=isFull||$('#all-sections',form)?.checked?null:$$('[data-scope]:checked',form).map(e=>Number(e.dataset.scope));
 if(u&&(!d.password||d.password===originalPassword))delete d.password;
 await api('/users','POST',{...d,...(u?{id:u.id}:{}),active:Number(d.active??1),full_access:isFull,permissions,section_scope});toast('Account access saved');
 });
 const passwordInput=$('#f-password'),passwordToggle=$('#reveal-member-password'),passwordHelp=$('#member-password-help');
 passwordInput.oninput=()=>{passwordEdited=true};
 passwordToggle.onclick=()=>{const visible=passwordInput.type==='password';passwordInput.type=visible?'text':'password';passwordToggle.textContent=visible?'Hide':'Show';passwordToggle.setAttribute('aria-pressed',String(visible))};
 if(u)api('/users/'+u.id+'/password/reveal','POST',{}).then(r=>{
  if(!document.contains(passwordInput))return;
  originalPassword=r.password||'';
  if(!passwordEdited)passwordInput.value=originalPassword;
  passwordInput.placeholder=r.reset_required?'Enter a new password':'';
  passwordHelp.textContent=r.reset_required?'Old password cannot be recovered. Enter at least 5 characters and save to replace it. Leave blank to keep it.':'Show or edit this password, then Save changes. Minimum 5 characters.';
 }).catch(e=>{if(document.contains(passwordHelp))passwordHelp.textContent='Saved password could not be loaded. Leave blank to keep it, or enter a replacement.';toast(e.message)});
 const update=()=>{const admin=$('#f-role').value==='ADMIN';if($('#grant-full')){if(!admin)$('#grant-full').checked=false;$('#grant-full').disabled=!admin}$('#granular-access').hidden=!!$('#grant-full')?.checked;const manage=$('[data-permission="users"]');if(manage){manage.disabled=!admin;if(!admin)manage.checked=false}$$('[data-scope]').forEach(e=>e.disabled=!!$('#all-sections')?.checked)};
 $('#f-role').onchange=update;if($('#grant-full'))$('#grant-full').onchange=update;if($('#all-sections'))$('#all-sections').onchange=update;update();
}

async function breakageForm(){
 try{
  const [items,context]=await Promise.all([itemOptions('breakage'),state.context?Promise.resolve(state.context):api('/context')]);
  const choices=context.sections.filter(sec=>sec.active&&items.some(i=>i.section_id===sec.id));
  if(!choices.length){toast('No inventory items available in your assigned sections. Contact your administrator.');return}
  const reference=crypto.randomUUID();let getPhoto,stage=1;
  showModal('Report breakage',`<div class="report-step-label" id="report-step-label">STEP 1 OF 2 · PHOTO</div><div id="breakage-photo-step"><p class="help">Take a clear photo of the broken item. Your photo is compressed automatically.</p>${uploadField(true)}<button type="button" id="use-breakage-photo" class="primary" disabled>Use photo & continue</button></div><div id="breakage-details-step" hidden><div class="breakage-photo-summary"><img id="breakage-confirmed-photo" alt="Breakage evidence"><div><strong>Photo ready</strong><button type="button" id="change-breakage-photo" class="small ghost">Change photo</button></div></div><div class="form-grid">${selectField('Section *','section_id',[['','Choose a section'],...choices.map(sec=>[sec.id,context.properties.find(p=>p.id===sec.property_id).name+' / '+sec.name])])}${selectField('Item *','item_id',[['','Choose a section first']])}<div class="field full item-preview-card" id="breakage-item-preview" style="display:none"></div>${field('Quantity broken *','qty','number','1',true,'min="1" step="1"')}${field('Date (automatic)','reported_date','date',context.today,false,'readonly tabindex="-1"')}<div class="field full"><label for="breakage-reason">Reason *</label><textarea id="breakage-reason" name="reason" required maxlength="2000" placeholder="Describe how the item broke…"></textarea></div></div><p class="help">Date is set by the server when sent. Past dates are not accepted. Your report and photo go to admin for approval. Stock changes only after acceptance.</p></div>`,async d=>{
   if(stage!==2||!getPhoto())throw new Error('Take and confirm a photo first.');
   if(!d.section_id||!d.item_id||!d.reason.trim())throw new Error('Select the section and item, then type a reason.');
   const result=await api('/movements','POST',{type:'BREAKAGE',item_id:Number(d.item_id),section_id:Number(d.section_id),qty:d.qty,reason:d.reason.trim(),photo:getPhoto(),request_id:reference});
   toast(result.pending?'Sent for admin review · #'+result.reference:'Report recorded · #'+result.reference);refreshNotifications();
  });
  const submit=$('#dialog-form [type="submit"]');submit.textContent='Send report';submit.hidden=true;
  $('#f-section_id').required=true;$('#f-item_id').required=true;$('#f-item_id').disabled=true;
  getPhoto=photoBinding(ready=>{$('#use-breakage-photo').disabled=!ready});
  $('#use-breakage-photo').onclick=()=>{if(!getPhoto())return;stage=2;$('#breakage-confirmed-photo').src=getPhoto();$('#breakage-photo-step').hidden=true;$('#breakage-details-step').hidden=false;$('#report-step-label').textContent='STEP 2 OF 2 · REPORT DETAILS';submit.hidden=false;$('#f-section_id').focus()};
  $('#change-breakage-photo').onclick=()=>{stage=1;$('#breakage-photo-step').hidden=false;$('#breakage-details-step').hidden=true;$('#report-step-label').textContent='STEP 1 OF 2 · PHOTO';submit.hidden=true;$('#camera-button').focus()};
  $('#f-section_id').onchange=e=>{const select=$('#f-item_id'),filtered=items.filter(i=>String(i.section_id)===e.target.value);select.innerHTML='<option value="">Choose an item</option>'+filtered.map(i=>`<option value="${i.id}">${esc(i.name)}</option>`).join('');select.disabled=!filtered.length;const prev=$('#breakage-item-preview');if(prev)prev.style.display='none'};
  $('#f-item_id').onchange=e=>{const itm=items.find(i=>String(i.id)===e.target.value);const prev=$('#breakage-item-preview');if(itm&&prev){prev.style.display='flex';prev.innerHTML=`${thumb(itm)}<div><strong>${esc(itm.name)}</strong><small>${esc(itm.code||'')} · ${esc(itm.specification||'Standard specification')}</small></div>`}else if(prev){prev.style.display='none'}};
 }catch(e){toast(e.message)}
}
function profileMenu(){
 showModal('Your profile',`<div class="profile-summary"><span class="avatar">${esc(state.user.name[0].toUpperCase())}</span><div><strong>${esc(state.user.name)}</strong><p>${esc(state.user.username)}</p><span class="badge">${esc(state.user.role)}</span></div></div><div class="profile-actions"><button id="profile-account">Account settings</button><button id="profile-logout" class="primary">Log out</button></div>`);
 $('#profile-account').onclick=()=>{$('#modal').close();state.page='settings';render()};$('#profile-logout').onclick=async()=>{try{await logout()}catch(e){toast(e.message)}};
}
let notificationBusy=false;
async function refreshNotifications(){
 if(state.user?.role!=='MASTER'||notificationBusy)return;
 const uid=state.user.id;notificationBusy=true;
 try{const data=await api('/notifications');if(state.user?.id!==uid)return;state.notifications=data;const count=$('#notification-count');if(count){count.textContent=data.unread>99?'99+':data.unread;count.hidden=!data.unread;$('#notifications-button').setAttribute('aria-label',`Notifications, ${data.unread} unread`)}}catch(e){/* Retry with the next regular refresh. */}finally{notificationBusy=false}
}
async function notificationInbox(){
 try{
  await refreshNotifications();const data=state.notifications||{items:[],unread:0};
  showModal('Breakage notifications',data.items.length?`<p class="help">${data.unread} unread. Reports arrive here even while you are logged out.</p><div class="notification-list">${data.items.map(n=>`<article class="notification-card ${n.read_at?'':'unread'}"><div class="row"><strong>${esc(n.name)}</strong>${!n.read_at?'<span class="badge green">New</span>':''}</div><p>${Math.abs(n.qty)} broken · ${esc(n.property)} / ${esc(n.section)}</p><p class="notification-reason">${esc(n.reason)}</p><small>${esc(n.staff)} · ${esc(n.date)} · #${n.reference}</small><div class="actions"><button class="small" data-notification-open="${n.id}">View report</button>${!n.read_at?`<button class="small ghost" data-notification-read="${n.id}">Mark read</button>`:''}</div></article>`).join('')}</div>`:empty('No breakage notifications yet.'));
  $$('[data-notification-read]').forEach(b=>b.onclick=async()=>{try{await api('/notifications/'+b.dataset.notificationRead+'/read','POST',{});await refreshNotifications();notificationInbox()}catch(e){toast(e.message)}});
  $$('[data-notification-open]').forEach(b=>b.onclick=async()=>{const n=data.items.find(n=>n.id===Number(b.dataset.notificationOpen));try{await api('/notifications/'+n.id+'/read','POST',{});$('#modal').close();state.property=String(n.property_id);state.month=n.date.slice(0,7);state.page='breakage';await render();const row=$(`[data-event-id="${n.reference}"]`);if(row){row.classList.add('notification-highlight');row.scrollIntoView({block:'center',behavior:'smooth'})}}catch(e){toast(e.message)}});
 }catch(e){toast(e.message)}
}
setInterval(()=>{if(!document.hidden)refreshNotifications()},30000);
window.addEventListener('focus',refreshNotifications);

async function reviewsPage(){
 const data=await api(staffMode()?'/corrections':'/reviews');state.reviewData=data;
 data.submissions=(data.submissions||[]).filter(r=>r.status!=='ACCEPTED');
 const priority={RETURNED:0,PENDING:1};data.submissions.sort((a,b)=>priority[a.status]-priority[b.status]||b.id-a.id);
 if(!state.reviewTab)state.reviewTab='breakage';

 const isBreakage=r=>['BREAKAGE','DAMAGE'].includes(r.payload?.type);
 const isNewItem=r=>r.payload?.type==='NEW_ITEM';
 const isPurchase=r=>r.payload?.type==='PURCHASE';

 const breakageSubmissions=data.submissions.filter(isBreakage);
 const newItemSubmissions=data.submissions.filter(isNewItem);
 const purchaseSubmissions=data.submissions.filter(isPurchase);

 const pendingFilter=r=>data.reviewer?r.status==='PENDING':r.status==='RETURNED';
 const pendingBreakage=breakageSubmissions.filter(pendingFilter).length;
 const pendingCounts=data.counts.filter(c=>data.reviewer?['SUBMITTED','IN PROGRESS'].includes(c.status):c.status==='RETURNED').length;
 const pendingNew=newItemSubmissions.filter(pendingFilter).length;
 const pendingPurchases=purchaseSubmissions.filter(pendingFilter).length;
 const totalPending=pendingBreakage+pendingCounts+pendingNew+pendingPurchases;

 const overviewHtml=`<div class="stats approval-overview">${stat('Breakage section',pendingBreakage,data.reviewer?'Awaiting verification':'To correct','break')}${stat('Monthly count section',pendingCounts,data.reviewer?'Awaiting verification':'To correct','count')}${stat('New added items',pendingNew,data.reviewer?'Awaiting approval':'To correct','plus')}${stat('Total pending',totalPending,data.reviewer?'Pending review':'Returned to you','audit')}</div>`;

 const categoryTabsHtml=`<div class="approval-category-tabs" role="tablist"><button type="button" class="approval-tab ${state.reviewTab==='breakage'?'active':''}" data-review-tab-btn="breakage" role="tab" aria-selected="${state.reviewTab==='breakage'}">${icon('break')}<span>Breakage section</span><span class="tab-badge ${pendingBreakage>0?'amber':''}">${pendingBreakage}</span></button><button type="button" class="approval-tab ${state.reviewTab==='counts'?'active':''}" data-review-tab-btn="counts" role="tab" aria-selected="${state.reviewTab==='counts'}">${icon('count')}<span>Monthly count section</span><span class="tab-badge ${pendingCounts>0?'amber':''}">${pendingCounts}</span></button><button type="button" class="approval-tab ${state.reviewTab==='new_item'?'active':''}" data-review-tab-btn="new_item" role="tab" aria-selected="${state.reviewTab==='new_item'}">${icon('plus')}<span>New added item</span><span class="tab-badge ${pendingNew>0?'amber':''}">${pendingNew}</span></button>${purchaseSubmissions.length?`<button type="button" class="approval-tab ${state.reviewTab==='purchases'?'active':''}" data-review-tab-btn="purchases" role="tab" aria-selected="${state.reviewTab==='purchases'}">${icon('box')}<span>Stock purchases</span><span class="tab-badge ${pendingPurchases>0?'amber':''}">${pendingPurchases}</span></button>`:''}<button type="button" class="approval-tab ${state.reviewTab==='all'?'active':''}" data-review-tab-btn="all" role="tab" aria-selected="${state.reviewTab==='all'}">${icon('report')}<span>All</span><span class="tab-badge">${totalPending}</span></button></div>`;

 let contentHtml='';
 if(state.reviewTab==='breakage'){
  const listHtml=submissionLists({...data,submissions:breakageSubmissions});
  contentHtml=`<section class="panel"><div class="panel-head"><h2>${staffMode()?'Returned breakage reports':'Breakage & damage verification'}</h2><span class="badge">${pendingBreakage} awaiting action</span></div><div class="panel-body">${listHtml||empty('No breakage reports awaiting review.','break')}</div></section>`;
 }else if(state.reviewTab==='counts'){
  contentHtml=`<section class="panel"><div class="panel-head"><h2>${staffMode()?'Monthly counts to correct':'Monthly count reviews'}</h2><span class="badge">${data.counts.length} section(s)</span></div><div class="panel-body">${data.counts.length?data.counts.map(c=>`<article class="review-card"><div class="row"><div><strong>${esc(c.section)} · ${esc(c.month)}</strong><p style="margin:4px 0 0 0;font-size:12px;color:var(--muted)">${c.status==='IN PROGRESS'?`<span class="badge amber" style="margin-right:6px">Counting in progress</span>${c.counted_count!=null?`${c.counted_count}/${c.total_count||'—'} counted · `:''}`:''}Submitted by ${esc(c.username||c.staff||'Staff')} · ID ${c.submitted_by||'—'}</p></div>${statusBadge(c.status)}</div><div class="actions" style="margin-top:12px"><button class="primary" data-review-count="${c.section_id}" data-review-month="${c.month}">${data.reviewer?'Review count & differences →':'View count / correct flagged items →'}</button></div></article>`).join(''):empty('No monthly count reviews or corrections needed.','count')}</div></section>`;
 }else if(state.reviewTab==='new_item'){
  const listHtml=submissionLists({...data,submissions:newItemSubmissions});
  contentHtml=`<section class="panel"><div class="panel-head"><h2>${staffMode()?'Returned new item requests':'New item approval'}</h2><span class="badge">${pendingNew} awaiting action</span></div><div class="panel-body">${listHtml||empty('No new item submissions awaiting approval.','plus')}</div></section>`;
 }else if(state.reviewTab==='purchases'){
  const listHtml=submissionLists({...data,submissions:purchaseSubmissions});
  contentHtml=`<section class="panel"><div class="panel-head"><h2>${staffMode()?'Returned purchases':'Stock purchase approvals'}</h2><span class="badge">${pendingPurchases} awaiting action</span></div><div class="panel-body">${listHtml||empty('No stock purchase submissions awaiting review.','box')}</div></section>`;
 }else{
  const listHtml=submissionLists(data);
  contentHtml=`<section class="panel"><div class="panel-head"><h2>${staffMode()?'Returned item lists':'Stock & breakage submissions'}</h2><span class="badge">${data.submissions.filter(r=>r.status!=='ACCEPTED').length} awaiting action</span></div><div class="panel-body">${listHtml||'<p class="help">No item submissions awaiting review.</p>'}</div></section><section class="panel"><div class="panel-head"><h2>${staffMode()?'Monthly counts to correct':'Monthly count reviews'}</h2><span class="badge">${data.counts.length} section(s)</span></div><div class="panel-body">${data.counts.map(c=>`<article class="review-card"><div class="row"><div><strong>${esc(c.section)} · ${esc(c.month)}</strong><p style="margin:4px 0 0 0;font-size:12px;color:var(--muted)">${c.status==='IN PROGRESS'?`<span class="badge amber" style="margin-right:6px">Counting in progress</span>${c.counted_count!=null?`${c.counted_count}/${c.total_count||'—'} counted · `:''}`:''}Submitted by ${esc(c.username||c.staff||'Staff')} · ID ${c.submitted_by||'—'}</p></div>${statusBadge(c.status)}</div><div class="actions" style="margin-top:12px"><button class="primary" data-review-count="${c.section_id}" data-review-month="${c.month}">${data.reviewer?'Review count & differences →':'View count / correct flagged items →'}</button></div></article>`).join('')||'<p class="help">No monthly count reviews needed.</p>'}</div></section>`;
 }

 return pageHead(data.reviewer?'Approvals & corrections':staffMode()?'Corrections for you':'Reports & approvals',staffMode()?'Only your returned lists appear here. Correct marked items, then send the complete list to master.':'Overview of submissions. Differentiate easily between breakage, monthly counts, and new added items.')+overviewHtml+categoryTabsHtml+contentHtml;
}
function bindReviews(){
 $$('[data-review-tab-btn]').forEach(b=>b.onclick=()=>{state.reviewTab=b.dataset.reviewTabBtn;render()});
 $$('[data-review-count]').forEach(b=>b.onclick=()=>{state.page='counts';state.countSection=Number(b.dataset.reviewCount);state.countTab='remaining';state.countSearch='';state.month=b.dataset.reviewMonth;render()});
 $$('[data-review-photo]').forEach(b=>b.onclick=()=>showModal('Report photo',`<img class="preview-full" src="/photo/${esc(b.dataset.reviewPhoto)}" alt="Submitted evidence">`));
 for(const [attr,action] of [['acceptReport','accept'],['returnReport','return']]){
  const selector=attr==='acceptReport'?'[data-accept-report]':'[data-return-report]';
  $$(selector).forEach(b=>b.onclick=async()=>{
   const r=state.reviewData.submissions.find(r=>r.id===Number(b.dataset[attr]));
   if(action==='accept'){
    b.disabled=true;const old=b.textContent;b.textContent='Approving…';
    try{
     await api('/reviews/'+r.id,'POST',{action:'accept',revision:r.revision});
     toast(r.payload?.type==='NEW_ITEM'?'Item approved and added to inventory list.':'Report approved. Stock updated.');
     refreshReviewBadge();
     await render();
    }catch(e){b.disabled=false;b.textContent=old;toast(e.message)}
    return;
   }
   showModal('Return report for correction',field('What must staff correct?','feedback','text','',true),async d=>{await api('/reviews/'+r.id,'POST',{action,revision:r.revision,...d});toast('Returned to the original staff member.');refreshReviewBadge();await render();});
  });
 }
 $$('[data-approve-single]').forEach(b=>b.onclick=async()=>{
  const id=Number(b.dataset.approveSingle),rev=Number(b.dataset.revision);
  const r=state.reviewData?.submissions?.find(x=>x.id===id);
  b.disabled=true;const old=b.textContent;b.textContent='Approving…';
  try{
   await api('/reviews/list','POST',{action:'accept',entries:[{id,revision:rev}],marked:[]});
   toast(r?.payload?.type==='NEW_ITEM'?'Item approved and added to inventory list.':'Report approved. Stock updated.');
   refreshReviewBadge();
   await render();
  }catch(e){b.disabled=false;b.textContent=old;toast(e.message)}
 });
 $$('[data-correct-report]').forEach(b=>b.onclick=async()=>{
  const r=state.reviewData.submissions.find(r=>r.id===Number(b.dataset.correctReport)),p=r.payload;let getPhoto,choices=[];
  if(p.type!=='NEW_ITEM'){try{choices=await itemOptions(p.type==='PURCHASE'?'purchases':'breakage')}catch(e){toast(e.message);return}}
  showModal(r.correction_group?'Correct marked item':'Correct & resubmit',`<p class="notice">${esc(r.feedback)}</p><p>${esc(p.name)} · ${esc(p.date)} (original date)</p>${p.type==='NEW_ITEM'?field('Item name','name','text',p.name,true)+field('Unit','unit','text',p.unit||'Nos',true):selectField('Reported item','item_id',choices.filter(i=>i.section_id===r.section_id).map(i=>[i.id,i.name]),p.item_id)}${field('Correct quantity','qty','number',Math.abs(p.qty),true,`min="${p.type==='NEW_ITEM'?0:1}" step="1"`)}${['PURCHASE','NEW_ITEM'].includes(p.type)?field('Unit rate (leave blank to keep)','rate','number','',false,'min="0" step="0.01"'):''}${field('Reason','reason','text',p.reason||'',p.type==='BREAKAGE'||p.type==='DAMAGE')}${field('Correction explanation','note','text',p.note||'',true)}${p.photo?`<p>Original photo stays unless you take a replacement.</p>${uploadField(false)}`:''}`,async d=>{const photo=getPhoto?.();await api('/corrections/'+r.id,'POST',{action:'resubmit',...d,...(photo?{photo}:{})});toast(r.correction_group?'Correction saved. Send the full list when ready.':'Sent to master for review');refreshReviewBadge();await render()});
  if(p.photo)getPhoto=photoBinding();
 });
 $$('[data-review-list]').forEach(b=>b.onclick=async()=>{
  const group=state.submissionGroups[Number(b.dataset.reviewList)],marked=$$(`[data-mark-group="${b.dataset.reviewList}"]:checked`).map(x=>Number(x.value)),action=b.dataset.listAction;
  if(action==='return'){
   if(!marked.length)return toast('Mark at least one doubtful item.');
   showModal('Return list with marked items',field('What must staff check?','feedback','text','',true),async d=>{await api('/reviews/list','POST',{action,entries:group.map(q=>({id:q.id,revision:q.revision})),marked,...d});toast('Full list returned to its submitter.');refreshReviewBadge();await render()});
   return;
  }
  if(action==='delete'){
   if(!confirm(`Delete this entire submission list (${group.length} item${group.length>1?'s':''})? This cannot be undone.`))return;
   b.disabled=true;const old=b.textContent;b.textContent='Deleting…';
   try{
    await api('/reviews/list','POST',{action:'delete',entries:group.map(q=>({id:q.id,revision:q.revision})),marked:[]});
    toast('Submission list deleted.');
    refreshReviewBadge();
    await render();
   }catch(e){b.disabled=false;b.textContent=old;toast(e.message)}
   return;
  }
  if(action==='accept'){
   b.disabled=true;const old=b.textContent;b.textContent='Approving…';
   try{
    await api('/reviews/list','POST',{action:'accept',entries:group.map(q=>({id:q.id,revision:q.revision})),marked:[]});
    const isNew=group[0]?.payload?.type==='NEW_ITEM';
    toast(isNew?'Item(s) approved and added to inventory list.':'Report(s) approved. Inventory updated.');
    refreshReviewBadge();
    await render();
   }catch(e){b.disabled=false;b.textContent=old;toast(e.message)}
  }
 });
 $$('[data-edit-submission]').forEach(b=>b.onclick=()=>editSubmissionModal(Number(b.dataset.editSubmission)));
 $$('[data-delete-submission]').forEach(b=>b.onclick=async()=>{
  const id=Number(b.dataset.deleteSubmission);
  const name=b.dataset.itemName||'this submission';
  if(!confirm(`Delete "${name}" from approvals? This cannot be undone.`))return;
  b.disabled=true;const old=b.textContent;b.textContent='Deleting…';
  try{
   await api('/reviews/'+id,'DELETE');
   toast(`Deleted "${name}"`);
   refreshReviewBadge();
   await render();
  }catch(e){b.disabled=false;b.textContent=old;toast(e.message)}
 });
 $$('[data-resubmit-list]').forEach(b=>b.onclick=async()=>{
  b.disabled=true;const old=b.textContent;b.textContent='Sending…';
  try{
   await api('/corrections/list/'+b.dataset.resubmitList+'/submit','POST',{});
   toast('Full list sent for review');
   refreshReviewBadge();
   await render();
  }catch(e){b.disabled=false;b.textContent=old;toast(e.message)}
 });
 if($('#return-count-list'))$('#return-count-list').onclick=()=>{
  const marked=$$('[data-mark-count]:checked').map(x=>Number(x.value));if(!marked.length)return toast('Mark at least one item.');
  showModal('Return full monthly count',field('What should the submitter check?','reason','text','',true),async d=>{await api(`/counts/${state.countSection}/${state.month}`,'POST',{action:'return',item_ids:marked,...d});toast('Full count returned with marked items');refreshReviewBadge();await render()});
 };
}
async function editSubmissionModal(qid){
 const r=state.reviewData?.submissions?.find(x=>x.id===qid);
 if(!r)return toast('Submission not found.');
 const p=r.payload;
 const isNew=p.type==='NEW_ITEM';
 const isBreak=['BREAKAGE','DAMAGE'].includes(p.type);
 const isPurch=p.type==='PURCHASE';

 const secOpts=(state.context?.sections||[]).filter(s=>s.active).map(s=>[
  s.id,
  (state.context?.properties?.find(prop=>prop.id===s.property_id)?.name||'Property')+' / '+s.name
 ]);

 let itemSelectHtml='';
 if(!isNew){
  try{
   const items=await api('/items');
   itemSelectHtml=selectField('Link to catalog item (optional)','item_id',[['',`Current: ${esc(p.name)}`],...items.map(i=>[i.id,i.section+' / '+i.name])],p.item_id||'');
  }catch(e){}
 }

 showModal('Edit submission',`
  <div class="form-grid">
   ${selectField('Property / section *','section_id',secOpts,r.section_id)}
   ${itemSelectHtml}
   ${field('Item name * (fix spelling)','name','text',p.name,true)}
   <div id="sub-name-caution" class="field full item-caution-banner" style="display:none" role="alert"></div>
   ${field('Count / quantity *','qty','number',Math.abs(p.qty),true,'min="0" step="1"')}
   ${field('Unit rate (INR)','rate','number',p.rate==null?'':p.rate/100,false,'min="0" step="0.01"')}
   ${isNew?selectField('Unit','unit',[['Nos','Nos'],['Set','Set'],['Pair','Pair'],['Piece','Piece']],p.unit||'Nos'):''}
   ${isNew?field('Specification','specification','text',p.specification||''):''}
   ${isNew?field('Category','category','text',p.category||''):''}
   ${isBreak?field('Breakage reason','reason','text',p.reason||''):''}
   <div class="field full"><label for="f-note">Note / explanation</label><input id="f-note" name="note" type="text" value="${esc(p.note||'')}"></div>
  </div>
  <p class="help">Correct spelling, count quantity, rate, or section directly as admin. Changes save immediately for review.</p>
 `,async d=>{
  if(isNew){
   const sid=Number(d.section_id);
   const rawName=d.name.trim();
   const check=await api(`/items/check-name?name=${encodeURIComponent(rawName)}&section_id=${encodeURIComponent(sid)}&exclude_sub_id=${r.id}`);
   if(check.in_section){
    if(!confirm(`⚠️ CAUTION: An item named "${check.item.name}" already exists in ${check.item.section} (Serial No: ${check.item.code}).\n\nSave changes anyway?`))return;
   }
  }
  await api('/reviews/'+r.id,'POST',{
   action:'edit',
   name:d.name.trim(),
   qty:d.qty,
   rate:d.rate,
   section_id:Number(d.section_id),
   ...(d.item_id?{item_id:Number(d.item_id)}:{}),
   ...(d.unit?{unit:d.unit}:{}),
   ...(d.specification!==undefined?{specification:d.specification}:{}),
   ...(d.category!==undefined?{category:d.category}:{}),
   ...(d.reason!==undefined?{reason:d.reason}:{}),
   ...(d.note!==undefined?{note:d.note}:{})
  });
  toast('Submission updated successfully.');
  refreshReviewBadge();
 });

 $('#dialog-form [type="submit"]').textContent='Save changes';
 if(isNew){
  bindItemNameCaution(null,'sub-name-caution','f-name','f-section_id',r.id);
 }

 if($('#f-item_id')){
  $('#f-item_id').onchange=async e=>{
   const selId=Number(e.target.value);
   if(selId){
    try{
     const items=await api('/items');
     const itm=items.find(i=>i.id===selId);
     if(itm){
      if($('#f-name'))$('#f-name').value=itm.name;
      if($('#f-section_id'))$('#f-section_id').value=itm.section_id;
      if($('#f-rate')&&itm.rate!=null)$('#f-rate').value=itm.rate/100;
     }
    }catch(err){}
   }
  };
 }
}

async function refreshReviewBadge(){
 if(!state.user||document.hidden||(!staffMode()&&!state.user.is_owner))return;
 try{
  const d=await api(staffMode()?'/corrections':'/reviews');
  const n=d.submissions.filter(r=>d.reviewer?r.status==='PENDING':r.status==='RETURNED').length+d.counts.filter(r=>d.reviewer?['SUBMITTED','IN PROGRESS'].includes(r.status):r.status==='RETURNED').length;
  const label=$(staffMode()?'[data-page="corrections"] span':'[data-page="reviews"] span');
  if(label)label.textContent=(staffMode()?'Corrections':'Reports & approvals')+(n?' ('+n+')':'');
 }catch(e){}
}
setInterval(refreshReviewBadge,8000);

let lastReviewHash='';
async function pollReviewsAutoPush(){
 if(!state.user||document.hidden||state.page!=='reviews')return;
 if($('#modal')?.open)return;
 const activeEl=document.activeElement;
 if(activeEl&&['INPUT','TEXTAREA','SELECT'].includes(activeEl.tagName)&&activeEl.id!=='f-property')return;
 try{
  const d=await api(staffMode()?'/corrections':'/reviews');
  const hash=JSON.stringify([
   (d.submissions||[]).map(s=>[s.id,s.status,s.revision,s.updated,s.section_id]),
   (d.counts||[]).map(c=>[c.id,c.status,c.month,c.counted_count,c.submitted_by])
  ]);
  if(lastReviewHash&&hash!==lastReviewHash){
   lastReviewHash=hash;
   state.reviewData=d;
   await render();
  }else{
   lastReviewHash=hash;
  }
 }catch(e){}
}
setInterval(pollReviewsAutoPush,4000);

function staffShell(){
 $('#app').innerHTML=`<div class="staff-shell"><header class="staff-header"><div class="brand"><img src="/static/travelicious-logo.png" alt="Travelicious"><div><strong>Travelicious</strong><small>${esc(state.user.name)} · ${esc(state.user.username)}</small></div></div><button id="profile-button" aria-label="Open profile">Profile</button></header><div class="staff-filters"><select id="property" aria-label="Property">${state.context.properties.map(p=>`<option value="${p.id}" ${String(p.id)===state.property?'selected':''}>${esc(p.name)}</option>`).join('')}</select>${state.page==='counts'?`<span id="staff-count-month" class="badge" aria-label="Automatic count month">${monthLabel()} · automatic</span>`:''}</div><main id="main"></main><nav class="staff-bottom" aria-label="Main navigation">${[['dashboard','Home'],['corrections','Corrections']].map(([key,label])=>`<button data-page="${key}" class="${state.page===key?'active':''}"><span>${label}</span></button>`).join('')}<button id="staff-logout">Log out</button></nav></div>`;
 $('#profile-button').onclick=profileMenu;$('#staff-logout').onclick=logout;
 $$('[data-page]').forEach(b=>b.onclick=()=>{state.page=b.dataset.page;state.countSection=null;render()});
 $('#property').onchange=e=>{state.property=e.target.value;state.countSection=null;render()};
 if($('#month'))$('#month').onchange=e=>{if(e.target.value){state.month=e.target.value;render()}};
}
async function staffDashboard(){
 const inbox=await api('/corrections');const n=inbox.submissions.filter(q=>q.needs_correction||!q.correction_group).length+inbox.counts.length;
 return `<div class="staff-intro"><div class="eyebrow">YOUR WORKSPACE</div><h1>What needs doing?</h1><p>Submit your work. Master checks and accepts it.</p></div><div class="staff-actions">${can('breakage')?`<button class="staff-action primary" data-move="BREAKAGE">${icon('photo')}<span><strong>Report breakage</strong><small>Take a photo and send details</small></span></button>`:''}${can('counts')?`<button class="staff-action" data-nav="counts">${icon('count')}<span><strong>Monthly count</strong><small>Count the items in your section</small></span></button>`:''}${can('add_items')||can('purchases')?`<button class="staff-action" data-nav="addstock">${icon('plus')}<span><strong>Add new items / purchases</strong><small>Send new items or received stock</small></span></button>`:''}</div><div class="notice"><strong>${n?n+' corrections need your attention':'No corrections needed'}</strong><p>Only you can correct submissions returned to you.</p>${n?'<button data-nav="corrections">Open my corrections</button>':''}</div>`;
}
async function staffAddPage(){return pageHead('Add items / purchases','Items and stock are added only after master accepts your submission.')+`<div class="staff-actions">${can('add_items')?'<button class="staff-action primary" data-additem>Add a new item</button>':''}${can('purchases')?'<button class="staff-action" data-move="PURCHASE">Add purchase / received stock</button>':''}</div>`}
function submissionLists(data){
 const grouped=new Map();for(const q of data.submissions){const p=q.payload;const key=q.correction_group||[q.actor,q.section_id,p.type,p.date,q.status].join('/');if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(q)}
 state.submissionGroups=[...grouped.values()];
 return state.submissionGroups.map((group,index)=>{
  const first=group[0],pending=group.every(q=>q.status==='PENDING'),returned=group.every(q=>q.status==='RETURNED');
  const type=first.payload.type;
  const isNew=type==='NEW_ITEM';
  const isBreak=type==='BREAKAGE'||type==='DAMAGE';
  const isPurch=type==='PURCHASE';
  const acceptText=isNew?(group.length>1?'Approve & add items to list':'Approve & add to list'):isBreak?(group.length>1?'Approve full breakage list':'Approve breakage report'):isPurch?(group.length>1?'Approve full purchase list':'Approve purchase'):(group.length>1?'Approve full list':'Approve');
  const canSingleApprove=data.reviewer&&pending&&!first.correction_group&&group.length>1;
  return `<section class="submission-list"><h3>${esc(first.payload.type.replace('_',' '))} · ${esc(first.section)} · ${esc(first.payload.date)}</h3><p>Submitted by ${esc(first.username)} · ID ${first.actor} · ${group.length} item(s)</p>${group.map(q=>{
   const p=q.payload;
   return `<article class="review-card ${q.needs_correction?'marked-correction':''}"><div class="row">${thumb(p)}<div><strong>${esc(p.name)}</strong><p>Quantity: ${Math.abs(p.qty)}</p><small>#${q.id} · Revision ${q.revision}</small></div>${statusBadge(q.status)}</div>${p.specification?`<p>${esc(p.specification)}</p>`:''}${p.photo?`<button class="small" data-review-photo="${esc(p.photo)}">View photo</button>`:''}<p>${esc(p.reason||p.note||'')}</p>${data.reviewer&&p.rate!=null?`<p>Unit rate: ${rupees(p.rate)}</p>`:''}${q.feedback?`<p class="notice">${q.needs_correction?'Recheck':'Review note'}: ${esc(q.feedback)}</p>`:''}${data.reviewer&&pending?`<label class="review-mark"><input type="checkbox" data-mark-group="${index}" value="${q.id}"> Mark this item for recheck</label>`:''}${data.reviewer?`<div class="submission-item-actions" style="margin-top:10px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">${canSingleApprove?`<button type="button" class="small primary" data-approve-single="${q.id}" data-revision="${q.revision}">${isNew?'✓ Approve & add to list':'✓ Approve'}</button>`:''}<button type="button" class="small ghost" data-edit-submission="${q.id}">✏️ Edit</button><button type="button" class="small danger ghost" data-delete-submission="${q.id}" data-item-name="${esc(p.name)}">🗑 Delete</button></div>`:''}${!data.reviewer&&returned?((!q.correction_group||q.feedback)?`<button class="primary" data-correct-report="${q.id}">${q.needs_correction?'Correct item':'Edit correction'}</button>`:'<p class="help">Not marked. Included for reference; no changes needed.</p>'):''}</article>`
  }).join('')}<div class="actions">${data.reviewer&&pending?`<button class="primary" data-review-list="${index}" data-list-action="accept">${acceptText}</button><button data-review-list="${index}" data-list-action="return">${group.length>1?'Return list with marked items':'Return for correction'}</button><button class="danger ghost" data-review-list="${index}" data-list-action="delete">${group.length>1?'🗑 Delete list':'🗑 Delete'}</button>`:''}${!data.reviewer&&returned&&first.correction_group?`<button class="primary" data-resubmit-list="${first.correction_group}" ${group.some(q=>q.needs_correction)?'disabled':''}>Send full list to master</button>`:''}</div></section>`
 }).join('');
}
