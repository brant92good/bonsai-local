import argparse,concurrent.futures as cf,hashlib,json,pathlib,statistics,time,urllib.request
import benchmark as b

def document(depth):
    path=b.RUN/f'retrieval-{depth}.json'
    if path.exists():return json.loads(path.read_text())
    base=b.filler(depth-350,91)
    lines=base.splitlines(keepends=True)
    inserts={int(len(lines)*0.09):'\nCRITICAL RECORD: project NORTH has recovery token ZINNIA-483721.\n',int(len(lines)*0.31):'\nCONFIG version 1: service atlas uses port 8091.\n',int(len(lines)*0.51):'\nCRITICAL RECORD: project SOUTH has checksum 7f4c9e2b18d6.\n',int(len(lines)*0.82):'\nCONFIG version 2 supersedes version 1: service atlas now uses port 17439.\n',int(len(lines)*0.94):'\nCRITICAL RECORD: maximum retry count for job violet is 37.\n'}
    for pos,txt in sorted(inserts.items(),reverse=True):lines.insert(pos,txt)
    doc=''.join(lines)
    prompt='Read the records. Return the exact requested fields at the end.\n<records>\n'+doc+'\n</records>\nReturn ONLY a JSON object with north_recovery_token, south_checksum, atlas_latest_port, violet_max_retries. Use the latest config version for the port.'
    count=len(b.api('/tokenize',{'content':prompt,'add_special':False})['tokens'])
    data={'prompt':prompt,'raw_tokens':count,'expected':{'north_recovery_token':'ZINNIA-483721','south_checksum':'7f4c9e2b18d6','atlas_latest_port':17439,'violet_max_retries':37}}
    path.write_text(json.dumps(data),encoding='utf-8');return data

def retrieval(mode,depth):
    d=document(depth)
    print(f'Starting long retrieval: {mode}, {d["raw_tokens"]} raw tokens',flush=True)
    with b.Monitor() as m:
        r=b.chat([{'role':'user','content':d['prompt']}],max_tokens=160)
    text=r['choices'][0]['message'].get('content','')
    try:
        actual=json.loads(text[text.index('{'):text.rindex('}')+1]);checks={k:actual.get(k)==v for k,v in d['expected'].items()}
    except Exception as e:actual=None;checks={k:False for k in d['expected']}
    b.save({'kind':'retrieval','mode':mode,'target_tokens':depth,'raw_tokens':d['raw_tokens'],'checks':checks,'fields_correct':sum(checks.values()),'pass':all(checks.values()),'wall_s':r['_wall_s'],'usage':r.get('usage'),'timings':r.get('timings'),'gpu_peak':m.summary(),'response':r})

def warm(mode,n=4,depth=6144):
    prompt=(b.RUN/f'filler-{depth}.txt').read_text()
    def req(i,tokens=192):
        t=time.perf_counter()
        r=b.chat([{'role':'user','content':prompt+f'\nAgent assignment {i}: produce a numbered audit checklist.'}],max_tokens=tokens,ignore_eos=True,cache_prompt=True,id_slot=i)
        return {'wall_s':time.perf_counter()-t,'usage':r.get('usage'),'timings':r.get('timings')}
    with cf.ThreadPoolExecutor(max_workers=n) as pool:list(pool.map(lambda i:req(i,1),range(n)))
    with b.Monitor() as m:
        t=time.perf_counter()
        with cf.ThreadPoolExecutor(max_workers=n) as pool:rows=list(pool.map(req,range(n)))
        wall=time.perf_counter()-t
    nt=sum(x['usage']['completion_tokens'] for x in rows)
    b.save({'kind':'warm_throughput','mode':mode,'concurrency':n,'input_target':depth,'wall_s':wall,'aggregate_tok_s':nt/wall,'output_tokens':nt,'cached_tokens':[x['usage'].get('prompt_tokens_details',{}).get('cached_tokens',0) for x in rows],'gpu_peak':m.summary(),'samples':rows})

def api_compat(mode):
    r=b.api('/v1/responses',{'model':'bonsai2-27b','input':'Reply exactly READY.','max_output_tokens':128,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}})
    text=''.join(c.get('text','') for o in r.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text')
    b.save({'kind':'responses_api','mode':mode,'pass':text.strip()=='READY','response':r})
    r=b.api('/v1/messages',{'model':'bonsai2-27b','messages':[{'role':'user','content':'Reply exactly READY.'}],'max_tokens':128,'temperature':0,'chat_template_kwargs':{'enable_thinking':False}})
    text=''.join(c.get('text','') for c in r.get('content',[]) if c.get('type')=='text')
    b.save({'kind':'messages_api','mode':mode,'pass':text.strip()=='READY','response':r})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode');p.add_argument('--depths',nargs='*',type=int,default=[]);p.add_argument('--warm',action='store_true');p.add_argument('--apis',action='store_true');a=p.parse_args()
    if a.warm:
        for n in (1,2,4):warm(a.mode,n)
    if a.apis:api_compat(a.mode)
    for d in a.depths:retrieval(a.mode,d)
