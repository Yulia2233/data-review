import json,hashlib,os
from pathlib import Path
from collections import Counter
root=Path(os.environ.get('DATA_REVIEW_ROOT', Path(__file__).resolve().parent)).expanduser().resolve();site=Path(os.environ.get('DATA_REVIEW_DATA_DIR', Path(__file__).resolve().parent)).expanduser().resolve();b=root/'stepir_geom_gen/cadcode_synth_datav1_565_v63'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rel=lambda p:str(p.relative_to(root)) if p is not None else None
active=site/'active-catalog.json';payload=json.loads(active.read_text()); marks=site/'annotations/marks.json'; markhash=sha(marks)
rows={x['case']:x for x in payload['rows']}; added=[]
for j in json.loads((b/'jobs.json').read_text()):
 case=j['case'];id='datav1v63--'+case
 output=next((b/sub/case for sub in ('out','smoke_out') if (b/sub/case/'verdict.json').exists()),None)
 if output is None:raise RuntimeError('missing verdict '+case)
 v=json.loads((output/'verdict.json').read_text());t=b/'trajectories'/(case+'.json');export=json.loads(t.read_text())
 if export['id']!=v['session']:raise RuntimeError('session mismatch '+case)
 target=b/'jobs'/case/'target.step'
 if sha(target)!=j['target_sha256']:raise RuntimeError('target mismatch '+case)
 rebuild=next((p for p in (output/'model.step',output/'verify_model_long/candidate.step',output/'verify_model/candidate.step') if p.is_file() and p.stat().st_size),None)
 model=output/'model.py';report=output/'report.json';m=v.get('model') or {};intent=''
 if report.is_file():
  try:intent=str(json.loads(report.read_text()).get('design_intent',''))
  except (ValueError,AttributeError):pass
 row={'case':id,'part_name':j['source_case'],'source_case':case,'batch':'datav1v63','batch_label':'datav1 565 重跑 · v6.3','ir_version':'v6.3','in_batch':True,'in_packed':False,'new_accepted':bool(m.get('ok')) and not m.get('cheated') and not v.get('forbidden_calls'),'ok':bool(m.get('ok')),'riou':m.get('riou'),'minutes':round(v.get('secs',0)/60,1) if 'secs' in v else None,'session':v['session'],'target':rel(target),'rebuild':rel(rebuild),'model':rel(model) if model.is_file() else None,'report':rel(report) if report.is_file() else None,'trajectory':rel(t),'design_intent':intent,'agent_delivered':bool(v.get('model_step')),'target_sha256':sha(target),'trajectory_sha256':sha(t),'relief':bool(j.get('relief'))}
 rows[id]=row;added.append(row)
assert len(added)==565
payload.update(total=len(rows),rows=list(rows.values()),batches=dict(Counter(x['batch'] for x in rows.values())))
for name,data in [('catalog-datav1-v63-565.json',{'total':565,'rows':added}),('active-catalog.json',payload)]:
 p=site/name;tmp=p.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n');os.replace(tmp,p)
assert sha(marks)==markhash
print(json.dumps({'added':len(added),'total':len(rows),'ok':sum(x['ok'] for x in added),'rebuild':sum(bool(x['rebuild']) for x in added),'marks_unchanged':True}))
