#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from app.core.database import SessionLocal
from app.services.gft_export_dataset_service import build_gft_export_dataset

def parse_args(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--scope', default='published')
    p.add_argument('--json', action='store_true', dest='json_output')
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    with SessionLocal() as db:
        rows=build_gft_export_dataset(db)
    out={
        'total_publicados': len(rows),
        'con_bifimed_ok': sum(1 for r in rows if r['bifimed_ok']),
        'con_cima_ok': sum(1 for r in rows if r['cima_ok']),
        'con_secciones_completas': sum(1 for r in rows if r['sections_complete']),
        'con_resumen_clinico': sum(1 for r in rows if r['summary_ok']),
        'fully_linked_public_detail_ready': sum(1 for r in rows if r['fully_linked_public_detail_ready']),
        'examples_blocked': {
            'missing_cima': [r['cn'] for r in rows if not r['cima_ok']][:10],
            'missing_bifimed': [r['cn'] for r in rows if not r['bifimed_ok']][:10],
            'missing_sections': [r['cn'] for r in rows if not r['sections_complete']][:10],
            'missing_summary': [r['cn'] for r in rows if not r['summary_ok']][:10],
            'not_found_cima': [r['cn'] for r in rows if r.get('cima_status') == 'not_found'][:10],
            'not_found_bifimed': [r['cn'] for r in rows if r.get('bifimed_status') == 'not_found'][:10],
        }
    }
    print(json.dumps(out, ensure_ascii=False, indent=2 if args.json_output else None))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
