FROM python:3.9-slim
# Set working directory
WORKDIR /app
# Copy only the requirements file, to cache the dependencies
# Install system dependencies without recommended packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
# Install Python dependencies
RUN pip install -r requirements.txt
# Copy your application code
COPY . .
ENV PORT 10071
# Expose the port the app runs on
EXPOSE $PORT
#CMD ["python", "server.py"]
CMD uvicorn server:app --host 0.0.0.0 --port $PORT --workers 4
