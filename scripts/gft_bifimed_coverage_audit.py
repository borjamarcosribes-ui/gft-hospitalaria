#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.bifimed_cache import BifimedCache

def parse_args(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('--json', action='store_true', dest='json_output'); p.add_argument('--examples', type=int, default=20); return p.parse_args(argv)

def main(argv=None)->int:
    args=parse_args(argv)
    with SessionLocal() as db:
      cns=[str(r['cn']) for r in db.execute(text('SELECT cn FROM v_gft_publicada ORDER BY cn')).mappings().all()]
      rows=db.query(BifimedCache).filter(BifimedCache.cn.in_(cns)).all() if cns else []
    by_cn={r.cn:r for r in rows}
    fin_si=fin_no=0; con_sit=0; con_restr=0; con_esp=0
    ex_sin=[]; ex_con=[]
    for cn in cns:
      r=by_cn.get(cn)
      if not r:
        if len(ex_sin)<args.examples: ex_sin.append(cn)
        continue
      if (r.situacion_financiacion or '').strip():
        con_sit += 1
        st=(r.situacion_financiacion or '').strip().lower()
        if st in {'si','sí'}: fin_si +=1
        elif st=='no': fin_no +=1
      if (r.condiciones_financiacion_restringidas or '').strip(): con_restr +=1
      if (r.condiciones_especiales_financiacion or '').strip(): con_esp +=1
      if ((r.condiciones_financiacion_restringidas or '').strip() or (r.condiciones_especiales_financiacion or '').strip()) and len(ex_con)<args.examples:
        ex_con.append(cn)
    payload={"total_publicados":len(cns),"con_bifimed_cache":len(rows),"con_situacion_financiacion":con_sit,"financiados_si":fin_si,"financiados_no":fin_no,
      "con_condiciones_restringidas":con_restr,"con_condiciones_especiales":con_esp,"sin_bifimed_cache":len(cns)-len(rows),"examples_sin_cache":ex_sin,"examples_con_condiciones":ex_con}
    print(json.dumps(payload,ensure_ascii=False,indent=2 if args.json_output else None)); return 0
if __name__=='__main__': raise SystemExit(main())
