from setuptools import find_packages, setup

version = open("cfo/__version__.py").read().strip('"\n')

setup(
    name="cfo",
    description="Python wrappers and a command line executable for accessing Forest Observatory data via the Salo API",
    packages=find_packages(),
    version=version,
    python_requires=">=3.0",
    install_requires=["requests", "retrying"],
    author="Salo Sciences",
    include_package_data=True,
    package_data={"cfo": ["data/paths.json", "data/public.json"]},
)
