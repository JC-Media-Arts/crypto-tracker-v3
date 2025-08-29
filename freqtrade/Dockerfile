# Freqtrade Docker image for Railway deployment
FROM python:3.11-slim-bullseye

# Install system dependencies
RUN apt-get update \
    && apt-get -y install curl build-essential git wget bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Set working directory
WORKDIR /freqtrade

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install numpy \
    && pip install TA-Lib \
    && pip install -r requirements.txt

# Copy the entire freqtrade directory
COPY . .

# Create necessary directories
RUN mkdir -p user_data/logs user_data/data/kraken

# Set environment variables for Railway
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Make startup script executable
RUN chmod +x start.sh

# Run Freqtrade via startup script
CMD ["./start.sh"]
