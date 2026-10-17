FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for yt-dlp audio extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code
COPY . .

# Ensure startup script is executable
RUN chmod +x start.sh

# Expose default port
EXPOSE 8501

# Start both background indexer and Streamlit UI
CMD ["./start.sh"]
