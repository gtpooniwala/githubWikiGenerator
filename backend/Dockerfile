FROM python:3.11-slim

WORKDIR /app

RUN pip install fastapi uvicorn

COPY src/ ./src/

EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
