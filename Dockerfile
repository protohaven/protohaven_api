FROM python:3.12

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
COPY ./setup.py /app/setup.py
RUN pip install --no-cache-dir -r requirements.txt && pip install -e .
