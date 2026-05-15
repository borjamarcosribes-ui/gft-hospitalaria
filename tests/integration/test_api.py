from io import BytesIO
import pandas as pd


def test_health(client):
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


def test_import_endpoints(client, admin_headers):
    df = pd.DataFrame([
        {"CN": "123456", "Observaciones revisión": "SI", "Estado editorial": "publicado"}
    ])
    bio = BytesIO()
    df.to_excel(bio, index=False)
    files = {"file": ("test.xlsx", bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post('/imports/excel', files=files, headers=admin_headers)
    assert r.status_code == 200
    batch_id = r.json()['batch_id']
    r2 = client.get(f'/imports/{batch_id}', headers=admin_headers)
    assert r2.status_code == 200
    r3 = client.get(f'/imports/{batch_id}/rows', headers=admin_headers)
    assert r3.status_code == 200
