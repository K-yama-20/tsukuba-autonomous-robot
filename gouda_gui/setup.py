from setuptools import setup
from glob import glob
setup(name='gouda_gui', version='0.1.0', packages=['gouda_gui'],
      data_files=[('share/ament_index/resource_index/packages', ['resource/gouda_gui']),
                  ('share/gouda_gui', ['package.xml']),
                  ('share/gouda_gui/web', glob('web/*')),
                  ('share/gouda_gui/config', glob('config/*')),
                  ('share/gouda_gui/launch', glob('launch/*.py'))],
      install_requires=['setuptools'], zip_safe=True,
      maintainer='Gouda Development Team', maintainer_email='ryoya-1@g.ecc.u-tokyo.ac.jp',
      description='Mission control with persistent maps and explicit plan/start', license='Apache-2.0',
      entry_points={'console_scripts': ['mission_control = gouda_gui.node:main',
                                    'phone_gateway = gouda_gui.gateway:main']})
