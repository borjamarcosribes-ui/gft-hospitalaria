#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.services.cima_segmented_sync_service import sync_cima_segmented_section
TARGET=("4.1","4.2","4.3","4.4","4.6")

def mask(url):
 if not url:return None
 s=urlsplit(url)
 if s.password:return urlunsplit((s.scheme,f"{s.username}:***@{s.hostname}{':' + str(s.port) if s.port else ''}",s.path,s.query,s.fragment))
 return url

def parse():
 p=argparse.ArgumentParser();p.add_argument('--sections',nargs='*',default=list(TARGET));p.add_argument('--dry-run',action='store_true');p.add_argument('--force',action='store_true');p.add_argument('--limit',type=int);p.add_argument('--json',action='store_true',dest='json_output');p.add_argument('--confirm-write',action='store_true');p.add_argument('--allow-default-db',action='store_true');p.add_argument('--only-missing',action='store_true');return p.parse_args()

def main():
 a=parse();sections=tuple(s for s in a.sections if s in TARGET)
 if not sections: raise SystemExit('No hay secciones válidas')
 env=os.getenv('DATABASE_URL')
 if not env and not a.allow_default_db: raise SystemExit('WARNING: DATABASE_URL no definido. Bloqueado salvo --allow-default-db')
 if not a.dry_run and not a.confirm_write: raise SystemExit('Safe abort: requiere --confirm-write para escritura real.')
 with SessionLocal() as db:
  db_name=db.execute(text('SELECT current_database()')).scalar_one_or_none()
  rows=db.execute(text('SELECT cn FROM v_gft_publicada ORDER BY cn')).mappings().all()
  if a.limit: rows=rows[:max(0,a.limit)]
  cns=[r['cn'] for r in rows]
  total_cima_ok=db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns),CimaMedicamentoCache.sync_status=='ok').count() if cns else 0
  total_nreg=db.query(CimaMedicamentoCache).filter(CimaMedicamentoCache.cn.in_(cns),CimaMedicamentoCache.sync_status=='ok',text("trim(coalesce(nregistro,''))<>''")).count() if cns else 0
  by={s:{'ok':0,'not_found':0,'not_segmented':0,'section_unavailable':0,'error':0} for s in sections}
  out={"database_url":mask(env),"database_name":db_name,"total_publicados":len(rows),"total_con_cima_cache_ok":total_cima_ok,"total_con_nregistro":total_nreg,"requested_sections":list(sections),"skipped_missing_cima_cache":0,"skipped_missing_nregistro":0,"examples_problematic_cn":[],"by_status":by}
  for cn in cns:
   cm=db.get(CimaMedicamentoCache,cn)
   if cm is None or cm.sync_status!='ok': out['skipped_missing_cima_cache']+=1; out['examples_problematic_cn'].append(cn); continue
   n=(cm.nregistro or '').strip()
   if not n: out['skipped_missing_nregistro']+=1; out['examples_problematic_cn'].append(cn); continue
   for s in sections:
    if a.only_missing and db.query(CimaFichaTecnicaCache).filter(CimaFichaTecnicaCache.cn==cn,CimaFichaTecnicaCache.seccion==s,CimaFichaTecnicaCache.sync_status=='ok').first():
      continue
    if a.dry_run: continue
    row=sync_cima_segmented_section(db=db,nregistro=n,seccion=s,tipo_documento=1,cn=cn,force=a.force)
    st=row.sync_status if row.sync_status in by[s] else 'error'; by[s][st]+=1
  if not a.dry_run: db.commit()
 print(json.dumps(out,ensure_ascii=False,indent=2) if a.json_output else json.dumps(out,ensure_ascii=False))
 return 0
if __name__=='__main__': raise SystemExit(main())
