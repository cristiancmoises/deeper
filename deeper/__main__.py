"""Production HTTP entry point, also usable on Windows."""
import argparse
import signal
from waitress import serve

from .app import create_app


def main():
    parser = argparse.ArgumentParser(description='Deeper: Maigret with native HTML and CSS')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    # A normal service/container stop must reach the cleanup in finally.
    def terminate(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, terminate)
    app = create_app()
    print(f'Deeper is available at http://{args.host}:{args.port}', flush=True)
    try:
        serve(app, host=args.host, port=args.port, threads=8, clear_untrusted_proxy_headers=True)
    finally:
        app.extensions['deeper_jobs'].close()


if __name__ == '__main__':
    main()
