# syntax=docker/dockerfile:1

FROM python:3.11.8-alpine
WORKDIR /code
ENV FLASK_APP=protohaven_api.main
ENV FLASK_RUN_HOST=0.0.0.0
RUN apk add --no-cache gcc musl-dev linux-headers
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN pip install flask-sock
EXPOSE 5000
COPY . .
CMD ["flask", "run", "--debug"]
