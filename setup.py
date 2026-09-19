"""Setup script for RAPO package."""

import rapo
import setuptools


name = rapo.__name__
version = rapo.__version__
author = rapo.__author__
author_email = rapo.__email__
description = rapo.__doc__
long_description = open('README.md', 'r').read()
long_description_content_type = 'text/markdown'
license = rapo.__license__
url = f'https://github.com/t3eHawk/{name}'
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
classifiers = [
    'Programming Language :: Python :: 3.10',
    'Programming Language :: Python :: 3.11',
    'Programming Language :: Python :: 3.12',
    'License :: OSI Approved :: MIT License',
    'Operating System :: OS Independent'
]
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
                 long_description=long_description,
                 long_description_content_type=long_description_content_type,
                 license=license,
                 url=url,
                 python_requires=python_requires,
                 install_requires=install_requires,
                 packages=packages,
                 package_data=package_data,
                 classifiers=classifiers,
                 entry_points=entry_points)
