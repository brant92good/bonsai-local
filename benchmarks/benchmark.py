import argparse, ast, concurrent.futures as cf, copy, datetime, hashlib, json, math, os, pathlib, re, statistics, subprocess, sys, threading, time, urllib.request
ROOT=pathlib.Path(os.environ.get('BONSAI_ROOT',str(pathlib.Path(__file__).resolve().parents[1])))
RUN=pathlib.Path(os.environ.get('BONSAI_BENCH_OUTPUT',str(ROOT/'benchmark-runs'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))))
RUN.mkdir(parents=True,exist_ok=True)
for fixture in ('filler-1024.txt','filler-6144.txt','retrieval-120000.json'):
    source=pathlib.Path(__file__).parent/'fixtures'/fixture
    if source.exists() and not (RUN/fixture).exists():(RUN/fixture).write_bytes(source.read_bytes())
BASE='http://127.0.0.1:18081'
OUT=RUN/'results.jsonl'
LOCK=threading.Lock()
def save(r):
    r['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with LOCK:
        with OUT.open('a',encoding='utf-8') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('response','prompt','samples','gpu_samples')},ensure_ascii=True),flush=True)
def api(path,body=None,timeout=1200):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
def gpu():
    p=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,creationflags=0x08000000)
    try:
        a=[float(x.strip()) for x in p.stdout.splitlines()[0].split(',')]
        return dict(zip(('memory_mib','util_pct','temp_c','power_w'),a))
    except Exception:return {'error':p.stdout[:100]}
class Monitor:
    def __enter__(self):
        self.samples=[];self.stop=threading.Event()
        def loop():
            while not self.stop.is_set():
                self.samples.append(gpu());self.stop.wait(2)
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,*args):self.stop.set();self.thread.join(5)
    def summary(self):
        return {k:max((x.get(k,0) for x in self.samples),default=0) for k in ('memory_mib','temp_c','power_w')}
def chat(messages,max_tokens=768,**kwargs):
    b={'model':'bonsai2-27b','messages':messages,'max_tokens':max_tokens,'temperature':0,'seed':12345,'chat_template_kwargs':{'enable_thinking':False},'cache_prompt':False,**kwargs}
    t=time.perf_counter();r=api('/v1/chat/completions',b);r['_wall_s']=time.perf_counter()-t;return r
