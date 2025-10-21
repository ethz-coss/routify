# Use official Python image
FROM python:3.11

# Set working directory
WORKDIR /app

# Install system dependencies for GDAL/rasterio
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV GDAL_DATA=/usr/share/gdal

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files (including seed files)
COPY . .

# Verify seed file exists (optional, for debugging)
RUN ls -la seed_*.png 2>/dev/null || echo "No seed files found"

# Expose port 8000
EXPOSE 8000

# Set default command (can be overridden at runtime)
CMD ["python", "OstLuftApi.py"]