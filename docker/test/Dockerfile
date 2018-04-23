FROM python:3.6

WORKDIR /app/
RUN groupadd --gid 1001 app && useradd -g app --uid 1001 --shell /usr/sbin/nologin app

RUN apt-get update && \
    apt-get install -y gcc apt-transport-https

COPY ./requirements-dev.txt /app/requirements-dev.txt

RUN pip install -U 'pip>=8' && \
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
