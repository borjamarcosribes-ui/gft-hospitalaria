from scripts import run_gft_clinical_until_done as mod


def test_stops_on_no_progress(monkeypatch, tmp_path):
    calls={'i':0}
    def fake_run(fn, argv):
        calls['i']+=1
        if fn.__name__=='main' and 'gft_linkage_coverage_audit' in fn.__module__:
            return {'sections': {'coverage_by_section': {'4.1': 1, '4.2': 1, '4.3': 1, '4.4': 1, '4.6': 1}}, 'summaries': {'con_resumen': 1}, 'completion': {'clinical_ready': 1, 'fully_linked_public_detail_ready': 1}}
        if 'sync_gft_clinical_sections' in fn.__module__:
            return {'by_status': {}, 'remaining_syncable_candidates': 0}
        return {'by_source_status': {}, 'no_candidates': True}
    monkeypatch.setattr(mod, '_run_json', fake_run)
    rc = mod.main(['--confirm-write','--json','--runtime-log-dir',str(tmp_path),'--max-runs','2'])
    assert rc == 0