TASKS=[
 ('intervals','Implement merge_intervals(intervals). Each interval is a pair of integers [start,end] with start<=end. Return a sorted list of merged closed intervals: endpoints touching must merge. Do not mutate the input.', 'merge_intervals', [([[1,3],[2,6],[8,10],[10,12]],[[1,6],[8,12]]),([],[]),([[2,2],[1,1]],[[1,1],[2,2]]),([[-5,-1],[-2,4],[8,9]], [[-5,4],[8,9]]),([[1,10],[2,3]],[[1,10]])]),
 ('topological','Implement topo(nodes, edges). Return the lexicographically smallest topological ordering of distinct string nodes. Each edge [u,v] means u comes before v. Ignore duplicate edges. Return [] for a cycle. Nodes include all edge endpoints.', 'topo', [([['c','a','b'],[['a','c'],['b','c']]],['a','b','c']),([['a','b'],[['a','b'],['a','b']]],['a','b']),([['a','b'],[['a','b'],['b','a']]],[]),([['b','a','c'],[]],['a','b','c']),([[],[]],[])]),
 ('lru','Implement lru(capacity, operations). Each operation is ["put",key,value] or ["get",key]. Return a list of results for get operations only (-1 for missing). Successful get and every put make the key most recently used. On overflow evict least recently used. Capacity can be zero.', 'lru', [([2,[['put','a',1],['put','b',2],['get','a'],['put','c',3],['get','b'],['get','c']]],[1,-1,3]),([0,[['put','a',1],['get','a']]],[-1]),([1,[['put','x',1],['put','x',2],['get','x'],['put','y',3],['get','x']]], [2,-1])]),
 ('lookup','Implement lookup(obj, path, default). path is a list of dictionary string keys or list integer indexes. Return the value at the path, including None/False/0/empty containers. If any component is missing, the wrong type, or an index is negative/out of range, return default. Empty path returns obj.', 'lookup', [([{'a':[{'b':0}]},['a',0,'b'],'missing'],0),([{'a':None},['a'],4],None),([{'a':[1]},['a',-1],9],9),([{'x':False},['x'],True],False),([{'x':[]},['x',0],'bad'],'bad'),([{},[],None],{})]),
 ('versions','Implement compare_versions(a,b). Inputs contain only non-negative decimal integer components separated by dots. Compare numerically, ignoring trailing zero components. Return -1, 0 or 1. Components can have leading zeros.', 'compare_versions', [(['1.2','1.2.0'],0),(['1.10','1.9'],1),(['01.002','1.2'],0),(['0.0.0','0'],0),(['2','2.0.1'],-1),(['10.0','9.999'],1)]),
 ('ratelimit','Implement allow_events(events,limit,window). events is a nondecreasing-by-time list [user,timestamp]. Return a boolean per event. Allow at most limit previously accepted events for the same user in (timestamp-window,timestamp]; reject if already at the limit. Rejected events do NOT consume capacity. window>0, limit>=0. Events at identical timestamps are processed in input order.', 'allow_events', [([[['a',0],['a',1],['a',2],['a',10],['b',10]],2,10],[True,True,False,True,True]),([[['a',0],['a',0],['a',5]],1,5],[True,False,True]),([[['a',0]],0,5],[False]),([[],2,5],[])])
]
SINGLE={'intervals'}
def check_code(code,task):
    _,_,fn,tests=task
    try:
        tree=ast.parse(code)
        forbidden=(ast.Import,ast.ImportFrom,ast.ClassDef,ast.Global,ast.Nonlocal)
        for n in ast.walk(tree):
            if isinstance(n,forbidden):raise ValueError('imports/classes/global disallowed')
            if isinstance(n,ast.Attribute) and n.attr.startswith('_'):raise ValueError('private attribute disallowed')
            if isinstance(n,ast.Name) and (n.id.startswith('__') or n.id in {'eval','exec','open','compile','getattr','setattr','globals','locals','input','help','breakpoint'}):raise ValueError('unsafe name')
        worker=RUN/'code_worker.py'
        payload={'code':code,'fn':fn,'tests':tests,'single':task[0] in SINGLE}
        p=subprocess.run([sys.executable,'-I',str(worker)],input=json.dumps(payload),capture_output=True,text=True,timeout=5,creationflags=0x08000000)
        return json.loads(p.stdout) if p.returncode==0 else {'pass':False,'error':p.stderr[-500:]}
    except Exception as e:return {'pass':False,'error':str(e)}
def extract_code(text):
    m=re.search(r'```(?:python)?\s*\n(.*?)```',text,re.S)
    return m.group(1) if m else text.strip()
def code_case(mode,task):
    r=chat([{'role':'system','content':'Write only Python code defining the requested function. Do not use imports. You may define helper functions. No explanation.'},{'role':'user','content':task[1]}],max_tokens=900)
    text=r['choices'][0]['message'].get('content') or ''
    result=check_code(extract_code(text),task)
    save({'kind':'code','mode':mode,'case':task[0],'check':result,'wall_s':r['_wall_s'],'usage':r.get('usage'),'timings':r.get('timings'),'finish':r['choices'][0]['finish_reason'],'response':r})
def tools_case(mode):
    tool={'type':'function','function':{'name':'lookup_order','description':'Look up an order by exact order ID.','parameters':{'type':'object','properties':{'order_id':{'type':'string'}},'required':['order_id'],'additionalProperties':False}}}
    messages=[{'role':'system','content':'Use the lookup_order tool to obtain order status. Never invent the status.'},{'role':'user','content':'What is the status of order ORD-7392?'}]
    r=chat(messages,tools=[tool],max_tokens=200)
    msg=r['choices'][0]['message']; calls=msg.get('tool_calls',[])
    ok=False;roundtrip=False; second=None
    if len(calls)==1:
        c=calls[0]
        try:ok=c['function']['name']=='lookup_order' and json.loads(c['function']['arguments'])=={'order_id':'ORD-7392'}
        except Exception:pass
        if ok:
            messages += [msg,{'role':'tool','tool_call_id':c['id'],'content':'{"order_id":"ORD-7392","status":"awaiting pickup","pickup_code":"LARCH-284"}'}]
            second=chat(messages,tools=[tool],max_tokens=180)
            text=second['choices'][0]['message'].get('content','').lower()
            roundtrip='awaiting pickup' in text and 'larch-284' in text
    save({'kind':'tools','mode':mode,'arguments_ok':ok,'roundtrip_ok':roundtrip,'response':[r,second]})
