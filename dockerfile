# Use official lightweight Python image
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy the action files into the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entrypoint for the action
ENTRYPOINT ["python", "main.py"]
