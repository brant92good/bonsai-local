"""Compare MTP draft lengths on two concurrent agent workloads."""
import concurrent.futures as cf
import json
from pathlib import Path
import statistics
import time

import benchmark as b
import extended
from server import server


TASKS = [b.TASKS[1], b.TASKS[2]]


def code_sample(task):
    started = time.perf_counter()
    response = b.chat([
        {'role': 'system', 'content': 'Write only Python code defining the requested function. Do not use imports. You may define helper functions. No explanation.'},
        {'role': 'user', 'content': task[1]},
    ], max_tokens=900)
    text = response['choices'][0]['message'].get('content') or ''
    return {
        'case': task[0],
        'check': b.check_code(b.extract_code(text), task),
        'usage': response.get('usage', {}),
        'timings': response.get('timings', {}),
        'wall_s': time.perf_counter() - started,
        'response': response,
    }


def code_pair(mode, repeat):
    started = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        samples = list(pool.map(code_sample, TASKS))
    wall = time.perf_counter() - started
    output_tokens = sum(row['usage'].get('completion_tokens', 0) for row in samples)
    b.save({
        'kind': 'draft_sweep_code',
        'mode': mode,
        'repeat': repeat,
        'concurrency': 2,
        'pass': all(row['check'].get('pass') for row in samples),
        'wall_s': wall,
        'output_tokens': output_tokens,
        'aggregate_tok_s': output_tokens / wall,
        'samples': samples,
    })


def summarize():
    rows = [json.loads(line) for line in b.OUT.read_text(encoding='utf-8').splitlines()]
    result = []
    for mode, draft in [('mtp-off', 0)] + [(f'draft-{n}', n) for n in range(1, 5)]:
        warm = [r for r in rows if r.get('kind') == 'warm_throughput' and r.get('mode') == mode]
        code = [r for r in rows if r.get('kind') == 'draft_sweep_code' and r.get('mode') == mode]
        drafted = sum(s.get('timings', {}).get('draft_n', 0) for r in code for s in r['samples'])
        accepted = sum(s.get('timings', {}).get('draft_n_accepted', 0) for r in code for s in r['samples'])
        total_tokens = sum(r['output_tokens'] for r in code)
        total_wall = sum(r['wall_s'] for r in code)
        result.append({
            'mode': mode,
            'draft_length': draft,
            'warm_median_tok_s': statistics.median(r['aggregate_tok_s'] for r in warm),
            'warm_min_tok_s': min(r['aggregate_tok_s'] for r in warm),
            'warm_max_tok_s': max(r['aggregate_tok_s'] for r in warm),
            'code_pooled_tok_s': total_tokens / total_wall,
            'code_median_wall_s': statistics.median(r['wall_s'] for r in code),
            'code_passes': sum(r['pass'] for r in code),
            'code_runs': len(code),
            'drafted': drafted,
            'accepted': accepted,
            'acceptance': accepted / drafted if drafted else None,
        })
    target = b.RUN / 'draft-sweep-summary.json'
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


def main():
    for draft in range(5):
        mode = 'mtp-off' if draft == 0 else f'draft-{draft}'
        with server(mode, slots=2, context=131072, no_spec=draft == 0, draft=max(draft, 1)):
            for _ in range(3):
                extended.warm(mode, n=2, depth=6144)
            for repeat in range(3):
                code_pair(mode, repeat)
    summarize()


if __name__ == '__main__':
    main()
