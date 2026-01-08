# syntax=docker/dockerfile:1

FROM python:3.13.7-slim-bookworm
WORKDIR /code

# Debian doesn't come with en_us.UTF-8 locale by default, but we set locale
# in python code.
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y locales
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8
ENV LANG en_US.UTF-8

ENV FLASK_APP=protohaven_api.main
ENV FLASK_RUN_HOST=0.0.0.0

RUN apt-get update && apt-get install -y --no-install-recommends gcc git curl bash && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install  -r requirements.txt
RUN pip install flask-sock playwright
RUN playwright install --with-deps --only-shell firefox

EXPOSE 5000
COPY . .
CMD ["flask", "run", "--debug"]
