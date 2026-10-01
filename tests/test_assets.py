import pytest
from test_workflows import clients, photo
import app as mod

def test_assets_crud_and_export(clients):
    m, s, p = clients
    # 1. Staff cannot access assets endpoints (403 forbidden)
    assert s.get('/api/assets').status_code == 403
    assert p(s, '/assets', {'name': 'AC', 'property_id': 1, 'qty': 2}).status_code == 403
    assert s.get('/api/assets/export').status_code == 403

    # 2. Master can create an asset with photo, rate, count, location, notes
    pic = photo()
    res = p(m, '/assets', {
        'name': 'Split AC 1.5 Ton',
        'property_id': 1,
        'location': 'Room 101',
        'qty': 2,
        'rate': 35000,
        'photo': pic,
        'notes': 'Installed Jan 2026'
    })
    assert res.status_code == 200
    aid1 = res.json['id']
    assert res.json['code'] == 'AST-0001'

    # Create a second asset for property 2 (Travellers Cavern)
    res2 = p(m, '/assets', {
        'name': 'Smart TV 55 inch',
        'property_id': 2,
        'location': 'Lobby',
        'qty': 1,
        'rate': 42000,
        'photo': None,
        'notes': 'Sony Bravia'
    })
    assert res2.status_code == 200
    aid2 = res2.json['id']
    assert res2.json['code'] == 'AST-0002'

    # 3. Retrieve assets: all, filtered by property, filtered by search
    all_assets = m.get('/api/assets').json
    assert len(all_assets) >= 2
    
    # Filter by property 1 (Travelicious)
    prop1_assets = m.get('/api/assets?property=1').json
    assert any(a['id'] == aid1 for a in prop1_assets)
    assert not any(a['id'] == aid2 for a in prop1_assets)

    # Filter by property 2 (Travellers Cavern)
    prop2_assets = m.get('/api/assets?property=2').json
    assert any(a['id'] == aid2 for a in prop2_assets)
    assert not any(a['id'] == aid1 for a in prop2_assets)

    # Search filter
    search_ac = m.get('/api/assets?search=bravia').json
    assert len(search_ac) == 1
    assert search_ac[0]['id'] == aid2

    search_loc = m.get('/api/assets?search=101').json
    assert len(search_loc) == 1
    assert search_loc[0]['id'] == aid1

    # Search by serial number
    search_code = m.get('/api/assets?search=AST-0001').json
    assert len(search_code) == 1
    assert search_code[0]['id'] == aid1

    # 4. Check photo access
    asset1 = next(a for a in prop1_assets if a['id'] == aid1)
    assert asset1['photo'] is not None
    # Master can view photo
    assert m.get('/photo/' + asset1['photo']).status_code == 200
    assert m.get('/photo/thumb-' + asset1['photo']).status_code == 200
    # Staff cannot view asset photo
    assert s.get('/photo/' + asset1['photo']).status_code == 403

    # 5. Edit asset (serial number cannot be changed)
    res_patch = m.patch(f'/api/assets/{aid1}', json={
        'name': 'Split AC 1.5 Ton (Inverter)',
        'code': 'MUTATE_CODE',
        'qty': 3,
        'location': 'Room 102'
    }, headers={'X-CSRF-Token': m.csrf})
    assert res_patch.status_code == 200
    updated = next(a for a in m.get(f'/api/assets?property=1').json if a['id'] == aid1)
    assert updated['name'] == 'Split AC 1.5 Ton (Inverter)'
    assert updated['code'] == 'AST-0001'
    assert updated['qty'] == 3
    assert updated['location'] == 'Room 102'

    # 6. Export assets (xlsx and pdf)
    xlsx_res = m.get('/api/assets/export?property=1&format=xlsx')
    assert xlsx_res.status_code == 200
    assert xlsx_res.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(xlsx_res.data) > 100

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx_res.data))
    sheet = wb.active
    headers = [cell for cell in list(sheet.values)[1]]
    assert 'Serial No' in headers

    pdf_res = m.get('/api/assets/export?property=1&format=pdf')
    assert pdf_res.status_code == 200
    assert pdf_res.headers['Content-Type'] == 'application/pdf'
    assert len(pdf_res.data) > 100

    # 7. Bulk delete
    # Create another asset to test bulk delete
    res3 = p(m, '/assets', {'name': 'Chair', 'property_id': 1, 'qty': 5})
    aid3 = res3.json['id']
    res_bulk = p(m, '/assets/bulk-delete', {'asset_ids': [aid1, aid3]})
    assert res_bulk.status_code == 200
    assert res_bulk.json['deleted'] == 2

    # Check remaining
    assert not any(a['id'] in (aid1, aid3) for a in m.get('/api/assets').json)
    assert any(a['id'] == aid2 for a in m.get('/api/assets').json)

    # 8. Single delete
    res_del = m.delete(f'/api/assets/{aid2}', headers={'X-CSRF-Token': m.csrf})
    assert res_del.status_code == 200
    assert not any(a['id'] == aid2 for a in m.get('/api/assets').json)

def test_inventory_serial_numbers(clients):
    m, s, p = clients
    pic = photo()
    # Creating items assigns sequential INV-0001, INV-0002...
    res1 = p(m, '/items', {'name': 'New Test Item 1', 'section_id': 1, 'photo': pic})
    assert res1.status_code == 200
    item1 = m.get('/api/items?property=1').json
    i1 = next(x for x in item1 if x['id'] == res1.json['id'])
    assert i1['code'] == 'INV-0001'

    res2 = p(m, '/items', {'name': 'New Test Item 2', 'section_id': 1, 'photo': pic})
    assert res2.status_code == 200
    item2 = m.get('/api/items?property=1').json
    i2 = next(x for x in item2 if x['id'] == res2.json['id'])
    assert i2['code'] == 'INV-0002'

    # Master edits item details - code must remain fixed and cannot be changed
    res_patch = m.patch(f"/api/items/{res1.json['id']}", json={'name': 'Renamed Item 1', 'code': 'INV-CHANGED'}, headers={'X-CSRF-Token': m.csrf})
    assert res_patch.status_code == 200
    i1_updated = next(x for x in m.get('/api/items?property=1').json if x['id'] == res1.json['id'])
    assert i1_updated['name'] == 'Renamed Item 1'
    assert i1_updated['code'] == 'INV-0001'
