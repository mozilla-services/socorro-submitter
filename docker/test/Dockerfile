FROM python:3.8.14@sha256:3693c8e04424d2155e8fcf932031727ec587f1182b7301bb0b88bb1593b2f144

# Set up user and group
ARG groupid=10001
ARG userid=10001

WORKDIR /app/
RUN groupadd --gid $groupid app && \
    useradd -g app --uid $userid --shell /usr/sbin/nologin app

RUN apt-get update && \
    apt-get install -y gcc apt-transport-https

COPY ./requirements.txt /app/requirements.txt
COPY ./requirements-runtime.txt /app/requirements-runtime.txt
COPY ./requirements-dev.txt /app/requirements-dev.txt

# Install the Python dependencies that are in the Python Lambda runtime, then
# the ones we need for socorro-submitter, then the ones needed for testing.
RUN echo '>>> update pip...' && \
    pip install -U pip && \
    echo '>>> install requirements-runtime.txt...' && \
    pip install --no-cache-dir -r requirements-runtime.txt && \
    echo '>>> install requirements.txt...' && \
    pip install --no-cache-dir -r requirements.txt && \
    echo '>>> install requirements-dev.txt...' && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy app repo
COPY . /app/

# Install libs into /app/build
RUN ./bin/run_build.sh

# Set Python-related environment variables to reduce annoying-ness
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

USER app

CMD bash
