FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for rasterio/GDAL
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

COPY requirements.txt .

# Install Python dependencies
# We use --no-cache-dir to keep the image small
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the Hugging Face model during the image build to speed up startup
# (Optional, but good for local dev)
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from transformers import AutoModel; AutoModel.from_pretrained('ibm-nasa-geospatial/Prithvi-EO-1.0-100M', trust_remote_code=True)" || true

# Copy application code and scripts
COPY . .

# Ensure output directories exist (they may be overridden by volume mounts)
RUN mkdir -p data/deforestation data/disaster public/masks public/images raw_data

EXPOSE 8082

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]
