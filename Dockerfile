FROM python:3.12

WORKDIR /app

# COPY requirements.txt ./
RUN pip install --no-cache-dir gunicorn
# -r requirements.txt && pip install -e .

EXPOSE 4100