def filler(target,seed=0):
    # Public synthetic ledger: no user files enter model prompts.
    lines=[]
    for i in range(max(50,int(target/20))):
        v=hashlib.sha256(f'{seed}:{i}'.encode()).hexdigest()[:12]
        lines.append(f'Ledger entry {i:06d}: parcel {v}, zone {i%31:02d}, quantity {i%97+1}; routine audit, no exception.\n')
    txt=''.join(lines)
    tokens=api('/tokenize',{'content':txt,'add_special':False})['tokens']
    while len(tokens)<target:
        txt+=txt;tokens=api('/tokenize',{'content':txt,'add_special':False})['tokens']
    text=api('/detokenize',{'tokens':tokens[:target]})['content']
    return text

def stream_request(prompt,reqid):
    b={'model':'bonsai2-27b','messages':[{'role':'user','content':prompt+f'\nWork item {reqid}: write a detailed audit checklist for this ledger. Continue with numbered items.'}],'max_tokens':192,'ignore_eos':True,'temperature':0,'seed':12345,'chat_template_kwargs':{'enable_thinking':False},'cache_prompt':False,'stream':True,'stream_options':{'include_usage':True},'timings_per_token':True}
    t=time.perf_counter();first=None;last={};usage={};timings={};chunks=0
    req=urllib.request.Request(BASE+'/v1/chat/completions',data=json.dumps(b).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=1200) as res:
        for line in res:
            if not line.startswith(b'data: '):continue
            s=line[6:].strip()
            if s==b'[DONE]':break
            item=json.loads(s);last=item
            if item.get('usage'):usage=item['usage']
            if item.get('timings'):timings=item['timings']
            delta=(item.get('choices') or [{}])[0].get('delta',{})
            if delta.get('content') or delta.get('reasoning_content'):
                if first is None:first=time.perf_counter()-t
                chunks+=1
    return {'wall_s':time.perf_counter()-t,'ttft_s':first,'usage':usage,'timings':timings,'chunks':chunks}
def throughput(mode,prompt,n,depth,repeat):
    with Monitor() as mon:
        t=time.perf_counter()
        with cf.ThreadPoolExecutor(max_workers=n) as pool:rows=list(pool.map(lambda i:stream_request(prompt,f'{mode}-{repeat}-{i}'),range(n)))
        wall=time.perf_counter()-t
    nt=sum(x['usage'].get('completion_tokens',x['timings'].get('predicted_n',0)) for x in rows)
    save({'kind':'throughput','mode':mode,'concurrency':n,'input_target':depth,'repeat':repeat,'wall_s':wall,'output_tokens':nt,'aggregate_tok_s':nt/wall,'median_ttft_s':statistics.median(x['ttft_s'] for x in rows),'median_request_s':statistics.median(x['wall_s'] for x in rows),'gpu_peak':mon.summary(),'samples':rows})
def suite(mode):
    save({'kind':'suite_start','mode':mode,'gpu':gpu(),'props':{k:v for k,v in api('/props').items() if k in ('total_slots','build_info','default_generation_settings')}})
    for task in TASKS:code_case(mode,task)
    tools_case(mode)
    for depth in (1024,6144):
        path=RUN/f'filler-{depth}.txt'
        if not path.exists():path.write_text(filler(depth,73),encoding='utf-8')
        prompt=path.read_text(encoding='utf-8')
        for repeat in range(2):
            for n in (1,2,4):throughput(mode,prompt,n,depth,repeat)
    save({'kind':'suite_end','mode':mode,'gpu':gpu()})
WORKER='''import builtins, copy, json, sys\np=json.load(sys.stdin)\nnames=['abs','all','any','bool','dict','enumerate','filter','float','int','isinstance','len','list','map','max','min','next','range','reversed','round','set','sorted','str','sum','tuple','zip','ValueError','TypeError','KeyError','IndexError','StopIteration']\nscope={'__builtins__':{n:getattr(builtins,n) for n in names}}\nexec(compile(p['code'],'generated.py','exec'),scope)\nrows=[]\nfor args,expected in p['tests']:\n original=copy.deepcopy(args)\n try:\n  supplied=copy.deepcopy(args)\n  actual=scope[p['fn']](supplied) if p['single'] else scope[p['fn']](*supplied)\n  mutation_ok=(supplied==args) if p['single'] else True\n  rows.append({'pass':actual==expected and mutation_ok,'actual':actual,'expected':expected,'mutation_ok':mutation_ok})\n except Exception as e: rows.append({'pass':False,'error':str(e)})\nprint(json.dumps({'pass':all(r['pass'] for r in rows),'tests':rows}))\n'''
(RUN/'code_worker.py').write_text(WORKER,encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode');a=p.parse_args();suite(a.mode)
