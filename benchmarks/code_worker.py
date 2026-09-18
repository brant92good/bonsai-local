import builtins, copy, json, sys
p=json.load(sys.stdin)
names=['abs','all','any','bool','dict','enumerate','filter','float','int','isinstance','len','list','map','max','min','next','range','reversed','round','set','sorted','str','sum','tuple','zip','ValueError','TypeError','KeyError','IndexError','StopIteration']
scope={'__builtins__':{n:getattr(builtins,n) for n in names}}
exec(compile(p['code'],'generated.py','exec'),scope)
rows=[]
for args,expected in p['tests']:
 original=copy.deepcopy(args)
 try:
  supplied=copy.deepcopy(args)
  actual=scope[p['fn']](supplied) if p['single'] else scope[p['fn']](*supplied)
  mutation_ok=(supplied==args) if p['single'] else True
  rows.append({'pass':actual==expected and mutation_ok,'actual':actual,'expected':expected,'mutation_ok':mutation_ok})
 except Exception as e: rows.append({'pass':False,'error':str(e)})
print(json.dumps({'pass':all(r['pass'] for r in rows),'tests':rows}))
