from setuptools import setup, find_packages

setup(
    name='weaveserver',
    version='0.8',
    author='Srivatsan Iyer',
    author_email='supersaiyanmode.rox@gmail.com',
    packages=find_packages(),
    license='MIT',
    description='Library to interact with Weave Server',
    long_description=open('README.md').read(),
    install_requires=[
        'weavelib',
        'eventlet!=0.22',
        'bottle',
        'GitPython',
        'redis',
    ],
    entry_points={
        'console_scripts': [
            'weave-launch = app:handle_launch',
            'weave-main = app:handle_main'
        ]
    }
)
