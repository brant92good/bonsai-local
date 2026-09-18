"""Run the matched Q8/MTP benchmarks on GPU."""
import argparse
import concurrent.futures as cf
import importlib.util
from pathlib import Path
import time

import benchmark as b
import extended as x
from server import server


def coding_pair(mode):
    def one(task):
        response = b.chat([
            {'role': 'system', 'content': 'Write only Python code defining the requested function. Do not use imports. You may define helper functions. No explanation.'},
            {'role': 'user', 'content': task[1]}], max_tokens=900)
        check = b.check_code(b.extract_code(response['choices'][0]['message'].get('content', '')), task)
        return {'case': task[0], 'check': check, 'usage': response.get('usage'),
                'timings': response.get('timings'), 'response': response}
    start = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one, [b.TASKS[1], b.TASKS[2]]))
    elapsed = time.perf_counter() - start
    tokens = sum(row['usage']['completion_tokens'] for row in rows)
    b.save({'kind': 'concurrent_code', 'mode': mode, 'concurrency': 2,
            'pass': all(row['check']['pass'] for row in rows), 'wall_s': elapsed,
            'output_tokens': tokens, 'aggregate_tok_s': tokens / elapsed, 'samples': rows})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-gpu', action='store_true')
    parser.add_argument('--suite', choices=['two-agent', 'mtp', 'long-context'], default='two-agent')
    args = parser.parse_args()
    if not args.enable_gpu:
        parser.error('Add --enable-gpu to start GPU inference.')
    if args.suite == 'long-context':
        with server('mtp-two-128k'):
            x.retrieval('mtp-two-128k', 120000)
            spec = importlib.util.spec_from_file_location('opencode_smoke', Path(__file__).with_name('opencode-smoke.py'))
            client = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(client)
            client.run('mtp-two-128k')
    else:
        for off in (True, False):
            name = ('mtp-two-control' if off else 'mtp-two-recheck') if args.suite == 'two-agent' else ('mtp-disabled' if off else 'mtp-enabled')
            with server(name, slots=2 if args.suite == 'two-agent' else 4,
                        context_pool=204800 if args.suite == 'two-agent' else 32768, no_spec=off):
                if args.suite == 'two-agent':
                    x.warm(name, 2)
                    coding_pair(name)
                else:
                    for task in b.TASKS:
                        b.code_case(name, task)
                    b.tools_case(name)
                    for depth in (1024, 6144):
                        prompt = (b.RUN / f'filler-{depth}.txt').read_text(encoding='utf-8')
                        for count in (1, 2, 4):
                            b.throughput(name, prompt, count, depth, 0)
                    for count in (1, 4):
                        x.warm(name, count)
    print('Results: ' + str(b.OUT))


if __name__ == '__main__':
    main()
