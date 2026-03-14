# AWS EC2 Deployment Guide for COSTAR Algo Trader

## Prerequisites
- AWS Account
- Domain name (optional, for HTTPS)
- Your Kotak NEO credentials

---

## Step 1: Launch EC2 Instance

### 1.1 Go to AWS Console
- Navigate to **EC2 Dashboard**
- Click **Launch Instance**

### 1.2 Configure Instance
```
Name: costar-algo-trader
AMI: Ubuntu Server 22.04 LTS (Free tier eligible)
Instance Type: t2.small (or t2.micro for testing)
Key Pair: Create new or select existing (SAVE THE .pem FILE!)
```

### 1.3 Network Settings
- Allow SSH (port 22)
- Allow HTTP (port 80)
- Allow HTTPS (port 443)
- Allow Custom TCP (port 8001) - Backend API
- Allow Custom TCP (port 3000) - Frontend

### 1.4 Storage
- 20 GB gp3 (default is fine)

### 1.5 Launch Instance
- Click **Launch Instance**
- Wait for instance to be "Running"
- Note the **Public IPv4 address**

---

## Step 2: Connect to Instance

```bash
# Make key file secure
chmod 400 your-key.pem

# Connect via SSH
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP
```

---

## Step 3: Install Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js 18
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install Yarn
sudo npm install -g yarn

# Install MongoDB
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Install Nginx (reverse proxy)
sudo apt install -y nginx

# Install PM2 (process manager)
sudo npm install -g pm2
```

---

## Step 4: Upload Code

### Option A: From GitHub
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/costar-algo-trader.git
cd costar-algo-trader
```

### Option B: Using SCP (from local machine)
```bash
# Run this on your LOCAL machine
scp -i your-key.pem -r /path/to/app ubuntu@YOUR_PUBLIC_IP:~/costar-algo-trader
```

---

## Step 5: Setup Backend

```bash
cd ~/costar-algo-trader/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="algo_trader"
EMERGENT_LLM_KEY="YOUR_EMERGENT_LLM_KEY"
KOTAK_ACCESS_TOKEN="YOUR_KOTAK_ACCESS_TOKEN"
EOF

# Edit with your actual keys
nano .env
```

---

## Step 6: Setup Frontend

```bash
cd ~/costar-algo-trader/frontend

# Install dependencies
yarn install

# Create .env file
echo 'EXPO_PUBLIC_BACKEND_URL=http://YOUR_PUBLIC_IP:8001' > .env

# Build for production
yarn build:web
# Or if using Expo: npx expo export --platform web
```

---

## Step 7: Configure PM2 (Process Manager)

Create ecosystem file:
```bash
cd ~/costar-algo-trader

cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'backend',
      cwd: './backend',
      script: 'venv/bin/uvicorn',
      args: 'server:app --host 0.0.0.0 --port 8001',
      interpreter: 'none',
      env: {
        PATH: process.env.PATH + ':./venv/bin'
      }
    },
    {
      name: 'frontend',
      cwd: './frontend',
      script: 'npx',
      args: 'expo start --web --port 3000',
      interpreter: 'none'
    }
  ]
};
EOF
```

Start services:
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup  # Follow the instructions it gives
```

---

## Step 8: Configure Nginx (Reverse Proxy)

```bash
sudo nano /etc/nginx/sites-available/costar
```

Add this configuration:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/costar /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

## Step 9: Setup SSL (HTTPS) - Optional but Recommended

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

---

## Step 10: Configure Firewall

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

---

## Step 11: Access Your App

- **Without domain**: http://YOUR_PUBLIC_IP
- **With domain**: https://yourdomain.com

---

## Useful Commands

```bash
# View logs
pm2 logs

# Restart services
pm2 restart all

# Check status
pm2 status

# Check MongoDB
sudo systemctl status mongod

# Check Nginx
sudo systemctl status nginx
```

---

## Estimated AWS Costs

| Resource | Monthly Cost |
|----------|--------------|
| t2.small EC2 | ~$17/month |
| t2.micro EC2 (free tier) | Free for 12 months |
| 20GB EBS Storage | ~$2/month |
| Data Transfer | ~$1-5/month |
| **Total** | **~$20-25/month** |

---

## Security Recommendations

1. **Use strong passwords** for all services
2. **Enable MFA** on your AWS account
3. **Keep system updated**: `sudo apt update && sudo apt upgrade`
4. **Backup MongoDB** regularly
5. **Use SSL/HTTPS** for production
6. **Restrict SSH access** to your IP only
7. **Don't commit .env files** to git

---

## Troubleshooting

### Backend not starting
```bash
cd ~/costar-algo-trader/backend
source venv/bin/activate
python -c "import server"  # Check for import errors
```

### Frontend not building
```bash
cd ~/costar-algo-trader/frontend
yarn install --force
yarn build:web
```

### MongoDB connection issues
```bash
sudo systemctl status mongod
sudo systemctl restart mongod
```

### Check PM2 logs
```bash
pm2 logs backend --lines 50
pm2 logs frontend --lines 50
```
