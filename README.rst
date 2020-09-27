Submitter
=========

AWS Lambda function that reacts to S3 object save events for raw crash
files and submits a specified percentage to another environment.

* Free software: Mozilla Public License version 2.0
* Documentation: this README
* Bugs: `Report a bug <https://bugzilla.mozilla.org/enter_bug.cgi?format=__standard__&product=Socorro>`_
* Community Participation Guidelines: `Guidelines <https://github.com/mozilla-services/socorro-submitter/blob/main/CODE_OF_CONDUCT.md>`_


Details
=======

Raw crash files have keys like this::

  v2/raw_crash/000/20170413/00007bd0-2d1c-4865-af09-80bc00170413


The submitter will "roll a die" to decide whether to submit to a specified
environment.

If so, it'll pull all the raw crash data from S3, package it up, and HTTP POST
it to the collector of the specified environment.


Quickstart
==========

1. `Install docker 18.00.0+ <https://docs.docker.com/install/>`_ and
   `install docker-compose 1.20.0+ <https://docs.docker.com/compose/install/>`_
   on your machine.

   You'll also need git, make, and bash.

2. Clone the repo:

   .. code-block:: shell

      $ git clone https://github.com/mozilla-services/socorro-submitter

3. Download and build Submitter Docker images and Python libraries:

   .. code-block:: shell

      $ make build

   Anytime you change requirements files or code, you'll need to run ``make
   build`` again.

4. Run tests:

   .. code-block:: shell

      $ make test

   You can also get a shell and run them manually:

   .. code-block:: shell

      $ make testshell
      app@4205495cfa57:/app$ pytest
      <test output>

   Using the shell lets you run and debug tests more easily.

5. Run the integration test:

   .. code-block:: shell

      $ ./bin/integration_test.sh
      <test output>

6. Invoke the function with a sample S3 ObjectCreated:Put event:

   .. code-block:: shell

      $ ./bin/generate_event.py --key v2/raw_crash/000/20170413/00007bd0-2d1c-4865-af09-80bc00170413 > event.json
      $ cat event.json | ./bin/run_invoke.sh
      <invoke output>

   FIXME -- check fake collector


Caveats of this setup
=====================

1. Because ``submitter.py`` is copied into ``build/`` and that version is tested
   and invoked, if you edit ``submitter.py``, you need to run ``make build``
   again. This is kind of annoying when making changes.

2. Packaging the ``.zip`` file and deploying it are not handled by the
   scaffolding in this repo.


Scripts
=======

* FIXME -- fake collector

* ``bin/generate_event.py``: Generates a sample AWS S3 event.

* ``bin/run_invoke.sh``: Invokes the submitter function in a AWS Lambda Python
  3.8 runtime environment.

* ``bin/integration_test.sh``: Runs an integration test.

* ``bin/run_circle.sh``: The script that Circle CI runs.


Configuration
=============

All configuration for Submitter relates to the RabbitMQ service it needs to connect
to.

Required environment variables:

* ``SUBMITTER_ENV_NAME``: The environment name. This is for tagging metrics with
  the environment.
* ``SUBMITTER_THROTTLE``: The percent of crashes to submit; 0 is none, 100 is
  all.
* ``SUBMITTER_DESTINATION_URL``: The full url of the collector to post crashes
  to.
* ``SUBMITTER_S3_BUCKET``: The s3 bucket to pull crash data from.
* ``SUBMITTER_S3_REGION_NAME``: The AWS region to use.

Then for local development, you need these:

* ``SUBMITTER_S3_ACCESS_KEY``: The s3 access key to use to access the bucket.
* ``SUBMITTER_S3_SECRET_ACCESS_KEY``: The s3 secret access key to use to access
  the bucket.
* ``SUBMITTER_S3_ENDPOINT_URL``: The endpoint url for the fake s3.

If any of these are missing from the environment, Submitter will raise a ``KeyError``.
