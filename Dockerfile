FROM docker.io/python:3.11-slim as python-base

LABEL maintainer="Yannick Linke <invisi@0x0f.net>"

# Based on https://github.com/python-poetry/poetry/discussions/1879#discussioncomment-216865

ENV PYTHONUNBUFFERED=1 \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=1.5.1 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # make poetry create the virtual environment in the project's root
    # it gets named `.venv`
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# `builder-base` stage is used to build deps + create our virtual environment
FROM python-base as builder
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        # deps for installing poetry
        curl \
        # deps for building python deps
        build-essential \
        git \
        # Required for mysqlclient \
        pkg-config \
        libmariadb-dev

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
RUN curl -sSL https://install.python-poetry.org/ | python

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
COPY poetry.lock pyproject.toml ./

# install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
# Modify this line to add extra dependencies
RUN poetry install --only main

# `production` image used for runtime
FROM python-base as production

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -yq --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder $PYSETUP_PATH $PYSETUP_PATH

# App's env
ENV RUNNING_IN_DOCKER=true

WORKDIR /app

COPY ./ts3bot /app/ts3bot
COPY ./alembic.ini /app/

CMD [ "python", "-m", "ts3bot", "bot" ]
