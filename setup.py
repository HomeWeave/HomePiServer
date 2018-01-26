try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name='weaveserver',
    version='0.8',
    author='Srivatsan Iyer',
    author_email='supersaiyanmode.rox@gmail.com',
    packages=['weaveserver'],
    license='MIT',
    description='Library to interact with Weave Server',
    long_description=open('README.md').read(),
    install_requires=[
        'weavelib',
        'eventlet',
        'flask',
        'requests[security]',
        'flask-socketio',
        'GitPython',
        'psutil',
        'redis',
    ],
    dependency_links=[
        'https://github.com/HomeWeave/WeaveLib/tarball/master#egg=weavelib-0.8'
    ],
    tests_require=[
        'pytest'
    ],
    setup_requires=[
        'pytest-runner'
    ]
)
