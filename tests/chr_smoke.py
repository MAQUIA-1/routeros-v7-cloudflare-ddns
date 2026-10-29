# RouterOS 7.25 CHR execution checks; see tests/README.md.
import argparse
import json
import re
import tempfile
import threading
import time
import traceback
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import pexpect
parser = argparse.ArgumentParser(description='Run DDNS checks on a fresh RouterOS 7.25 CHR image with a local mock API.')
parser.add_argument('image', type=Path, help='Freshly extracted CHR raw image (changes are discarded).')
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
A = '198.51.100.10'
B = '198.51.100.20'
state = {'mode': 'ok', 'test': False, 'proxy': False, 'requests': [], 'records': {'one.example.com': A, 'two.example.com': A}}

def source():
    s = (ROOT / 'cloudflare-ddns.rsc').read_text().replace(':local WanInterface "ether1"', ':local WanInterface "wan-test"')
    s = re.sub(':local DomainConfigs \\{.*?\\n\\}', ':local DomainConfigs {\n    "one.example.com"={"DnsZoneID"="test";"AuthToken"="test-token"};\n    "two.example.com"={"DnsZoneID"="test";"AuthToken"="test-token"};\n}', s, count=1, flags=re.S)
    s = s.replace('https://api.cloudflare.com/client/v4/zones/$zoneID/dns_records', f'http://10.0.2.2:{server.server_port}/zones/$zoneID/dns_records')
    if state['test']:
        s = s.replace(':local TestMode false', ':local TestMode true')
    if state['proxy']:
        s = s.replace(':local CloudflareProxy false', ':local CloudflareProxy true')
    return s.encode()

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def reply(self, code, body, kind='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body, separators=(',', ':')).encode()
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/source.rsc':
            return self.reply(200, source(), 'text/plain')
        domain = parse_qs(urlparse(self.path).query)['name'][0]
        state['requests'].append(('GET', domain))
        if state['mode'] == 'all-fail':
            return self.reply(403, {'success': False, 'errors': [{'code': 10000, 'message': 'Denied'}]})
        record = {'id': ('1' if domain.startswith('one.') else '2') * 32, 'name': domain, 'type': 'A', 'content': state['records'][domain]}
        return self.reply(200, {'result': [record], 'success': True, 'errors': []})

    def do_PUT(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        domain = body['name']
        state['requests'].append(('PUT', domain, body))
        if state['mode'] == 'partial-fail' and domain.startswith('two.'):
            return self.reply(403, {'success': False, 'errors': [{'code': 10000, 'message': 'Denied'}]})
        if state['mode'] == 'api-fail' and domain.startswith('two.'):
            return self.reply(200, {'success': False, 'errors': [{'code': 10000, 'message': 'Denied'}]})
        state['records'][domain] = body['content']
        return self.reply(200, {'result': body, 'success': True, 'errors': []})
server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
p = pexpect.spawn('qemu-system-x86_64', ['-snapshot', '-m', '256', '-drive', f'file={args.image.resolve()},format=raw', '-nic', 'user,model=e1000', '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-no-reboot'], encoding='utf-8', codec_errors='replace', timeout=60)
log = tempfile.NamedTemporaryFile(mode='w', prefix='ddns-chr-console-', suffix='.log', delete=False)
p.logfile = log
print('Console log:', log.name, flush=True)
prompt = '\\[admin@[^\\]]+\\][^\\r\\n]*> '
try:
    p.expect('Login:', timeout=120)
    p.sendline('admin+ct')
    p.expect('Password:')
    p.sendline('')
    p.expect('Do you want to see the software license[^\\r\\n]*')
    p.sendline('n')
    p.expect('new password>')
    p.sendline('DdnsLocalTest123!')
    p.expect('repeat new password>')
    p.sendline('DdnsLocalTest123!')
    p.expect('Password changed')
    p.expect(prompt)

    def cmd(text, timeout=30):
        p.sendline(text)
        p.expect(prompt, timeout=timeout)
        return p.before.replace('\r', '')

    def install(first=False):
        out = cmd(f'/tool fetch url="http://10.0.2.2:{server.server_port}/source.rsc" dst-path=refactor.rsc')
        assert 'finished' in out, out
        action = 'add name=cloudflare-ddns policy=read,test' if first else 'set cloudflare-ddns'
        out = cmd('/system script ' + action + ' source=[/file get refactor.rsc contents]')
        assert 'syntax error' not in out and 'expected' not in out, out

    def execute():
        state['requests'] = []
        out = cmd('/system script run cloudflare-ddns use-script-permissions')
        assert 'syntax error' not in out and 'expected end' not in out, out
        return out

    def cache():
        out = cmd(':global WanIP4Cur; :put ("CACHE=" . $WanIP4Cur)')
        found = re.findall('^CACHE=([^\\r\\n]*)', out, re.M)
        assert found, out
        return found[-1]

    def wan(value):
        cmd('/ip address set [find where interface="wan-test" disabled=no] address=' + value + '/24')

    def wait_for_idle(timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            out = cmd(':put ("JOBS=" . [:len [/system script job find where script="cloudflare-ddns"]])',
                      timeout=max(0.1, min(5, remaining)))
            count = re.findall(r'^JOBS=(\d+)', out, re.M)
            assert count, out
            if int(count[-1]) == 0:
                return
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        raise AssertionError('DDNS did not finish within the timeout')

    def passed(name):
        print('PASS:', name, flush=True)
    resource = cmd('/system resource print')
    assert re.search('version:\\s+7\\.25\\b', resource), resource
    print('RouterOS 7.25 CHR / read,test / local mock API', flush=True)
    cmd('/interface bridge add name=wan-test')
    cmd('/ip address add address=198.51.100.99/24 interface=wan-test disabled=yes')
    cmd('/ip address add address=' + A + '/24 interface=wan-test')
    install(True)
    out = cmd(':put [:typeof [:parse [/file get refactor.rsc contents]]]')
    assert re.search('\\bcode\\b', out), out
    passed('native source parsing')
    execute()
    assert len(state['requests']) == 4 and cache() == A, state
    passed('initial sync using read,test and disabled address exclusion')
    execute()
    assert not state['requests']
    passed('unchanged IP skips API')
    wan(B)
    state['mode'] = 'partial-fail'
    execute()
    assert state['records']['one.example.com'] == B and state['records']['two.example.com'] == A and (cache() == ''), state
    logs = cmd('/log print detail without-paging where topics~"script"')
    assert 'HTTP 403' in logs, logs
    passed('partial failure, HTTP 403 logging, cache invalidation')
    wan(A)
    state['mode'] = 'ok'
    execute()
    assert len(state['requests']) == 4 and cache() == A and (set(state['records'].values()) == {A}), state
    passed('WAN reversion retries and repairs all records')
    wan(B)
    state['mode'] = 'all-fail'
    execute()
    assert len(state['requests']) == 2 and cache() == ''
    state['mode'] = 'ok'
    execute()
    assert len(state['requests']) == 4 and cache() == B
    passed('total failure followed by retry')
    wan(A)
    state['test'] = True
    install()
    execute()
    assert not state['requests'] and cache() == B
    state['test'] = False
    state['proxy'] = True
    install()
    execute()
    assert len(state['requests']) == 4 and cache() == A and all((r[2]['proxied'] is True for r in state['requests'] if r[0] == 'PUT'))
    passed('TestMode leaves cache unchanged; real run resumes with shared proxy option')
    wan(B)
    state['mode'] = 'api-fail'
    execute()
    assert cache() == ''
    logs = cmd('/log print detail without-paging where topics~"script"')
    assert 'Denied' in logs, logs
    passed('API success=false is logged without marking sync complete')
    state['mode'] = 'ok'
    state['requests'] = []
    cmd(':execute {/system script run cloudflare-ddns use-script-permissions}')
    cmd('/system script run cloudflare-ddns use-script-permissions')
    wait_for_idle()
    logs = cmd('/log print detail without-paging where topics~"script"')
    assert 'Another instance is running' in logs and len(state['requests']) == 4, (logs, state)
    passed('overlapping runs skip the second instance')
    print('ALL CHR TESTS PASSED (mock API; no Cloudflare account used)', flush=True)
except Exception:
    print('TEST FAILED', flush=True)
    traceback.print_exc()
    print(p.before, flush=True)
    raise
finally:
    p.close(force=True)
    server.shutdown()
    log.close()
