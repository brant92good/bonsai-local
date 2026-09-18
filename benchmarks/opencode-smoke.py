import json,os,pathlib,subprocess,time,sys
import benchmark as b

def run(mode):
    fixture=b.RUN/'fixture-project'
    fixture.mkdir(exist_ok=True);(fixture/'fixture.txt').write_text('Recovery code: MARIGOLD-59281\n',encoding='utf-8')
    state=b.RUN/'opencode-state'
    env=os.environ.copy()
    for key,sub in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state')]:
        p=state/sub;p.mkdir(parents=True,exist_ok=True);env[key]=str(p)
    config=json.loads((b.ROOT/'opencode.bonsai.example.json').read_text(encoding='utf-8-sig'))
    config['provider']['bonsai']['options']['baseURL']=b.BASE+'/v1'
    config.update({'enabled_providers':['bonsai'],'autoupdate':False,'share':'disabled','snapshot':False,'permission':{'*':'deny','read':'allow','external_directory':'deny'}})
    path=state/'benchmark-config.json';path.write_text(json.dumps(config,indent=2))
    env['OPENCODE_CONFIG']=str(path);env['OPENCODE_CONFIG_CONTENT']=json.dumps(config)
    args=[str(b.ROOT/'clients/opencode/opencode.exe'),'run','--pure','--format','json','--model','bonsai/bonsai2-27b','--dir',str(fixture),'Use the read tool to read fixture.txt in the current directory. Reply with only the recovery code found in the file.']
    start=time.perf_counter()
    try:
        p=subprocess.run(args,env=env,cwd=str(fixture),capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,creationflags=0x08000000)
        (b.RUN/f'opencode-{mode}.stdout.jsonl').write_text(p.stdout,encoding='utf-8');(b.RUN/f'opencode-{mode}.stderr.log').write_text(p.stderr,encoding='utf-8')
        events=[]
        for line in p.stdout.splitlines():
            try:events.append(json.loads(line))
            except Exception:pass
        text='\n'.join(e.get('part',{}).get('text','') for e in events if e.get('type')=='text')
        calls=[e.get('part',{}) for e in events if e.get('type')=='tool_use']
        ok=p.returncode==0 and 'MARIGOLD-59281' in text and any(c.get('tool')=='read' and c.get('state',{}).get('status')=='completed' for c in calls)
        b.save({'kind':'opencode_client','mode':mode,'pass':ok,'returncode':p.returncode,'wall_s':time.perf_counter()-start,'reply':text,'tool_calls':calls,'stderr_tail':p.stderr[-1500:]})
    except subprocess.TimeoutExpired as e:
        (b.RUN/f'opencode-{mode}.stdout.jsonl').write_bytes(e.stdout or b'');(b.RUN/f'opencode-{mode}.stderr.log').write_bytes(e.stderr or b'')
        b.save({'kind':'opencode_client','mode':mode,'pass':False,'error':'timeout after 180s'})
if __name__=='__main__':run(sys.argv[1] if len(sys.argv)>1 else 'mtp-agent-profile')
