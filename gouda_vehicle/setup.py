from setuptools import setup
from glob import glob
setup(name='gouda_vehicle', version='0.1.0', packages=['gouda_vehicle'],
    data_files=[('share/ament_index/resource_index/packages', ['resource/gouda_vehicle']),
                ('share/gouda_vehicle', ['package.xml']),
                ('share/gouda_vehicle/launch', glob('launch/*.py')),
                ('share/gouda_vehicle/config', glob('config/*'))],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Gouda Development Team', maintainer_email='ryoya-1@g.ecc.u-tokyo.ac.jp',
    description='Gouda development and validation', license='Apache-2.0',
    entry_points={'console_scripts': ['serial_bridge_node = gouda_vehicle.bridge:main']})
