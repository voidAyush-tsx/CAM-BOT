from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'carrier_description'


def asset_files(directory):
    return [path for path in glob(os.path.join(directory, '*')) if os.path.isfile(path)]

setup(
    name=package_name,
    version='0.0.1',

    packages=find_packages(exclude=['test']),

    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name]
        ),

        (
            'share/' + package_name,
            ['package.xml']
        ),

        (
            os.path.join('share', package_name, 'urdf'),
            asset_files('urdf')
        ),

        (
            os.path.join('share', package_name, 'launch'),
            asset_files('launch')
        ),

        (
            os.path.join('share', package_name, 'config'),
            asset_files('config')
        ),

        (
            os.path.join('share', package_name, 'meshes'),
            asset_files('meshes')
        ),

        (
            os.path.join('share', package_name, 'rviz'),
            asset_files('rviz')
        ),
    ],

    install_requires=['setuptools'],
    zip_safe=True,

    maintainer='shanmukha',
    maintainer_email='shanmukha@example.com',

    description='UR5 carrier with flange and visual dual-arm placeholder',

    license='Apache-2.0',

    extras_require={
        'test': [
            'pytest',
        ],
    },

    entry_points={
        'console_scripts': [
        ],
    },
)
