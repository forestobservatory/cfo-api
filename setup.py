from setuptools import find_packages, setup

version = open("cfo/__version__.py").read().strip('"\n')
long_description = open("README.md", "r", encoding="utf-8").read()

setup(
    name="cfo",
    url="https://github.com/forestobservatory/cfo-api",
    license="MIT",
    description="Python wrappers for accessing Forest Observatory data via the Salo API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords=[
        "ecology",
        "conservation",
        "remote sensing",
        "wildfire",
        "california",
    ],
    packages=find_packages(exclude="tests"),
    version=version,
    python_requires=">=3.0",
    platforms="any",
    install_requires=["requests", "retrying"],
    author="Salo Sciences",
    author_email="cba@salo.ai",
    include_package_data=True,
    package_data={"cfo": ["data/paths.json", "data/public.json"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
