FROM python:3.11-slim

WORKDIR /app

# System deps for rasterio/GDAL/OpenCV
RUN apt-get update && apt-get install -y \
    gdal-bin libgdal-dev libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure output dir exists
RUN mkdir -p output_files explorer_data models

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
