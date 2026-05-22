#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from urllib.parse import urlsplit, urlunsplit
from sqlalchemy import text
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.core.database import SessionLocal
TARGET=("4.1","4.2","4.3","4.4","4.6")

def mask(url:str|None):
 if not url:return None
 s=urlsplit(url)
 if s.password:return urlunsplit((s.scheme,f"{s.username}:***@{s.hostname}{':' + str(s.port) if s.port else ''}",s.path,s.query,s.fragment))
 return url

def parse():
 p=argparse.ArgumentParser();p.add_argument('--examples',type=int,default=20);p.add_argument('--json',action='store_true',dest='json_output');return p.parse_args()

def main():
 a=parse(); env=os.getenv('DATABASE_URL')
 with SessionLocal() as db:
  db_name=db.execute(text('SELECT current_database()')).scalar_one_or_none()
  rows=db.execute(text('SELECT cn,url_ficha_tecnica FROM v_gft_publicada')).mappings().all(); cns=[r['cn'] for r in rows]
  cov={s:set() for s in TARGET}
  cache=db.query(CimaFichaTecnicaCache.cn,CimaFichaTecnicaCache.seccion).filter(CimaFichaTecnicaCache.sync_status=='ok',CimaFichaTecnicaCache.cn.in_(cns),CimaFichaTecnicaCache.seccion.in_(TARGET),CimaFichaTecnicaCache.contenido_texto.is_not(None),text("trim(contenido_texto)<>''")).all() if cns else []
  for r in cache: cov[r.seccion].add(r.cn)
 payload={"database_url":mask(env),"database_url_missing":not bool(env),"database_name":db_name,"total_publicados":len(rows),"con_seccion_4_1":len(cov['4.1']),"con_seccion_4_2":len(cov['4.2']),"con_seccion_4_3":len(cov['4.3']),"con_seccion_4_4":len(cov['4.4']),"con_seccion_4_6":len(cov['4.6']),"warning": "WARNING: DATABASE_URL no definido" if not env else None}
 print(json.dumps(payload,ensure_ascii=False,indent=2) if a.json_output else json.dumps(payload,ensure_ascii=False))
 return 0
if __name__=='__main__': raise SystemExit(main())
