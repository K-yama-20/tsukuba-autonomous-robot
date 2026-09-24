"""Local API/RViz gateway with optional pinned SSH transport for Mac clients."""
import asyncio
import json
from pathlib import Path
import subprocess
import socket
from urllib.parse import urlsplit
from aiohttp import web, ClientSession, ClientTimeout

import argparse
ROOT=Path(__file__).resolve().parent
ALLOWED={'/','/style.css','/app.js','/api/state','/api/session','/api/stop',
         '/api/target','/api/planning_start','/api/plan','/api/start','/api/initial_pose','/api/mapping_start',
         '/api/mapping_stop','/api/save_map','/api/recording_config_save','/api/recording_start','/api/recording_stop','/api/mapping_settings_save','/api/load_map','/api/viewer'}


def allowed_path(path):
    return path in ALLOWED


async def startup(app):
    if app['ssh_runtime'] is None:
        app['client']=ClientSession(timeout=ClientTimeout(total=30),auto_decompress=False)
        return
    runtime=Path(app['ssh_runtime']); c=json.loads((runtime/'connection.json').read_text())
    # Let SSH reject occupied ports. Never adopt an unrelated listener.
    args=['ssh','-N','-i',str(runtime/'id_ed25519'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
          '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(runtime/'known_hosts'),
          '-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=3',
          '-L','127.0.0.1:18765:127.0.0.1:8765',c['user']+'@'+c['host']]
    for port in (18765,):
        with socket.socket() as probe:
            probe.settimeout(.2)
            if probe.connect_ex(('127.0.0.1',port))==0:
                raise RuntimeError(f'Tunnel port {port} is already in use')
    app['tunnel']={'args':args,'process':subprocess.Popen(args)}
    await asyncio.sleep(.2)
    for _ in range(80):
        if app['tunnel']['process'].poll() is not None:raise RuntimeError('SSH tunnel failed')
        try:
            reader,writer=await asyncio.open_connection('127.0.0.1',18765)
            writer.close();await writer.wait_closed();break
        except OSError:await asyncio.sleep(.1)
    else:raise RuntimeError('SSH tunnel did not become ready')
    app['client']=ClientSession(timeout=ClientTimeout(total=30),auto_decompress=False)
    app['watchdog']=asyncio.create_task(watch_tunnel(app))


async def watch_tunnel(app):
    while True:
        await asyncio.sleep(2)
        if app['tunnel']['process'].poll() is not None:
            # The same pinned host and key are reused; only the owned tunnel restarts.
            app['tunnel']['process']=subprocess.Popen(app['tunnel']['args'])


async def cleanup(app):
    if app.get('watchdog'):
        app['watchdog'].cancel()
        await asyncio.gather(app['watchdog'],return_exceptions=True)
    if app.get('client'):await app['client'].close()
    p=app.get('tunnel',{}).get('process')
    if p and p.poll() is None:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait()


async def proxy(request):
    if request.host not in ('127.0.0.1:8766','localhost:8766'):raise web.HTTPForbidden()
    origin=request.headers.get('Origin')
    if origin and origin!='http://'+request.host:raise web.HTTPForbidden()
    if not allowed_path(request.path):raise web.HTTPNotFound()
    if request.method not in ('GET','POST'):raise web.HTTPMethodNotAllowed(request.method,['GET','POST'])
    url=request.app['api_url']+request.rel_url.path_qs
    client=request.app['client']
    body=await request.read()
    headers={k:request.headers[k] for k in ('X-Gouda-Session','Content-Type') if k in request.headers}
    try:
        async with client.request(request.method,url,data=body if request.method=='POST' else None,headers=headers,
                                 timeout=ClientTimeout(total=60 if request.path=='/api/plan' else 30)) as response:
            data=await response.read()
            out={k:response.headers[k] for k in ('Content-Type','Content-Encoding','Cache-Control','X-Content-Type-Options','Content-Security-Policy') if k in response.headers}
            return web.Response(status=response.status,body=data,headers=out)
    except (OSError,asyncio.TimeoutError):raise web.HTTPBadGateway(text='Backend unavailable')



def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ssh-runtime',help='Existing Mac SSH runtime with connection.json, key and known_hosts')
    args=parser.parse_args()
    app=web.Application(client_max_size=16384)
    app['ssh_runtime']=args.ssh_runtime
    app['api_url']='http://127.0.0.1:'+('18765' if args.ssh_runtime else '8765')
    app.router.add_route('*','/{path:.*}',proxy)
    app.on_startup.append(startup);app.on_cleanup.append(cleanup)
    web.run_app(app,host='127.0.0.1',port=8766,shutdown_timeout=3)

if __name__=='__main__':main()
