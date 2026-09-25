import copy
from unittest.mock import patch
import pytest
import rclpy
from gouda_navigation import autonomy_mvp as m
from gouda_navigation.autonomy_core import DEFAULT_SETTINGS

@pytest.mark.parametrize('domain,clock,hardware,fixture',[
    ('99',True,False,True),('101',False,False,True),('101',True,True,True),('101',True,False,False)])
def test_simulation_cannot_share_hardware_profile(monkeypatch,domain,clock,hardware,fixture):
    monkeypatch.setenv('ROS_DOMAIN_ID',domain)
    cfg=copy.deepcopy(DEFAULT_SETTINGS);cfg.update(hardware_enabled=hardware,simulation_fixture=fixture)
    rclpy.init(args=['--ros-args','-p','gazebo_simulation:=true','-p',f'use_sim_time:={str(clock).lower()}'])
    try:
        with patch.object(m,'load_autonomy_settings',return_value=cfg):
            with pytest.raises(RuntimeError,match='Gazebo requires'):m.AutonomyMVP()
    finally:rclpy.shutdown()
