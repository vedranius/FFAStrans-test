from setuptools import setup, find_packages

setup(
    name="ffastrans-linux-mimo",
    version="2.0.0",
    description="FFAStrans Linux Mimo - Free Workflow and Transcoding System for Linux",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="FFAStrans Linux Mimo Contributors",
    url="https://github.com/vedranius/FFAStrans-refactor_linux_mimo",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "ffastrans": ["gui/templates/*", "gui/static/**/*", "presets/*"],
    },
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.34.0",
        "pydantic>=2.10.0",
        "python-multipart>=0.0.19",
        "aiofiles>=24.1.0",
    ],
    entry_points={
        "console_scripts": [
            "ffastrans=ffastrans.main:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Video",
        "Operating System :: POSIX :: Linux",
    ],
)
