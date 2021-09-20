FROM python:3.9-alpine

RUN apk update && \
    apk add libmemcached-dev postgresql-dev libpq mariadb-dev mariadb-connector-c-dev openssl-dev && \
    apk add gcc musl-dev libffi-dev py-cryptography python3-dev

RUN apk add curl wget bash zsh


RUN pip3 install -U pip && \
    pip3 install -U pipenv

RUN curl https://sh.rustup.rs -sSf | sh -s -- --profile default --default-toolchain nightly -y

ENV PATH "${HOME}/.cargo/bin:${PATH}"
ARG PATH="${PATH}"

WORKDIR /app

RUN apk add sudo rsync
RUN mkdir /app/logs
COPY Pipfile Pipfile.lock requirements.txt /app/

RUN sed -Ei 's/python\_version \= "3.8"/python_version = "3.9"/' Pipfile
RUN PATH="${HOME}/.cargo/bin/:${PATH}" pipenv --python python3.9 install --ignore-pipfile

#COPY example.yaml LICENSE.txt README.md run.sh update_geoip.sh wsgi.py /app/
COPY example.yaml LICENSE.txt README.md /app/
COPY neighgen/ /app/neighgen/
#COPY dkr/init.sh /app/
#RUN chmod +x /app/init.sh /app/update_geoip.sh /app/run.sh /app/wsgi.py

ENTRYPOINT [ "pipenv", "run", "python3", "-m", "neighgen" ]

