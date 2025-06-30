FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mlb-discord-rpc.py ./

ENTRYPOINT ["python", "mlb-discord-rpc.py"]
CMD []
