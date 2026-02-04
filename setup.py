"""Create the protohaven_api module"""

from setuptools import find_packages, setup

with open("requirements.txt", encoding="utf-8") as f:
    install_requires = [
        line.strip() for line in f if line.strip() and not line.startswith("#")
    ]

setup(
    name="protohaven_api",
    version="0.1.0",
    packages=find_packages(),
    install_requires=install_requires,
)
