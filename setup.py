import setuptools

try:
    long_desc = open("README.rst").read()
except IOError:
    long_desc = "Failed to read README.rst"

setuptools.setup(
    name="fbchat-asyncio",
    version="0.3.0",
    url="https://github.com/tulir/fbchat-asyncio",

    author="Tulir Asokan",
    author_email="tulir@maunium.net",

    description="Facebook Messenger library for Python/Asyncio.",
    long_description=long_desc,

    packages=setuptools.find_packages(),

    install_requires=[
        "aenum",
        "attrs",
        "beautifulsoup4",
        "aiohttp",
        "yarl",
        "tulir-hbmqtt>=0.9.6.dev20191123131128",
    ],

    python_requires="~=3.6",

    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Natural Language :: English",
        "Topic :: Communications :: Chat",
        "Framework :: AsyncIO",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
