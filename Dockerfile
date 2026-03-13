FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY . .

# Install system dependencies
RUN apt-get update && \
    apt-get install -y libzbar0 dumb-init && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Required for cv2 to run otherwise throws: ImportError: libGL.so.1: cannot open shared object file error
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

RUN sh scripts/setup.sh

# Expose ports for various services
EXPOSE 3000 5173 7860 8000 8080

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["sleep", "infinity"]