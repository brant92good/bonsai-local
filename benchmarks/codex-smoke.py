import json,os,pathlib,subprocess,time
import benchmark as b

def run(mode):
    root=b.RUN/'fixture-project'
    root.mkdir(exist_ok=True)
    (root/'fixture.txt').write_text('Bonsai local integration check.\nRecovery code: MARIGOLD-59281\n',encoding='utf-8')
    state=root/'codex-home';state.mkdir(exist_ok=True)
    env=os.environ.copy();env['CODEX_HOME']=str(state)
    exe=os.environ.get('BONSAI_CODEX','codex.exe')
    args=[exe,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(root),'--json',
      '-c','model_provider="bonsai_benchmark"','-c','model="bonsai2-27b"',
      '-c','model_context_window=131072','-c','model_auto_compact_token_limit=114688',
      '-c','model_reasoning_summary="none"',
      '-c','model_providers.bonsai_benchmark={name="Bonsai benchmark",base_url="http://127.0.0.1:18081/v1",wire_api="responses",requires_openai_auth=false,supports_websockets=false}',
      'Use your shell tool to read fixture.txt in the current directory. Reply with only the recovery code found in that file. Do not edit files or access other directories.']
    t=time.perf_counter()
    try:
        p=subprocess.run(args,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240,creationflags=0x08000000)
        (b.RUN/f'codex-{mode}.stdout.jsonl').write_text(p.stdout,encoding='utf-8');(b.RUN/f'codex-{mode}.stderr.log').write_text(p.stderr,encoding='utf-8')
        events=[]
        for line in p.stdout.splitlines():
            try:events.append(json.loads(line))
            except Exception:pass
        items=[e.get('item',{}) for e in events if e.get('type')=='item.completed']
        messages=[i.get('text','') for i in items if i.get('type')=='agent_message']
        commands=[i for i in items if i.get('type')=='command_execution']
        ok=p.returncode==0 and any(m.strip()=='MARIGOLD-59281' for m in messages) and any(c.get('exit_code')==0 for c in commands)
        b.save({'kind':'codex_client','mode':mode,'pass':ok,'returncode':p.returncode,'commands':commands,'messages':messages,'wall_s':time.perf_counter()-t,'stderr_tail':p.stderr[-3000:]})
    except subprocess.TimeoutExpired as e:
        (b.RUN/f'codex-{mode}.stdout.jsonl').write_bytes(e.stdout or b'');(b.RUN/f'codex-{mode}.stderr.log').write_bytes(e.stderr or b'')
        b.save({'kind':'codex_client','mode':mode,'pass':False,'error':'timeout after 240s','wall_s':time.perf_counter()-t})

    except Exception as e:
        b.save({'kind':'codex_harness_error','mode':mode,'pass':False,'error':repr(e)})

if __name__=='__main__':
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else 'pq2-q8-two-128k')
