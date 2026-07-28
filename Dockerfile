# Official Python image
FROM python:3.12-bookworm
LABEL maintainer="Nikhil <nikhil@nekonik.com>"

# No user interaction for this
ENV DEBIAN_FRONTEND=noninteractive

# Update the package lists
RUN apt-get update

# Install essential packages
RUN apt-get install -y gcc python3.11-dev ansible sshpass curl

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory for logs with appropriate permissions
RUN mkdir -p /var/log/rmq_worker

# Copy code
COPY utils/ utils/
COPY ansible/ ansible/
COPY main.py .

# Run the main file
CMD ["python3", "main.py"]
