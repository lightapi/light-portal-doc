#!/usr/bin/env python3
"""Prepare tutorial files only; never deploy, publish, issue tokens, or edit admission in place."""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

import yaml


def digest(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def canonical(value):
    # These generated digest inputs contain only ASCII strings, integers and arrays.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def output(*command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path('/home/steve/workspace'))
    parser.add_argument('--instance-id', required=True, type=uuid.UUID)
    parser.add_argument('--agent-image', required=True, help='Exact rebuilt light-agent image tag or digest')
    parser.add_argument('--output', type=Path, help='Optional output directory, for offline verification')
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    deploy = workspace / 'portal-config-loc/all-in-lt'
    old = deploy / 'light-workflow-runner-personal/.runtime'
    dest = (args.output or old / 'codex-personal').resolve()
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest.chmod(0o700)
    host = '01964b05-552a-7c4b-9184-6857e7f3dc5f'
    service = 'com.networknt.agent.codex-personal-1.0.0'
    config = yaml.safe_load((old / 'runner.yml').read_text())
    if config['hostId'] != host or config['maximumConcurrency'] != 1:
        raise SystemExit('Expected the enrolled dev.lightapi.net single-user runner')
    jwt = Path(config['jwtFile']).read_text().strip()
    claims = json.loads(base64.urlsafe_b64decode(jwt.split('.')[1] + '=='))
    scopes = claims.get('scp', [])
    scopes = scopes.split() if isinstance(scopes, str) else scopes
    if (claims.get('host') != host or claims.get('runner_id') != config['runnerId']
            or claims.get('enrollment_id') != config['enrollmentId']
            or claims.get('sub') != 'urn:lightapi:runner:personal-codex-runner'
            or claims.get('aud') != 'urn:lightapi:runner' or 'runner.connect' not in scopes
            or claims.get('exp', 0) <= time.time()):
        raise SystemExit('Renew/correct the existing runner JWT before preparation')
    # Decoding above checks inputs only. The Controller still verifies the JWT signature.
    worker = Path(config['agentWorker']['executable'])
    native = Path(config['agentWorker']['codexExecutable'])
    runner = old / 'light-workflow-runner'
    caps = json.loads(output(str(worker), 'print-capabilities'))
    constants = (workspace / 'light-fabric/crates/coding-agent-runtime/src/lib.rs').read_text()

    def constant(name):
        match = re.search(r'pub const ' + name + r': &str\s*=\s*"([^"]+)";', constants)
        if not match:
            raise SystemExit('Cannot find qualified constant: ' + name)
        return match.group(1)

    version = constant('CODEX_APP_SERVER_VERSION')
    if caps['capabilities']['adapterVersion'] != version:
        raise SystemExit('Installed worker differs from the qualified source; rebuild first')
    if output(str(native), '--version').strip() != 'codex-cli ' + version:
        raise SystemExit('Native Codex version differs from the qualified source')
    if digest(native.read_bytes()) != constant('CODEX_APP_SERVER_BINARY_DIGEST'):
        raise SystemExit('Native Codex binary digest mismatch')
    worker_digest = digest(worker.read_bytes())
    if config['agentWorker']['binaryDigest'] != worker_digest or config['agentWorker']['capabilityDigest'] != caps['capabilityDigest']:
        raise SystemExit('Existing runner worker identity is stale; rebuild/regenerate it first')
    template = json.loads((old / 'command-template.json').read_text())
    if template['binaryDigest'] != worker_digest or template['capabilityDigest'] != caps['capabilityDigest'] or template['executable'] != str(worker):
        raise SystemExit('Command template does not identify this installed worker')
    template_digest = digest(canonical(template))
    if template_digest not in config['allowedCommandTemplateDigests']:
        raise SystemExit('Command template is not admitted')
    evidence_bytes = (workspace / 'light-fabric/contracts/coding-adapters/codex-app-server-v1-qualification.json').read_bytes()
    evidence = json.loads(evidence_bytes)
    if evidence['adapterVersion'] != version or digest(evidence_bytes) != constant('CODEX_APP_SERVER_QUALIFICATION_EVIDENCE_DIGEST'):
        raise SystemExit('Qualification evidence digest mismatch')

    def write(name, value):
        path = dest / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
        path.chmod(0o600)

    config['agentWorker']['originServiceId'] = service
    config['dataDirectory'] = str(dest / 'runner-data')
    # Reuse the existing runner ID, JWT, health port, and exact native installation.
    # The old runner must be stopped before starting this configuration.
    write('runner.yml', yaml.safe_dump(config, sort_keys=False))
    subject = 'urn:lightapi:runner:personal-codex-runner'
    env = dict(os.environ, LIGHT_WORKFLOW_RUNNER_CONFIG_FILE=str(dest / 'runner.yml'))
    admission = json.loads(output(str(runner), 'print-admission', subject, 'light-workflow', env=env))
    write('admission.json', json.dumps(admission, indent=2) + '\n')
    spool = dest / 'repositories'
    spool.mkdir(exist_ok=True, mode=0o700)
    contract = {
        'schemaVersion': 1, 'adapterId': 'codex-app-server-v1', 'adapterVersion': version,
        'adapterProtocolVersion': 'codex-app-server-v2', 'actionKind': 'coding.codex-app-server-v1',
        'compatibilityDigest': config['backend']['compatibilityDigest'],
        # Native installation identity: no worker container is launched by this profile.
        'imageDigest': worker_digest, 'capabilityDigest': caps['capabilityDigest'],
        'templateId': 'coding-codex-app-server-v1', 'templateVersion': 1,
        'templateDigest': template_digest, 'executable': '/usr/local/bin/codex',
        'binaryDigest': constant('CODEX_APP_SERVER_BINARY_DIGEST'),
        'schemaDigest': constant('CODEX_APP_SERVER_SCHEMA_DIGEST'),
        'requiredFeatures': sorted(['codex-app-server-v1', 'canonical-patch-output',
                                    'immutable-repository-upload', 'local-single-user-native-v1']),
    }
    identity = dict(hostId=host, runtimeInstanceId=str(args.instance_id), serviceId=service, envTag='dev')
    profile = dict(contract, productProfileDigest=digest(canonical(identity)),
                   repositoryUriPrefix=spool.as_uri() + '/', model='coding-implementer',
                   reviewModel='coding-reviewer', authenticationProfile='personal-subscription',
                   enterpriseGateway=None,
                   qualification={k: evidence[k] for k in ['schemaVersion', 'adapterId', 'adapterVersion', 'status', 'evaluatedDimensions']})
    profile['qualification'].update(contractDigest=digest(canonical(contract)), evidenceDigest=digest(evidence_bytes))
    write('coding-profile.json', json.dumps(profile, indent=2) + '\n')
    base = yaml.safe_load((deploy / 'docker-compose.yml').read_text())
    agent = copy.deepcopy(base['services']['light-agent'])
    agent.update(image=args.agent_image, hostname='light-agent-codex-personal',
                 container_name='light-agent-codex-personal', ports=['127.0.0.1:8089:8083'])
    agent['environment'].pop('LIGHT_PORTAL_AUTHORIZATION', None)
    agent['environment'].update(LIGHT_AGENT_SERVICE_ID=service, SERVER_SERVICEID=service,
        LIGHT_AGENT_ADVERTISED_ADDRESS='light-agent-codex-personal', LIGHT_AGENT_HOST_ID=host,
        LIGHT_AGENT_STARTUP_HOST='dev.lightapi.net', LIGHT_AGENT_ENVIRONMENT='dev',
        LIGHT_ENV_TAG='dev', LIGHT_AGENT_HTTP_PORT='8083')
    agent['volumes'].append(str(dest / 'service.jwt') + ':/run/codex-personal/service.jwt:ro')
    agent['command'] = ['export LIGHT_PORTAL_AUTHORIZATION="Bearer $$(cat /run/codex-personal/service.jwt)"\n' + agent['command'][0]]
    controller_image = output('docker', 'inspect', 'controller', '--format', '{{.Config.Image}}').strip()
    overlay = {'services': {'light-agent-codex-personal': agent, 'controller': {
        'image': controller_image, 'ports': ['127.0.0.1:8438:8438'],
        'environment': {'CONTROLLER_RUNNER_ENABLED': 'true',
                        'CONTROLLER_RUNNER_ADMISSION_PATH': '/run/runner-admission.json',
                        'CONTROLLER_RUNNER_JWT_AUDIENCE': 'urn:lightapi:runner'},
        'volumes': [str(dest / 'admission.json') + ':/run/runner-admission.json:ro'],
    }}}
    write('compose.yml', yaml.safe_dump(overlay, sort_keys=False))
    needed = set(contract['requiredFeatures']) | {'personal-subscription-auth-v1'}
    backends = admission['enrollments'][0]['backends']
    missing = sorted(needed - set(backends[0]['features']))
    report = dict(instanceId=str(args.instance_id), serviceId=service, adapterVersion=version,
                  missingRunnerFeatures=missing, codingSchedulable=not missing,
                  note='Feature comparison only; readiness and a real turn remain separate gates.')
    write('preflight.json', json.dumps(report, indent=2) + '\n')
    print('Prepared files in', dest)
    print(json.dumps(report, indent=2))
    if missing:
        print('STOP before coding dispatch: rebuild a runner implementing these features; do not hand-edit admission.')


if __name__ == '__main__':
    main()
