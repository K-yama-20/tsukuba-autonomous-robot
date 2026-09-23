from setuptools import setup
from glob import glob
setup(name='gouda_sensors', version='0.1.0', packages=['gouda_sensors'],
    data_files=[('share/ament_index/resource_index/packages', ['resource/gouda_sensors']),
                ('share/gouda_sensors', ['package.xml']),
                ('share/gouda_sensors/launch', glob('launch/*.py')),
                ('share/gouda_sensors/config', glob('config/*'))],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Gouda Development Team', maintainer_email='ryoya-1@g.ecc.u-tokyo.ac.jp',
    description='Gouda development and validation', license='Apache-2.0',
    entry_points={'console_scripts': ['sensor_plane_scan = gouda_sensors.scan:main', 'cloud_monitor = gouda_sensors.monitor:main', 'configure_hesai = gouda_sensors.profiles:main']})
