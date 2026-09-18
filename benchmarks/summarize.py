import collections,json,statistics,csv
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('run',type=Path);run=p.parse_args().run
rows=[json.loads(s.lstrip('\ufeff')) for s in (run/'results.jsonl').read_text(encoding='utf-8').splitlines()]
groups=collections.defaultdict(list)
for r in rows:
    if r['kind']=='throughput':groups[(r['mode'],r['input_target'],r['concurrency'])].append(r)
summary=[]
for (mode,depth,n),vals in groups.items():
    total_out=sum(v['output_tokens'] for v in vals);wall=sum(v['wall_s'] for v in vals)
    samples=[s for v in vals for s in v['samples']]
    summary.append({'mode':mode,'input_target':depth,'concurrency':n,'repeats':len(vals),'aggregate_output_tok_s':total_out/wall,'median_ttft_s':statistics.median(s['ttft_s'] for s in samples),'median_request_s':statistics.median(s['wall_s'] for s in samples),'peak_total_gpu_mib':max(v['gpu_peak']['memory_mib'] for v in vals),'median_single_stream_decode_tok_s':statistics.median(s['timings']['predicted_per_second'] for s in samples),'median_prompt_tok_s':statistics.median(s['timings']['prompt_per_second'] for s in samples)})
(run/'throughput-summary.json').write_text(json.dumps(summary,indent=2))
if summary:
    with (run/'throughput-summary.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
print(json.dumps(summary,indent=2))
