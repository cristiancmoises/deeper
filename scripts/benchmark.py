"""Reproducible Maigret benchmark against local HTTP, never public profiles."""
import argparse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--sites', type=int, default=500)
    args = parser.parse_args()
    args.output = args.output.resolve()
    project = args.project.resolve()
    sys.path.insert(0, str(project))
    os.chdir(project)
    from deeper.config import Settings
    from deeper.jobs import JobManager

    lock = threading.Lock()
    requests = Counter()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            index = int(self.path.split('/')[2])
            with lock:
                requests['total'] += 1
            time.sleep(0.005)
            code = 200 if index % 10 == 0 else (503 if index % 10 == 1 else 404)
            self.send_response(code)
            self.end_headers()
            self.wfile.write(b'<html><h1>synthetic profile</h1></html>')

        def log_message(self, *args):
            pass

    class Server(ThreadingHTTPServer):
        request_queue_size = 256

    server = Server(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    # Change only fixture endpoints. Keep actual upstream DB loading/ranking,
    # worker lifecycle and official engine. No mock of search()/HTTP/parser.
    worker_script = f'''
import deeper.worker as worker
import deeper.engine as engine
from maigret.sites import MaigretSite
import resource
original_load = engine.load_sites
def load(settings):
    ranked = original_load(settings)
    return {{name: MaigretSite(name, {{'urlMain': {base!r},
        'url': {base!r} + '/site/' + str(index) + '/{{username}}',
        'checkType': 'status_code', 'requestHeadOnly': False,
        'disabled': False, 'tags': ['synthetic']}})
        for index, name in enumerate(ranked)}}
engine.load_sites = load
worker.load_sites = load
original_search = worker.search_username
async def search(username, settings, emit, **kwargs):
    def event(report):
        report['_benchmark_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        emit(report)
    return await original_search(username, settings, event, **kwargs)
worker.search_username = search
raise SystemExit(worker.main())
'''
    original_popen = subprocess.Popen
    children = []

    def local_popen(command, **kwargs):
        child = original_popen([sys.executable, '-c', worker_script], **kwargs)
        children.append(child)
        return child

    subprocess.Popen = local_popen
    settings = Settings(top_sites=args.sites, workers=1, site_timeout=3, search_timeout=30)
    times, reports = [], []
    rss = []
    original_update = JobManager._update

    def observe_update(manager, token, report):
        rss.append(report.pop('_benchmark_rss_bytes', 0))
        return original_update(manager, token, report)

    JobManager._update = observe_update
    try:
        with JobManager(settings) as manager:
            last = None
            for index in range(args.runs):
                start = time.perf_counter()
                token = manager.submit(f'synthetic_{index}', 'benchmark-owner')
                while True:
                    job = manager.snapshot(token, 'benchmark-owner')
                    if job['state'] not in ('queued', 'running'):
                        break
                    time.sleep(0.002)
                times.append(time.perf_counter() - start)
                summary = {key: job[key] for key in ('state', 'checked', 'total', 'unknown')}
                summary['found'] = len(job['profiles'])
                assert summary == {'state': 'done', 'checked': args.sites, 'total': args.sites,
                                   'unknown': len(range(1, args.sites, 10)),
                                   'found': len(range(0, args.sites, 10))}, summary
                reports.append(summary)
                last = (f'synthetic_{index}', token)
            count_before_cache = requests['total']
            start = time.perf_counter()
            token = manager.submit(last[0], 'benchmark-owner')
            while True:
                cached = manager.snapshot(token, 'benchmark-owner')
                if cached['state'] not in ('queued', 'running'):
                    break
                time.sleep(0.002)
            repeat_seconds = time.perf_counter() - start
            cache_hit = token == last[1]
        assert all(child.poll() is not None for child in children)
    finally:
        subprocess.Popen = original_popen
        JobManager._update = original_update
        server.shutdown()
        server.server_close()
        thread.join()
    result = {
        'scenario': 'official Maigret 0.6.6, ranked database + local HTTP, 5ms response delay',
        'python': platform.python_version(), 'platform': platform.platform(),
        'sites': args.sites, 'connections': settings.max_connections, 'workers': 1,
        'runs_seconds': times, 'cold_seconds': times[0],
        'subsequent_median_seconds': statistics.median(times[1:]),
        'repeat_seconds': repeat_seconds, 'repeat_cache_hit': cache_hit,
        'repeat_http_requests': requests['total'] - count_before_cache,
        'spawned_processes': len(children), 'peak_single_worker_rss_bytes': max(rss, default=0),
        'reports': reports, 'http_requests': requests['total'],
        'limits': 'Local measurements only; excludes Docker image, public-site latency and VPS hardware.',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
