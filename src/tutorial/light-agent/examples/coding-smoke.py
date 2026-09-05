#!/usr/bin/env python3
"""Build a typed coding request; --send submits it to the loopback Agent /chat endpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    repository = args.repository.resolve()
    bundle = runtime / 'repositories/smoke.bundle'
    revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()
    data = bundle.read_bytes()
    profile = json.loads((runtime / 'coding-profile.json').read_text())
    assert bundle.as_uri().startswith(profile['repositoryUriPrefix'])
    request = {
        'text': 'Change only README.md: append one line saying Codex personal smoke passed. Run git diff --check to validate the change. Do not commit, push, or modify other files.',
        'clientMessageId': str(uuid.uuid4()), 'profile': 'coding',
        'coding': {
            'repository': {'artifactUri': bundle.as_uri(), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest(),
                           'size': len(data), 'mediaType': 'application/x-git-bundle'},
            'baseRevision': revision, 'workspaceRoot': '/workspace/repository',
            'writableRoots': ['/workspace/repository'],
            'allowedTools': ['fs.read', 'fs.write', 'process.exec'],
            'maximumPatchBytes': 65536, 'maximumChangedFiles': 1, 'role': 'implement',
        },
    }
    (runtime / 'coding-request.json').write_text(json.dumps(request, indent=2) + '\n')
    print('Prepared', runtime / 'coding-request.json')
    if not args.send:
        return
    report = json.loads((runtime / 'preflight.json').read_text())
    if not report['codingSchedulable']:
        raise SystemExit('Runner preflight failed. Fix/rebuild and regenerate; do not bypass the feature requirement.')
    import websocket
    token = (runtime / 'service.jwt').read_text().strip().removeprefix('Bearer ')
    session_id = str(uuid.uuid4())
    ws = websocket.create_connection('ws://127.0.0.1:8089/chat?sessionId=' + session_id,
                                     header={'Authorization': 'Bearer ' + token}, timeout=150,
                                     http_no_proxy=['127.0.0.1', 'localhost'])
    try:
        first = json.loads(ws.recv())
        if first.get('type') != 'session':
            raise SystemExit('Session admission failed: ' + json.dumps(first))
        ws.send(json.dumps(request))
        while True:
            message = json.loads(ws.recv())
            print(json.dumps(message))
            if message.get('type') == 'error':
                raise SystemExit('Coding dispatch failed')
            if message.get('type') == 'executionAccepted':
                (runtime / 'accepted.json').write_text(json.dumps(dict(message, sessionId=session_id), indent=2) + '\n')
                print('Accepted for scheduling only. Verify terminal state and patch in operations.agent_ops.')
                return
    finally:
        ws.close()


if __name__ == '__main__':
    main()
