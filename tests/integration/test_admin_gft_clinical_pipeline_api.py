from app.models.gft_estado_presentacion import GFTEstadoPresentacion

ADMIN_HEADERS={"X-Admin-API-Key":"secret"}

def test_admin_pipeline_requires_admin_key(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    r=client.get('/admin/gft/clinical/pipeline-status')
    assert r.status_code==401

def test_admin_pipeline_returns_blocks(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    db_session.add(GFTEstadoPresentacion(cn='111111', estado_gft='incluido', estado_editorial='publicado'))
    db_session.commit()
    r=client.get('/admin/gft/clinical/pipeline-status?limit=20&examples=5&only_missing=true', headers=ADMIN_HEADERS)
    assert r.status_code==200
    body=r.json()
    for key in ('audit','sync_plan','summary_plan','recommendation','safety'):
        assert key in body
    assert body['safety']['read_only'] is True
    assert body['safety']['writes_enabled'] is False
