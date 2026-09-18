import json
import benchmark as b
rows=[json.loads(s.lstrip('\ufeff')) for s in b.OUT.read_text(encoding='utf-8').splitlines()]
checks=[]
for r in rows:
    if r['kind']!='code':continue
    task=next(t for t in b.TASKS if t[0]==r['case'])
    text=r['response']['choices'][0]['message'].get('content','')
    check=b.check_code(b.extract_code(text),task)
    checks.append({'mode':r['mode'],'case':r['case'],'check':check,'changed_from_original':check['pass']!=r['check']['pass']})
(b.RUN/'code-rescore.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
for r in checks:
    print(r['mode'],r['case'],r['check']['pass'],'CHANGED' if r['changed_from_original'] else '',r['check'].get('error',''))
