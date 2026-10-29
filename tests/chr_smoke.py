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
POLICIES = ('read', 'write', 'policy', 'test')
POLICY = ','.join(POLICIES)
SCHEDULER = 'cloudflare-ddns-scheduler'
INTERVAL = 10
state = {'mode': 'ok', 'test': False, 'proxy': False, 'requests': [], 'request_times': [], 'records': {'one.example.com': A, 'two.example.com': A}}

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
        state['request_times'].append(time.monotonic())
        if state['mode'] == 'all-fail':
            return self.reply(403, {'success': False, 'errors': [{'code': 10000, 'message': 'Denied'}]})
        record = {'id': ('1' if domain.startswith('one.') else '2') * 32, 'name': domain, 'type': 'A', 'content': state['records'][domain]}
        return self.reply(200, {'result': [record], 'success': True, 'errors': []})

    def do_PUT(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        domain = body['name']
        state['requests'].append(('PUT', domain, body))
        state['request_times'].append(time.monotonic())
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
        out = p.before.replace('\r', '')
        assert not re.search(r'(?m)^(syntax error|expected end of command|bad command name)', out), out
        return out

    def install(first=False):
        out = cmd(f'/tool fetch url="http://10.0.2.2:{server.server_port}/source.rsc" dst-path=refactor.rsc')
        assert 'finished' in out, out
        action = f'add name=cloudflare-ddns policy={POLICY}' if first else 'set cloudflare-ddns'
        out = cmd('/system script ' + action + ' source=[/file get refactor.rsc contents]')
        assert 'syntax error' not in out and 'expected' not in out, out

    def script_logs():
        out = cmd(':foreach entry in=[/log find where topics~"script"] do={ '
                  ':put ("LOG=" . [:tostr $entry] . "|" . [/log get $entry message]) }')
        return dict(re.findall(r'^LOG=(\*\w+)\|([^\r\n]*)', out, re.M))

    def new_logs(previous):
        return '\n'.join(message for key, message in script_logs().items() if key not in previous)

    def execute():
        previous = script_logs()
        state['requests'] = []
        state['request_times'] = []
        out = cmd('/system script run cloudflare-ddns use-script-permissions')
        assert 'syntax error' not in out and 'expected end' not in out, out
        return new_logs(previous)

    def cache():
        out = cmd(':local value ""; '
                  ':foreach entry in=[/system script environment find where name="WanIP4Cur"] do={ '
                  ':set value [/system script environment get $entry value] }; '
                  ':put ("CACHE=" . $value)')
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

    def scalar(expression):
        out = cmd(':put ("VALUE=" . (' + expression + '))')
        found = re.findall(r'^VALUE=([^\r\n]*)', out, re.M)
        assert found, out
        return found[-1]

    def stop_scheduler():
        cmd(f'/system scheduler remove [find where name="{SCHEDULER}"]')
        wait_for_idle()

    def start_scheduler(policy=POLICY, script_policy=None, clear_cache=True):
        stop_scheduler()
        cmd(f'/system script set cloudflare-ddns policy={script_policy or policy}')
        if clear_cache:
            cmd('/system script environment remove [find where name="WanIP4Cur"]')
            assert cache() == ''
        state['requests'] = []
        state['request_times'] = []
        previous = script_logs()
        started = time.monotonic()
        cmd(f'/system scheduler add name={SCHEDULER} interval={INTERVAL}s '
            f'on-event=cloudflare-ddns policy={policy}')
        assert scheduled_count() == 0
        return previous, started

    def scheduled_count():
        return int(scalar(f'[/system scheduler get [find where name="{SCHEDULER}"] run-count]'))

    def wait_scheduled(after):
        deadline = time.monotonic() + INTERVAL + 30
        while time.monotonic() < deadline:
            count = scheduled_count()
            if count > after:
                assert count == after + 1, f'Missed scheduled execution: {after} -> {count}'
                wait_for_idle()
                return
            time.sleep(0.5)
        raise AssertionError('Scheduled execution did not start within the timeout')

    resource = cmd('/system resource print')
    assert re.search('version:\\s+7\\.25\\b', resource), resource
    print(f'RouterOS 7.25 CHR / {POLICY} / local mock API', flush=True)
    cmd('/interface bridge add name=wan-test')
    cmd('/ip address add address=198.51.100.99/24 interface=wan-test disabled=yes')
    cmd('/ip address add address=' + A + '/24 interface=wan-test')
    install(True)
    out = cmd(':put [:typeof [:parse [/file get refactor.rsc contents]]]')
    assert re.search('\\bcode\\b', out), out
    passed('native source parsing')
    execute()
    assert len(state['requests']) == 4 and cache() == A, state
    passed('initial sync and disabled address exclusion')
    execute()
    assert not state['requests']
    passed('unchanged IP skips API')
    wan(B)
    state['mode'] = 'partial-fail'
    logs = execute()
    assert state['records']['one.example.com'] == B and state['records']['two.example.com'] == A and (cache() == ''), state
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
    logs = execute()
    assert cache() == ''
    assert 'Denied' in logs, logs
    passed('API success=false is logged without marking sync complete')
    state['mode'] = 'ok'
    state['requests'] = []
    previous = script_logs()
    cmd(':execute {/system script run cloudflare-ddns use-script-permissions}')
    cmd('/system script run cloudflare-ddns use-script-permissions')
    wait_for_idle()
    logs = new_logs(previous)
    assert 'Another instance is running' in logs and len(state['requests']) == 4, (logs, state)
    passed('overlapping runs skip the second instance')

    # Scheduled execution uses the real updater and an accelerated interval.
    state['test'] = False
    state['proxy'] = False
    install()
    wan(A)
    state['records'] = dict.fromkeys(state['records'], '1.1.1.1')
    previous, started = start_scheduler()
    wait_scheduled(0)
    assert min(state['request_times']) - started >= INTERVAL - 1
    assert len(state['requests']) == 4 and set(state['records'].values()) == {A}, state
    assert cache() == A
    wait_scheduled(1)
    stop_scheduler()
    logs = new_logs(previous)
    assert len(state['requests']) == 4 and cache() == A, state
    assert logs.count('Record updated:') == 2 and 'No IP change:' in logs, logs
    passed('scheduler waits one interval, updates both records, retains cache, and skips unchanged IP')

    # Equal script and scheduler policies isolate each missing permission.
    for missing in POLICIES:
        state['records'] = dict.fromkeys(state['records'], B)
        policy = ','.join(name for name in POLICIES if name != missing)
        previous, _ = start_scheduler(policy)
        wait_scheduled(0)
        assert cache() == '', missing
        if missing in ('read', 'test'):
            stop_scheduler()
            logs = new_logs(previous)
            assert not state['requests'] and set(state['records'].values()) == {B}, state
            assert 'not enough permissions' in logs, logs
            if missing == 'test':
                assert '/tool/fetch' in logs, logs
            passed(f'permission check: excluding {missing} blocks required operations')
        else:
            assert len(state['requests']) == 4 and set(state['records'].values()) == {A}, state
            wait_scheduled(1)
            stop_scheduler()
            logs = new_logs(previous)
            assert cache() == '' and len(state['requests']) == 8, state
            assert logs.count('Record updated:') == 4 and 'No IP change:' not in logs, logs
            passed(f'permission check: excluding {missing} loses cache and repeats updates')

    state['records'] = dict.fromkeys(state['records'], B)
    previous, _ = start_scheduler(script_policy='read,test')
    wait_scheduled(0)
    assert len(state['requests']) == 4 and cache() == A, state
    wait_scheduled(1)
    stop_scheduler()
    logs = new_logs(previous)
    assert len(state['requests']) == 4 and 'No IP change:' in logs, (logs, state)
    passed('named on-event invocation inherits scheduler permissions with script policy read,test')

    wan(B)
    state['mode'] = 'partial-fail'
    assert cache() == A
    previous, _ = start_scheduler(clear_cache=False)
    wait_scheduled(0)
    logs = new_logs(previous)
    assert len(state['requests']) == 4 and cache() == '', state
    assert state['records']['one.example.com'] == B and state['records']['two.example.com'] == A, state
    assert 'HTTP 403' in logs, logs
    passed('scheduled partial failure logs HTTP 403 and leaves cache empty')
    state['mode'] = 'ok'
    state['requests'] = []
    previous = script_logs()
    wait_scheduled(1)
    assert len(state['requests']) == 4 and set(state['records'].values()) == {B}, state
    assert cache() == B
    wait_scheduled(2)
    stop_scheduler()
    logs = new_logs(previous)
    assert len(state['requests']) == 4 and cache() == B, state
    assert logs.count('Record updated:') == 2 and 'No IP change:' in logs, logs
    passed('next scheduled run retries without WAN change; successful cache skips later updates')

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
