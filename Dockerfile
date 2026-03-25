FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p data

# Expose Flask webhook port
EXPOSE 5000

# Run the application
CMD ["python3", "main.py"]
