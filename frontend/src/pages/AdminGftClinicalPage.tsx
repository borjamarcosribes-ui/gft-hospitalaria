import { useState } from 'react';
import { getGftClinicalPipelineStatus } from '../services/adminApi';

const SECTIONS = ['4.1','4.2','4.3','4.4','4.6'];

export function AdminGftClinicalPage(){
  const [apiKey,setApiKey]=useState('');
  const [limit,setLimit]=useState(20);
  const [examples,setExamples]=useState(20);
  const [onlyMissing,setOnlyMissing]=useState(true);
  const [sections,setSections]=useState<string[]>(SECTIONS);
  const [data,setData]=useState<any>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const load=async()=>{setLoading(true);setError(null);try{setData(await getGftClinicalPipelineStatus(apiKey,{limit,examples,only_missing:onlyMissing,sections}));}catch(e){setError((e as Error).message)}finally{setLoading(false)}}
  return <main style={{padding:16}}><h1>Control clínico GFT <span>READ-ONLY</span></h1><p>Auditoría no destructiva de cobertura CIMA y resúmenes clínicos</p><p>Este módulo no escribe datos. Solo muestra dry-run.</p>
  <input placeholder='X-Admin-API-Key' value={apiKey} onChange={e=>setApiKey(e.target.value)}/>
  <input type='number' value={limit} onChange={e=>setLimit(Number(e.target.value)||0)}/>
  <input type='number' value={examples} onChange={e=>setExamples(Number(e.target.value)||0)}/>
  <label><input type='checkbox' checked={onlyMissing} onChange={e=>setOnlyMissing(e.target.checked)}/>only missing</label>
  {SECTIONS.map(s=><label key={s}><input type='checkbox' checked={sections.includes(s)} onChange={e=>setSections(e.target.checked?[...sections,s]:sections.filter(x=>x!==s))}/>{s}</label>)}
  <button onClick={load}>Actualizar dry-run</button>
  {loading && <p>loading</p>}
  {error && <p>{error}</p>}
  {data && <pre>{JSON.stringify(data,null,2)}</pre>}
  </main>
}
