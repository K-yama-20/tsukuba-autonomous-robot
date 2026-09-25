"""Local GUI proxy and explicitly enabled, authenticated HTTPS field gateway."""
import argparse
import asyncio
import hmac
import ipaddress
import uuid
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
from aiohttp import web, ClientSession, ClientTimeout
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
API_PATHS = {'/api/state','/api/session','/api/stop','/api/target','/api/planning_start','/api/plan','/api/start','/api/initial_pose','/api/mapping_start','/api/mapping_stop','/api/save_map','/api/recording_config_save','/api/recording_start','/api/recording_stop','/api/mapping_settings_save','/api/load_map','/api/viewer','/api/autonomy_settings_save','/api/autonomy_start','/api/autonomy_cancel'}
STATIC_PATHS = {'/','/style.css','/app.js','/manifest.webmanifest','/icon.svg','/apple-touch-icon.png'}


def web_root():
    candidates = [ROOT.parent / 'web']
    try:
        from ament_index_python.packages import get_package_share_directory
        candidates.append(Path(get_package_share_directory('gouda_gui')) / 'web')
    except Exception:
        pass
    return next((path for path in candidates if path.is_dir()), candidates[0])


async def startup(app):
    app['client'] = ClientSession(timeout=ClientTimeout(total=30), auto_decompress=False)
    if app['ssh_runtime'] is None:
        return
    runtime = Path(app['ssh_runtime']); c = json.loads((runtime/'connection.json').read_text())
    args = ['ssh','-N','-i',str(runtime/'id_ed25519'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(runtime/'known_hosts'),'-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=3','-L','127.0.0.1:18765:127.0.0.1:8765',c['user']+'@'+c['host']]
    with socket.socket() as probe:
        probe.settimeout(.2)
        if probe.connect_ex(('127.0.0.1',18765)) == 0:
            raise RuntimeError('Tunnel port 18765 is already in use')
    app['tunnel'] = {'args':args,'process':subprocess.Popen(args)}
    for _ in range(80):
        if app['tunnel']['process'].poll() is not None: raise RuntimeError('SSH tunnel failed')
        try:
            _, writer = await asyncio.open_connection('127.0.0.1',18765); writer.close(); await writer.wait_closed(); break
        except OSError: await asyncio.sleep(.1)
    else: raise RuntimeError('SSH tunnel did not become ready')
    app['watchdog'] = asyncio.create_task(watch_tunnel(app))


async def watch_tunnel(app):
    while True:
        await asyncio.sleep(2)
        if app['tunnel']['process'].poll() is not None:
            app['tunnel']['process'] = subprocess.Popen(app['tunnel']['args'])


async def cleanup(app):
    if app.get('watchdog'):
        app['watchdog'].cancel(); await asyncio.gather(app['watchdog'], return_exceptions=True)
    if app.get('client'): await app['client'].close()
    p = app.get('tunnel',{}).get('process')
    if p and p.poll() is None:
        p.terminate()
        try: p.wait(timeout=5)
        except subprocess.TimeoutExpired: p.kill(); p.wait()


def remote_request(request):
    sock = request.transport.get_extra_info('sockname') if request.transport else None
    return bool(sock and sock[1] == request.app['remote_port'])


def valid_host(request):
    host = request.headers.get('Host','')
    if not host or any(c in host for c in '\r\n/@\\ '): return False
    try: parsed = urlsplit('//'+host)
    except ValueError: return False
    name = (parsed.hostname or '').lower().rstrip('.')
    try:
        if parsed.port != request.app['remote_port']: return False
    except ValueError: return False
    if not name: return False
    if name in request.app['allowed_hosts']: return True
    if request.app['allow_private_hosts']:
        try: return ipaddress.ip_address(name).is_private
        except ValueError: return False
    return False


def authorized(request):
    expected = request.app['remote_token']
    provided = request.headers.get('Authorization','')
    return bool(expected and provided.startswith('Bearer ') and hmac.compare_digest(provided[7:].encode('utf-8','ignore'), expected.encode('utf-8')))


async def handler(request):
    remote = remote_request(request)
    if remote and not valid_host(request): raise web.HTTPForbidden()
    if request.method not in ('GET','POST'): raise web.HTTPMethodNotAllowed(request.method,['GET','POST'])
    if remote:
        origin = request.headers.get('Origin')
        if origin and origin != f"https://{request.headers['Host']}": raise web.HTTPForbidden(text='Origin mismatch')
        if request.path in STATIC_PATHS:
            if request.method != 'GET': raise web.HTTPMethodNotAllowed(request.method,['GET'])
            names = {'/':'index.html','/style.css':'style.css','/app.js':'app.js','/manifest.webmanifest':'manifest.webmanifest','/icon.svg':'icon.svg','/apple-touch-icon.png':'apple-touch-icon.png'}
            mimetypes = {'/':'text/html; charset=utf-8','/style.css':'text/css; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/manifest.webmanifest':'application/manifest+json','/icon.svg':'image/svg+xml','/apple-touch-icon.png':'image/png'}
            path = request.app['web_root'] / names[request.path]
            if not path.is_file(): raise web.HTTPNotFound()
            return web.Response(body=path.read_bytes(),content_type=mimetypes[request.path].split(';')[0],charset='utf-8' if 'charset=' in mimetypes[request.path] else None,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        if request.path == '/api/access' and request.method == 'POST':
            try: body = await request.json()
            except Exception: raise web.HTTPBadRequest(text='Invalid JSON')
            if not isinstance(body,dict) or not hmac.compare_digest(str(body.get('token','')).encode('utf-8','ignore'),request.app['remote_token'].encode('utf-8')): raise web.HTTPUnauthorized(text='アクセスキーを確認してください')
            return web.json_response({'ok':True},headers={'Cache-Control':'no-store'})
        if not authorized(request): raise web.HTTPUnauthorized(text='アクセスキーを入力してください',headers={'Cache-Control':'no-store'})
        if request.path.startswith('/api/runtime/'):
            adapter = request.app.get('runtime_adapter')
            if adapter is None: raise web.HTTPServiceUnavailable(text='Runtime control is not configured')
            if request.path == '/api/runtime/status' and request.method == 'GET':
                status = await asyncio.to_thread(adapter.runtime_status)
                jobs = request.app['runtime_jobs']
                recent = next(reversed(jobs.values()), None) if jobs else None
                if recent: status['lifecycle_job'] = {k:v for k,v in recent.items() if k not in {'task','result','error'}} | {k:recent[k] for k in ('result','error') if k in recent}
                return web.json_response(status,headers={'Cache-Control':'no-store'})
            if request.path == '/api/runtime/action' and request.method == 'POST':
                try: payload = await request.json()
                except Exception: raise web.HTTPBadRequest(text='Invalid JSON')
                if not isinstance(payload,dict) or set(payload)-{'action','profile'}: raise web.HTTPBadRequest(text='Invalid lifecycle request')
                if payload.get('action') not in {'start_observe','start_autonomy','stop','restart','apply_config'}: raise web.HTTPBadRequest(text='Unknown lifecycle action')
                if any(job.get('state') in ('accepted','running') for job in request.app['runtime_jobs'].values()):
                    raise web.HTTPConflict(text='PC lifecycle operation is already in progress')
                job_id = uuid.uuid4().hex
                job = {'job_id':job_id,'state':'accepted','action':payload['action'],'accepted_at':asyncio.get_running_loop().time()}
                request.app['runtime_jobs'][job_id] = job
                async def run_job():
                    job['state']='running'
                    try:
                        result=await asyncio.to_thread(adapter.runtime_action,payload)
                        job['result']=result;job['state']='completed'
                    except Exception as exc:
                        job['error']=str(exc);job['state']='failed'
                job['task']=asyncio.create_task(run_job())
                while len(request.app['runtime_jobs'])>32:
                    old_id,old=request.app['runtime_jobs'].popitem(last=False)
                    if old['state'] in ('accepted','running'): request.app['runtime_jobs'][old_id]=old; break
                return web.json_response({'ok':True,'job_id':job_id,'state':'accepted'},status=202,headers={'Cache-Control':'no-store'})
            raise web.HTTPNotFound()
        if request.path not in API_PATHS: raise web.HTTPNotFound()
        if request.method == 'POST' and request.path not in {'/api/stop','/api/autonomy_cancel'}:
            lifecycle_busy=any(job.get('state') in ('accepted','running') for job in request.app['runtime_jobs'].values())
            if not lifecycle_busy and request.app.get('runtime_adapter') is not None:
                lifecycle_busy=bool((await asyncio.to_thread(request.app['runtime_adapter'].runtime_status)).get('lifecycle_busy'))
            if lifecycle_busy: raise web.HTTPConflict(text='PC lifecycle operation is in progress')
    else:
        if request.host not in ('127.0.0.1:8766','localhost:8766'): raise web.HTTPForbidden()
        if request.path in {'/manifest.webmanifest','/icon.svg','/apple-touch-icon.png'} and request.method=='GET':
            ext='manifest.webmanifest' if request.path.startswith('/manifest') else ('apple-touch-icon.png' if request.path.endswith('.png') else 'icon.svg')
            kind='application/manifest+json' if ext.startswith('manifest') else ('image/png' if ext.endswith('.png') else 'image/svg+xml')
            return web.Response(body=(request.app['web_root']/ext).read_bytes(),content_type=kind,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        origin=request.headers.get('Origin')
        if origin and origin != 'http://' + request.host: raise web.HTTPForbidden()
        if request.path not in STATIC_PATHS | API_PATHS: raise web.HTTPNotFound()
    url = request.app['api_url'] + request.rel_url.path_qs
    body = await request.read()
    headers = {k:request.headers[k] for k in ('X-Gouda-Session','Content-Type') if k in request.headers}
    try:
        async with request.app['client'].request(request.method,url,data=body if request.method=='POST' else None,headers=headers,timeout=ClientTimeout(total=60 if request.path=='/api/plan' else 30)) as response:
            data=await response.read()
            out={k:response.headers[k] for k in ('Content-Type','Content-Encoding','Cache-Control','X-Content-Type-Options','Content-Security-Policy') if k in response.headers}
            out['Cache-Control']='no-store'
            return web.Response(status=response.status,body=data,headers=out)
    except (OSError,asyncio.TimeoutError): raise web.HTTPBadGateway(text='Backend unavailable')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ssh-runtime')
    parser.add_argument('--remote-only',action='store_true',help='Bind only the authenticated HTTPS field listener')
    parser.add_argument('--remote-bind',default='127.0.0.1')
    parser.add_argument('--remote-port',type=int,default=8443)
    parser.add_argument('--tls-cert')
    parser.add_argument('--tls-key')
    parser.add_argument('--remote-token-file')
    parser.add_argument('--allowed-host',action='append',default=[],help='Exact HTTPS Host name or IP accepted by the field listener')
    parser.add_argument('--allow-private-hosts',action='store_true',help='Allow private IP Host values for tethered/AP addresses')
    args=parser.parse_args()
    remote_enabled=bool(args.remote_token_file or args.tls_cert or args.tls_key or args.remote_only)
    if remote_enabled and not (args.remote_token_file and args.tls_cert and args.tls_key): parser.error('remote access requires --remote-token-file, --tls-cert and --tls-key')
    if remote_enabled and not (args.allowed_host or args.allow_private_hosts): parser.error('remote access requires --allowed-host or --allow-private-hosts')
    if remote_enabled and args.remote_port == 8766 and not args.remote_only: parser.error('remote port must differ from local port 8766')
    token=''
    if remote_enabled:
        token=Path(args.remote_token_file).read_text().strip()
        if len(token)<32: parser.error('remote token must contain at least 32 characters')
    app=web.Application(client_max_size=16384)
    app['ssh_runtime']=args.ssh_runtime
    app['api_url']='http://127.0.0.1:'+('18765' if args.ssh_runtime else '8765')
    app['remote_port']=args.remote_port if remote_enabled else -1
    app['remote_token']=token
    app['allowed_hosts']={value.lower().rstrip('.') for value in args.allowed_host}
    app['allow_private_hosts']=args.allow_private_hosts
    app['web_root']=web_root()
    app['runtime_jobs']=__import__('collections').OrderedDict()
    app['runtime_adapter']=None
    if remote_enabled:
        from . import runtime as runtime_module
        app['runtime_adapter']=runtime_module
    app.router.add_route('*','/{path:.*}',handler)
    app.on_startup.append(startup); app.on_cleanup.append(cleanup)
    async def serve():
        runner=web.AppRunner(app,shutdown_timeout=3); await runner.setup()
        sites=[]
        if not args.remote_only: sites.append(web.TCPSite(runner,'127.0.0.1',8766))
        if remote_enabled:
            context=ssl.create_default_context(ssl.Purpose.CLIENT_AUTH); context.load_cert_chain(args.tls_cert,args.tls_key)
            sites.append(web.TCPSite(runner,args.remote_bind,args.remote_port,ssl_context=context))
        for site in sites: await site.start()
        try: await asyncio.Event().wait()
        finally: await runner.cleanup()
    asyncio.run(serve())

if __name__=='__main__': main()
