FROM python:3.8@sha256:44a850f6b849f06c19e9634e540966ed5f9000094ab719737a6089164b512396

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
RUN pip install --no-cache-dir -r requirements-runtime.txt && \
    pip install --no-cache-dir -r requirements.txt && \
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
