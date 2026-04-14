FROM python:3.11-slim

WORKDIR /app

RUN pip install flask==3.0.3

COPY worker.py .

EXPOSE 5001

CMD ["python", "worker.py"]