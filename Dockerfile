# Use official Python slim image for a smaller footprint
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api.py .

# Expose the port (Render assigns PORT dynamically)
EXPOSE 8000

# Command to run the application
CMD ["python", "api.py"]
