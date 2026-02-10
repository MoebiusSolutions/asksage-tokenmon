FROM python:3.14-slim

# RUN apt-get update && apt-get install -y \
#     build-essential \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    # Used to interact with REST endpoints
    requests \
    # Used for testing
    pytest \
    # AskSage API and dependencies
    asksageclient pip_system_certs

WORKDIR /app
COPY ./python /app

ENTRYPOINT ["python3", "/app/main.py" ]

