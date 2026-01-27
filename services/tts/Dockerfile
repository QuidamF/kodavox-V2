# Stage 1: Base image with Python and CUDA support
# Using an official NVIDIA CUDA image which is necessary for GPU access.
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

# Set environment variables to prevent interactive prompts during installation
ENV TZ=Etc/UTC
ENV DEBIAN_FRONTEND=noninteractive

# Install Python, pip, and essential audio libraries
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    libsndfile1 \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Create a symlink for python3 to python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Patch TTS/utils/io.py to include weights_only=False for torch.load
# This resolves UnpicklingError with PyTorch 2.6+ when loading XTTSv2 models
RUN sed -i "s/return torch.load(f, map_location=map_location, \*\*kwargs)/return torch.load(f, map_location=map_location, weights_only=False, \*\*kwargs)/g" /usr/local/lib/python3.10/dist-packages/TTS/utils/io.py


# Copy the rest of the application code
COPY ./app ./app
COPY ./voices ./voices

# Expose the port the app runs on
EXPOSE 8000

# The command to run the application
# Uvicorn will run the FastAPI application defined in app/main.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
