from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'carrier_control'


def asset_files(directory):
    return [path for path in glob(os.path.join(directory, '*')) if os.path.isfile(path)]

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), asset_files('config')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='shanmukha',
    maintainer_email='shanmukha@example.com',
    description='Bounded carrier control and CAM-BOT machine-tending coordination',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'dual_arm_cycle = carrier_control.dual_arm_cycle:main',
            'machine_shop_trajectory = carrier_control.machine_shop_trajectory:main',
            'machine_shop_joint_cycle = carrier_control.machine_shop_joint_cycle:main',
            'plot_machine_shop_path = carrier_control.plot_machine_shop_path:main',
            'machine_tending_coordinator = carrier_control.machine_tending_coordinator:main',
        ],
    },
)
