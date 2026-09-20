"""Setup script for RAPO package."""

import rapo
import setuptools


name = rapo.__name__
version = rapo.__version__
author = rapo.__author__
author_email = rapo.__email__
description = rapo.__doc__
license = rapo.__license__
python_requires = '>=3.10'
install_requires = open('requirements.txt').read().splitlines()
packages = setuptools.find_packages()
package_data = {
    'rapo': [
        'web/api/templates/*',
        'web/ui/**/*',
        'algorithms/**/*'
    ]
}
entry_points = {
    'console_scripts': [
        'rapo-scheduler=rapo.cli:run_scheduler',
        'rapo-server=rapo.cli:run_server',
    ],
}


setuptools.setup(name=name,
                 version=version,
                 author=author,
                 author_email=author_email,
                 description=description,
                 license=license,
                 python_requires=python_requires,
                 install_requires=install_requires,
                 packages=packages,
                 package_data=package_data,
                 entry_points=entry_points)
