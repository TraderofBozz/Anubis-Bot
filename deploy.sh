#!/bin/bash

# DigitalOcean Anubis Bot Deployment Script

echo "🚀 Deploying Anubis Bot to DigitalOcean..."

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "Please install doctl first: https://docs.digitalocean.com/reference/doctl/how-to/install/"
    exit 1
fi

# Configuration
DROPLET_NAME="anubis-bot"
REGION="nyc3"  # Change to your preferred region
SIZE="s-1vcpu-2gb"  # $18/month
IMAGE="ubuntu-22-04-x64"

# Create droplet
echo "Creating droplet..."
doctl compute droplet create $DROPLET_NAME \
    --region $REGION \
    --size $SIZE \
    --image $IMAGE \
    --ssh-keys $(doctl compute ssh-key list --format ID --no-header) \
    --wait

# Get IP address
IP=$(doctl compute droplet list $DROPLET_NAME --format PublicIPv4 --no-header)
echo "Droplet created at IP: $IP"

# Wait for SSH
echo "Waiting for SSH..."
sleep 30

# Deploy via SSH
ssh root@$IP << 'ENDSSH'
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
apt install docker-compose -y

# Create app directory
mkdir -p /app
cd /app

# Clone your repository (replace with your repo)
# git clone https://github.com/yourusername/anubis-bot.git .

echo "Deployment complete! 🎉"
ENDSSH

echo "✅ Droplet ready at: $IP"
echo "Next: Copy your files and start the bot"