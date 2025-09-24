# syntax=docker/dockerfile:1

FROM python:3.12.7-alpine
WORKDIR /code

ENV FLASK_APP=protohaven_api.main
ENV FLASK_RUN_HOST=0.0.0.0

RUN apk add --no-cache gcc musl-dev linux-headers git curl bash

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

EXPOSE 5000
COPY . .
CMD ["python3", "-m", "protohaven_api.ldap_server", "5001"]

