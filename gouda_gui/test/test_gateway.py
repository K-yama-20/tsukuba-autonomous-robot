from types import SimpleNamespace

from gouda_gui.gateway import authorized, valid_host


def request(host, *, allow_private=False, allowed_hosts=(), token='a'*40, authorization=''):
    return SimpleNamespace(headers={'Host': host, 'Authorization': authorization}, app={
        'remote_port': 8443, 'allow_private_hosts': allow_private,
        'allowed_hosts': set(allowed_hosts), 'remote_token': token,
    })


def test_remote_host_must_be_private_or_explicit_and_match_listener_port():
    req=request('192.168.1.4:8443',allow_private=True)
    assert valid_host(req)
    assert not valid_host(request('8.8.8.8:8443',allow_private=True))
    assert valid_host(request('control.example:8443',allowed_hosts=('control.example',)))
    assert not valid_host(request('control.example:8444',allowed_hosts=('control.example',)))
    assert not valid_host(request('attacker.example:8443',allowed_hosts=('control.example',)))


def test_bearer_key_is_checked_without_unicode_comparison_errors():
    expected='correct horse battery staple 1234567890'
    assert authorized(request('192.168.1.4:8443',token=expected,authorization='Bearer '+expected))
    assert not authorized(request('192.168.1.4:8443',token=expected,authorization='Bearer ☃'))
    assert not authorized(request('192.168.1.4:8443',token=expected))


import asyncio
import json
import threading
import unittest
from collections import OrderedDict
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from gouda_gui.gateway import cleanup, handler, startup


class RuntimeStub:
    def __init__(self):
        self.entered=threading.Event()
        self.release=threading.Event()
        self.calls=[]
    def runtime_status(self):
        return {'mode':'stopped','lifecycle_busy':any(job.get('state') in ('accepted','running') for job in jobs.values())}
    def runtime_action(self,payload):
        self.calls.append(payload)
        self.entered.set()
        self.release.wait(1)
        return {'ok':True,'action':payload['action']}


class GatewayHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.forwarded=[]
        async def backend(request):
            self.forwarded.append((request.method,request.path,dict(request.headers)))
            return web.json_response({'ok':True,'token':'session-token'})
        backend_app=web.Application();backend_app.router.add_route('*','/{tail:.*}',backend)
        self.backend=TestServer(backend_app);await self.backend.start_server()
        self.runtime=RuntimeStub()
        global jobs
        jobs=OrderedDict()
        app=web.Application(client_max_size=16384)
        app['ssh_runtime']=None;app['api_url']=str(self.backend.make_url('/')).rstrip('/')
        app['remote_port']=0;app['remote_token']='t'*40;app['allowed_hosts']=set();app['allow_private_hosts']=True
        app['web_root']=Path(__file__).parents[1]/'web';app['runtime_jobs']=jobs;app['runtime_adapter']=self.runtime
        app.router.add_route('*','/{path:.*}',handler);app.on_startup.append(startup);app.on_cleanup.append(cleanup)
        self.gateway=TestServer(app);await self.gateway.start_server();app['remote_port']=self.gateway.port
        self.client=TestClient(self.gateway);await self.client.start_server()
        self.host=f'127.0.0.1:{self.gateway.port}'
        self.headers={'Authorization':'Bearer '+'t'*40,'Origin':'https://'+self.host}

    async def asyncTearDown(self):
        self.runtime.release.set()
        await self.client.close();await self.backend.close()

    async def test_unauthenticated_api_is_rejected_before_backend(self):
        response=await self.client.get('/api/state',headers={'Host':self.host})
        self.assertEqual(response.status,401)
        self.assertEqual(self.forwarded,[])

    async def test_cross_origin_mutation_is_rejected(self):
        headers={**self.headers,'Origin':'https://attacker.example'}
        response=await self.client.post('/api/stop',headers=headers,json={},)
        self.assertEqual(response.status,403)
        self.assertEqual(self.forwarded,[])

    async def test_valid_session_is_forwarded_without_remote_bearer(self):
        response=await self.client.post('/api/stop',headers={**self.headers,'X-Gouda-Session':'gui-session'},json={})
        self.assertEqual(response.status,200)
        self.assertEqual(len(self.forwarded),1)
        forwarded=self.forwarded[0][2]
        self.assertEqual(forwarded.get('X-Gouda-Session'),'gui-session')
        self.assertNotIn('Authorization',forwarded)

    async def test_static_login_page_is_available_when_backend_is_down(self):
        await self.backend.close()
        response=await self.client.get('/',headers={'Host':self.host})
        self.assertEqual(response.status,200)
        self.assertIn('Mission Control'.encode(),await response.read())
        icon=await self.client.get('/apple-touch-icon.png',headers={'Host':self.host})
        self.assertEqual(icon.status,200)
        self.assertEqual(icon.headers.get('Content-Type'),'image/png')

    async def test_runtime_job_is_accepted_and_mutations_are_locked(self):
        response=await self.client.post('/api/runtime/action',headers=self.headers,json={'action':'start_observe'})
        self.assertEqual(response.status,202)
        body=await response.json();self.assertTrue(body['job_id'])
        self.assertTrue(await asyncio.to_thread(self.runtime.entered.wait,1))
        duplicate=await self.client.post('/api/runtime/action',headers=self.headers,json={'action':'stop'})
        self.assertEqual(duplicate.status,409)
        conflict=await self.client.post('/api/recording_start',headers={**self.headers,'X-Gouda-Session':'gui-session'},json={})
        self.assertEqual(conflict.status,409)
        bad=await self.client.post('/api/runtime/action',headers=self.headers,json={'action':'run_shell'})
        self.assertEqual(bad.status,400)
        self.runtime.release.set()
        await asyncio.sleep(.05)
        status=await self.client.get('/api/runtime/status',headers=self.headers)
        result=await status.json()
        self.assertEqual(result['lifecycle_job']['state'],'completed')

