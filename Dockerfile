FROM python:3.7.2

MAINTAINER LSST SQuaRE <sqre-admin@lists.lsst.org>
LABEL description="Templatebot is an api.lsst.codes microservice for creating new projects and files from templates." \
      name="lsstsqre/templatebot"

ENV APPDIR /app
RUN mkdir $APPDIR
WORKDIR $APPDIR

# Supply on CL as --build-arg VERSION=<version> (or run `make image`).
ARG VERSION
LABEL version="$VERSION"

# Must run python setup.py sdist first before building the Docker image.

COPY dist/templatebot-$VERSION.tar.gz .
RUN pip install templatebot-$VERSION.tar.gz && \
    rm templatebot-$VERSION.tar.gz && \
    groupadd -r app_grp && useradd -r -g app_grp app && \
    chown -R app:app_grp $APPDIR

USER app

EXPOSE 8080

CMD ["templatebot", "run", "--port", "8080"]
