from setuptools import setup

package_name = 'talos_core'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'openai', 'pyyaml'],
    zip_safe=True,
    maintainer='Jiyoon Kim',
    maintainer_email='jiyoonkim@example.com',
    description='Core logic for TALOS disaster search robot',
    license='MIT',
    entry_points={
        'console_scripts': [
            'mission_node = talos_core.mission_node:main',
        ],
    },
)
