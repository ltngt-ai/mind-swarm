"""
Setup script for Cyber Terminal package.
"""

from setuptools import setup, find_packages
import os

# Read README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Terminal Interaction System for AI Agents"

# Read requirements
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name="cyber-terminal",
    version="1.0.0",
    author="Manus AI",
    author_email="contact@manus.ai",
    description="Terminal Interaction System for AI Agents (Cybers)",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/manus-ai/cyber-terminal",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Shells",
        "Topic :: Terminals",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-asyncio>=0.18.0",
            "pytest-cov>=2.0",
            "black>=22.0",
            "flake8>=4.0",
            "mypy>=0.900",
        ],
        "docs": [
            "sphinx>=4.0",
            "sphinx-rtd-theme>=1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cyber-terminal=src.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="terminal, ai, agents, automation, pty, shell, interactive",
    project_urls={
        "Bug Reports": "https://github.com/manus-ai/cyber-terminal/issues",
        "Source": "https://github.com/manus-ai/cyber-terminal",
        "Documentation": "https://cyber-terminal.readthedocs.io/",
    },
)

