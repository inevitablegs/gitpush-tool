from setuptools import setup, find_packages
from pathlib import Path

# Read long description
long_description = (Path(__file__).parent / "LONG_DESCRIPTION.md").read_text(encoding="utf-8")

setup(
    name="gitpush-tool",
    version="0.4.2",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        "console_scripts": [
            "gitpush=gitpush.cli:run",
            "gitpush-guard=gitpush.cli:run",
            "gitpush-status=gitpush.cli:run",
            "gitpush-undo=gitpush.cli:run"
        ],
    },
    author="Ganesh Sonawane",
    author_email="sonawaneganu3101@gmail.com",
    description="Supercharged Git push tool with automatic GitHub repo creation and pushing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/inevitablegs/gitpush",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    include_package_data=True,
    project_urls={
        "Documentation": "https://github.com/inevitablegs/gitpush",
        "Source": "https://github.com/inevitablegs/gitpush",
        "Tracker": "https://github.com/inevitablegs/gitpush/issues",
    },
)