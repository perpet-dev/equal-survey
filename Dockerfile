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
RUN pip install --no-cache-dir -r requirements.txt
# Copy your application code
COPY . .
ENV OPENAI_API_KEY="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"
# Expose port and define command to run the app
EXPOSE 10000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "10000"]
