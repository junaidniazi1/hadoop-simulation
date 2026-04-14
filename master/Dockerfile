FROM python:3.11-slim

WORKDIR /app

RUN pip install flask==3.0.3 requests==2.32.3

COPY master.py .

EXPOSE 5000

CMD ["python", "master.py"]