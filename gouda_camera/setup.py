from glob import glob
from setuptools import setup


setup(
    name="gouda_camera",
    version="0.1.0",
    packages=["gouda_camera"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/gouda_camera"]),
        ("share/gouda_camera", ["package.xml"]),
        ("share/gouda_camera/launch", glob("launch/*.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Gouda Development Team",
    maintainer_email="ryoya-1@g.ecc.u-tokyo.ac.jp",
    description="Network camera input for Gouda observation and perception",
    license="Apache-2.0",
)
