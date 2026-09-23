"""Render upstream KISS RViz in a dedicated X server and carry lossless RFB.

Owns only its display processes. Never starts/stops sensors or vehicle nodes.
"""
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

from aiohttp import web, WSMsgType
from .paths import data_dir
from ament_index_python.packages import get_package_share_directory
import rclpy
from sensor_msgs.msg import PointCloud2
from rclpy.qos import qos_profile_sensor_data


class NativeView:
    def __init__(self):
        self.children=[]; self.received={}; self.started=time.monotonic()
        self.root=data_dir()/'logs/native_view'
        self.root.mkdir(parents=True,exist_ok=True)
        self.env=dict(os.environ,DISPLAY=':97',QT_QPA_PLATFORM='xcb',LIBGL_ALWAYS_SOFTWARE='1',LP_NUM_THREADS='1',MESA_GLTHREAD='false')
        self.node=rclpy.create_node('gouda_native_view_health')
        for topic in ('/lidar_points','/kiss/frame','/kiss/local_map'):
            self.node.create_subscription(PointCloud2,topic,lambda _,t=topic:self.received.__setitem__(t,time.monotonic()),qos_profile_sensor_data)
        self.thread=threading.Thread(target=rclpy.spin,args=(self.node,),daemon=True); self.thread.start()

    def spawn(self,name,args):
        log=(self.root/(name+'.log')).open('a')
        p=subprocess.Popen(args,env=self.env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        log.close();self.children.append((name,p));return p

    async def start(self,app):
        if Path('/tmp/.X97-lock').exists():raise RuntimeError('Dedicated display :97 is already occupied')
        self.spawn('xvfb',['Xvfb',':97','-screen','0','1280x720x24','-nolisten','tcp','-ac'])
        for _ in range(100):
            if Path('/tmp/.X11-unix/X97').exists():break
            await asyncio.sleep(.05)
        else:raise RuntimeError('Xvfb did not start')
        self.spawn('openbox',['openbox','--sm-disable'])
        config=Path(get_package_share_directory('kiss_icp'))/'rviz/kiss_icp.rviz'
        # The upstream configuration remains byte-for-byte untouched.
        self.spawn('rviz',['/opt/ros/jazzy/lib/rviz2/rviz2','-d',str(config),'--ros-args',
                           '-r','/initialpose:=/gouda/viewer/initialpose_unused',
                           '-r','/goal_pose:=/gouda/viewer/goal_unused'])
        self.spawn('vnc',['x11vnc','-display',':97','-localhost','-rfbport','5907','-forever','-shared',
                          '-nopw','-noxdamage','-noscr','-nowf','-wait','50','-defer','20'])
        app['maximize']=asyncio.create_task(self.maximize())

    async def maximize(self):
        for _ in range(100):
            p=await asyncio.create_subprocess_exec('wmctrl','-l',env=self.env,stdout=asyncio.subprocess.PIPE)
            data,_=await p.communicate()
            lines=[line for line in data.decode().splitlines() if 'rviz' in line.lower()]
            if lines:
                p=await asyncio.create_subprocess_exec('wmctrl','-ir',lines[0].split()[0],'-b','add,maximized_vert,maximized_horz',env=self.env)
                await p.wait();return
            await asyncio.sleep(.2)

    async def status(self,request):
        now=time.monotonic(); processes={name:p.poll() is None for name,p in self.children}
        ages={t:round(now-v,3) for t,v in self.received.items()}
        healthy=all(processes.values()) and len(processes)==4
        fresh=all(ages.get(t,999)<2 for t in ('/kiss/frame','/kiss/local_map'))
        return web.json_response(dict(available=healthy,fresh=fresh,processes=processes,ages=ages,
                                      renderer='KISS-ICP / RViz2',lossless=True,resolution=[1280,720]))

    async def websocket(self,request):
        if request.headers.get('Origin') and request.headers['Origin']!='http://'+request.host:
            raise web.HTTPForbidden()
        try:reader,writer=await asyncio.open_connection('127.0.0.1',5907)
        except OSError:raise web.HTTPServiceUnavailable(text='RViz display unavailable')
        ws=web.WebSocketResponse(max_msg_size=8*1024*1024,heartbeat=20)
        await ws.prepare(request)
        async def upstream():
            async for msg in ws:
                if msg.type==WSMsgType.BINARY:writer.write(msg.data);await writer.drain()
                elif msg.type in (WSMsgType.ERROR,WSMsgType.CLOSE):break
        async def downstream():
            while data:=await reader.read(262144):await ws.send_bytes(data)
        tasks=[asyncio.create_task(upstream()),asyncio.create_task(downstream())]
        try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:t.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            writer.close();await writer.wait_closed();await ws.close()
        return ws

    async def close(self,app):
        if app.get('maximize'):app['maximize'].cancel()
        for _,p in reversed(self.children):
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
        for _,p in reversed(self.children):
            try:p.wait(timeout=4)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        if rclpy.ok():rclpy.shutdown()
        self.thread.join(timeout=2);self.node.destroy_node()


def main():
    rclpy.init();viewer=NativeView();app=web.Application()
    app.router.add_get('/native/status',viewer.status)
    app.router.add_get('/native/ws',viewer.websocket)
    app.router.add_static('/native/vendor/', '/usr/share/novnc',follow_symlinks=False)
    app.on_startup.append(viewer.start);app.on_cleanup.append(viewer.close)
    web.run_app(app,host='127.0.0.1',port=6080,print=None)
