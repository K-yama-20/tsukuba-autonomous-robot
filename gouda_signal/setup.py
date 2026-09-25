from setuptools import setup

package_name = "gouda_signal"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "model_manifest.json"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Gouda Development Team",
    maintainer_email="ryoya-1@g.ecc.u-tokyo.ac.jp",
    description="Manual-ROI pedestrian signal color observation desktop application",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "pedestrian_signal = gouda_signal.bootstrap:main",
        ],
    },
)
