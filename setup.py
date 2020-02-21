from setuptools import setup, find_packages

setup(
    name="ts3bot",
    version="0.0.1",
    description="A TeamSpeak bot for assigning server groups based on the user's world in Guild Wars 2",
    long_description="",
    author="Yannick Linke",
    author_email="invisi@0x0f.net",
    url="https://github.com/Axforest/teamspeak_bot",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        "python-i18n==0.3.*",
        "requests==2.22.*",
        "sentry-sdk==0.14.*",
        "sqlalchemy==1.3.*",
        "alembic==1.4.*",
        "ts3==2.0.0b2",
    ],
    extras_require={
        "tests": ["requests-mock==1.7.*"],
    },
)
