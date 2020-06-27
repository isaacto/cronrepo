import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='cronrepo',
    version='0.1.0',
    author='Isaac To',
    author_email='isaac.to@gmail.com',
    description='Maintain a set of cron jobs in your code repository',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/isaacto/cronrepo',
    packages=setuptools.find_packages(),
    install_requires=[
        'calf'
    ],
    entry_points={
        "console_scripts": [
            "cronrepo=cronrepo.__main__:main",
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
    ],
)
