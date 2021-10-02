FROM python:3.8-slim as python-base

LABEL maintainer="Yannick Linke <invisi@0x0f.net>"

ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/opt/pysetup"

# App's env
ENV RUNNING_IN_DOCKER=true

# install pipenv
RUN pip install pipenv

WORKDIR $PYSETUP_PATH
COPY Pipfile Pipfile.lock ./

RUN pipenv install --system --deploy --ignore-pipfile

# `production` image used for runtime
FROM python-base as production
COPY --from=python-base $PYSETUP_PATH $PYSETUP_PATH

COPY ./ts3bot /app/ts3bot
COPY ./alembic.ini /app/

WORKDIR /app
CMD [ "python", "-m", "ts3bot", "bot" ]
