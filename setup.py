from setuptools import setup, find_packages

AIIDALAB = ["aiidalab-widgets-base~=1.0.0b2"]
TESTING = ["pytest", "pytest-cov", "codecov"]
DEV = ["pylint", "black", "pre-commit", "invoke"] + TESTING

setup(
    name="aiidalab-optimade",
    version="3.0.0",
    packages=find_packages(),
    license="MIT Licence",
    author="The AiiDA Lab team",
    python_requires=">=3.6",
    install_requires=[
        "optimade~=0.7",
        "requests~=2.23",
        "jupyterlab~=2.0",
        "ipywidgets~=7.5",
        "nglview~=2.7",
        "numpy~=1.18",
        "pandas~=1.0",
    ],
    extras_require={"aiidalab": AIIDALAB, "dev": DEV, "testing": TESTING},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: AiiDA",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Database :: Front-Ends",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Scientific/Engineering :: Physics",
    ],
)
