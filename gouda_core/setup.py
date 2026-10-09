from glob import glob
from setuptools import setup
setup(name='gouda_core', version='0.1.0', packages=['gouda_core'],
      data_files=[('share/ament_index/resource_index/packages', ['resource/gouda_core']),
                  ('share/gouda_core', ['package.xml']),
                  ('share/gouda_core/launch', glob('launch/*.py')),
                  ('share/gouda_core/web', glob('web/*'))],
      install_requires=['setuptools'], zip_safe=True,
      maintainer='Gouda Development Team', maintainer_email='ryoya-1@g.ecc.u-tokyo.ac.jp',
      description='Gouda core nodes (recorder, mode manager) of the new implementation', license='Apache-2.0',
      entry_points={'console_scripts': ['gouda_recorder = gouda_core.recorder_node:main',
                                        'gouda_mode_manager = gouda_core.mode_manager_node:main',
                                        'gouda_monitor = gouda_core.monitor_node:main',
                                        'gouda_map_creator = gouda_core.map_creator_node:main']})
