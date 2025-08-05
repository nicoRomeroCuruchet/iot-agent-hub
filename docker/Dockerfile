FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Copy files
COPY docker/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY server.py .

# Run the Flask app
CMD ["python3", "server.py"]
