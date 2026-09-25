from setuptools import setup
from glob import glob
setup(name='gouda_navigation', version='0.1.0', packages=['gouda_navigation'],
    data_files=[('share/ament_index/resource_index/packages', ['resource/gouda_navigation']),
                ('share/gouda_navigation', ['package.xml']),
                ('share/gouda_navigation/launch', glob('launch/*.py')),
                ('share/gouda_navigation/config', glob('config/*'))],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='Gouda Development Team', maintainer_email='ryoya-1@g.ecc.u-tokyo.ac.jp',
    description='Gouda development and validation', license='Apache-2.0',
    entry_points={'console_scripts': ['autonomy_mvp = gouda_navigation.autonomy_mvp:main', 'follower = gouda_navigation.node:main', 'glim_odom_tf = gouda_navigation.glim_odom_tf:main']})
