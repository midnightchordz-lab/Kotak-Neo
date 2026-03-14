# Complete AWS Setup Guide: EC2 + Domain + SSL

## Part 1: Creating & Launching EC2 Instance

### Step 1.1: Sign in to AWS Console
1. Go to https://aws.amazon.com
2. Click **Sign In to the Console** (top right)
3. Enter your AWS credentials

### Step 1.2: Navigate to EC2
1. In the search bar at top, type **EC2**
2. Click **EC2** from the dropdown
3. You'll see the EC2 Dashboard

### Step 1.3: Launch Instance
1. Click the orange **Launch Instance** button

### Step 1.4: Configure Instance Details

#### Name and Tags
```
Name: costar-algo-trader
```

#### Application and OS Images (AMI)
1. Click **Ubuntu**
2. Select: **Ubuntu Server 22.04 LTS (HVM), SSD Volume Type**
3. Architecture: **64-bit (x86)**

#### Instance Type
```
For testing:  t2.micro (Free tier eligible)
For production: t2.small or t2.medium
```

| Type | vCPUs | Memory | Cost/Month |
|------|-------|--------|------------|
| t2.micro | 1 | 1 GB | Free (12 months) |
| t2.small | 1 | 2 GB | ~$17 |
| t2.medium | 2 | 4 GB | ~$34 |

#### Key Pair (Login)
1. Click **Create new key pair**
2. Key pair name: `costar-key`
3. Key pair type: **RSA**
4. Private key format: **.pem** (for Mac/Linux) or **.ppk** (for Windows PuTTY)
5. Click **Create key pair**
6. **⚠️ IMPORTANT: Save the downloaded .pem file safely! You cannot download it again!**

#### Network Settings
Click **Edit** and configure:

```
☑️ Allow SSH traffic from: My IP (or Anywhere if IP changes)
☑️ Allow HTTPS traffic from the internet
☑️ Allow HTTP traffic from the internet
```

Then click **Add security group rule** twice to add:
```
Type: Custom TCP    Port: 8001    Source: Anywhere (0.0.0.0/0)
Type: Custom TCP    Port: 3000    Source: Anywhere (0.0.0.0/0)
```

#### Configure Storage
```
Size: 20 GiB
Volume type: gp3
```

### Step 1.5: Launch!
1. Review your settings in the **Summary** panel on the right
2. Click **Launch Instance**
3. Click **View all instances**

### Step 1.6: Wait for Instance to Start
1. Wait until **Instance State** shows: `Running` ✅
2. Wait until **Status check** shows: `2/2 checks passed` ✅
3. Note your **Public IPv4 address** (e.g., `54.123.45.67`)

---

## Part 2: Connect to Your EC2 Instance

### For Mac/Linux Users

```bash
# 1. Open Terminal

# 2. Navigate to where you saved the .pem file
cd ~/Downloads

# 3. Set correct permissions (REQUIRED)
chmod 400 costar-key.pem

# 4. Connect via SSH (replace with YOUR IP)
ssh -i costar-key.pem ubuntu@YOUR_PUBLIC_IP

# Example:
ssh -i costar-key.pem ubuntu@54.123.45.67
```

### For Windows Users (Using PuTTY)

1. Download PuTTY: https://www.putty.org/
2. If you downloaded .pem, convert to .ppk:
   - Open **PuTTYgen**
   - Click **Load** → Select your .pem file
   - Click **Save private key** → Save as `costar-key.ppk`
3. Open **PuTTY**:
   - Host Name: `ubuntu@YOUR_PUBLIC_IP`
   - Port: 22
   - Connection → SSH → Auth → Browse → Select your .ppk file
   - Click **Open**

### First Time Connection
When prompted "Are you sure you want to continue connecting?", type `yes`

You should see:
```
Welcome to Ubuntu 22.04.x LTS
ubuntu@ip-xxx-xxx-xxx-xxx:~$
```

🎉 **You're now connected to your EC2 instance!**

---

## Part 3: Install Everything on EC2

Copy and paste these commands one section at a time:

### 3.1: Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2: Install Python
```bash
sudo apt install -y python3 python3-pip python3-venv
python3 --version  # Should show Python 3.10+
```

### 3.3: Install Node.js 18
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
node --version  # Should show v18.x
npm --version   # Should show 9.x or 10.x
```

### 3.4: Install Yarn & PM2
```bash
sudo npm install -g yarn pm2
```

### 3.5: Install MongoDB
```bash
# Import MongoDB GPG key
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install MongoDB
sudo apt update
sudo apt install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod

# Verify it's running
sudo systemctl status mongod
# Should show "active (running)"
```

### 3.6: Install Nginx
```bash
sudo apt install -y nginx
sudo systemctl status nginx  # Should be active
```

### 3.7: Install Git
```bash
sudo apt install -y git
```

---

## Part 4: Upload Your Code to EC2

### Option A: From GitHub (Recommended)

If your code is on GitHub:
```bash
cd ~
git clone https://github.com/YOUR_USERNAME/costar-algo-trader.git
cd costar-algo-trader
```

### Option B: Direct Upload via SCP

Run this on your **LOCAL machine** (not EC2):

**Mac/Linux:**
```bash
# Navigate to your project folder locally
cd /path/to/your/app

# Upload to EC2 (replace YOUR_IP)
scp -i ~/Downloads/costar-key.pem -r ./* ubuntu@YOUR_PUBLIC_IP:~/costar-algo-trader/
```

**Windows (using PowerShell):**
```powershell
scp -i C:\Users\YOU\Downloads\costar-key.pem -r .\* ubuntu@YOUR_PUBLIC_IP:~/costar-algo-trader/
```

### Option C: Create Files Manually

If the above don't work, I can provide commands to create each file directly on EC2.

---

## Part 5: Setup Backend on EC2

```bash
# Navigate to backend
cd ~/costar-algo-trader/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file with your credentials
cat > .env << 'EOF'
MONGO_URL="mongodb://localhost:27017"
DB_NAME="algo_trader"
EMERGENT_LLM_KEY="sk-emergent-YOUR-KEY-HERE"
KOTAK_ACCESS_TOKEN="your-kotak-token-here"
EOF

# Edit with your actual credentials
nano .env
# (Press Ctrl+X, then Y, then Enter to save)

# Test backend starts
uvicorn server:app --host 0.0.0.0 --port 8001
# Press Ctrl+C to stop after testing
```

---

## Part 6: Setup Frontend on EC2

```bash
# Navigate to frontend
cd ~/costar-algo-trader/frontend

# Install dependencies
yarn install

# Create .env file (replace YOUR_IP or YOUR_DOMAIN)
echo 'EXPO_PUBLIC_BACKEND_URL=http://YOUR_PUBLIC_IP' > .env

# Or if you have a domain:
# echo 'EXPO_PUBLIC_BACKEND_URL=https://yourdomain.com' > .env
```

---

## Part 7: Setup PM2 Process Manager

```bash
cd ~/costar-algo-trader

# Create PM2 ecosystem file
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'backend',
      cwd: './backend',
      script: './venv/bin/uvicorn',
      args: 'server:app --host 0.0.0.0 --port 8001',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
    },
    {
      name: 'frontend',
      cwd: './frontend',
      script: 'npx',
      args: 'expo start --web --port 3000 --no-dev',
      interpreter: 'none',
      autorestart: true,
      watch: false,
    }
  ]
};
EOF

# Start all services
pm2 start ecosystem.config.js

# Check status
pm2 status

# Should show:
# ┌─────┬──────────┬─────────────┬─────────┬─────────┬──────────┐
# │ id  │ name     │ mode        │ status  │ cpu     │ memory   │
# ├─────┼──────────┼─────────────┼─────────┼─────────┼──────────┤
# │ 0   │ backend  │ fork        │ online  │ 0%      │ 50mb     │
# │ 1   │ frontend │ fork        │ online  │ 0%      │ 100mb    │
# └─────┴──────────┴─────────────┴─────────┴─────────┴──────────┘

# Save PM2 configuration
pm2 save

# Setup PM2 to start on boot
pm2 startup
# Copy and run the command it outputs!
```

---

## Part 8: Configure Nginx (Web Server)

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/costar
```

Paste this configuration (replace YOUR_DOMAIN_OR_IP):
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    # Frontend - React/Expo app
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Save and exit (Ctrl+X, Y, Enter)

```bash
# Enable the site
sudo ln -sf /etc/nginx/sites-available/costar /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t
# Should show: syntax is ok, test is successful

# Restart Nginx
sudo systemctl restart nginx
```

### Test Your App!

Open in browser: `http://YOUR_EC2_PUBLIC_IP`

You should see the COSTAR login screen! 🎉

---

## Part 9: Setup Custom Domain (Optional)

### 9.1: Buy/Get a Domain
- **Namecheap**: https://namecheap.com (~$10/year for .com)
- **GoDaddy**: https://godaddy.com
- **Google Domains**: https://domains.google
- **AWS Route 53**: In AWS Console

### 9.2: Point Domain to EC2

#### Option A: Using Your Domain Registrar's DNS

Add these DNS records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | YOUR_EC2_PUBLIC_IP | 300 |
| A | www | YOUR_EC2_PUBLIC_IP | 300 |

Example for `costar-trader.com`:
```
A Record:  @    →  54.123.45.67
A Record:  www  →  54.123.45.67
```

#### Option B: Using AWS Route 53 (More Reliable)

1. Go to **Route 53** in AWS Console
2. Click **Hosted zones** → **Create hosted zone**
3. Domain name: `yourdomain.com`
4. Type: Public hosted zone
5. Click **Create hosted zone**
6. Note the 4 **NS (Name Server)** records shown
7. Go to your domain registrar and update nameservers to the AWS ones
8. Back in Route 53, click **Create record**:
   - Record name: (leave empty for root domain)
   - Record type: A
   - Value: YOUR_EC2_PUBLIC_IP
   - Click **Create records**
9. Create another for `www`:
   - Record name: www
   - Record type: A
   - Value: YOUR_EC2_PUBLIC_IP

### 9.3: Wait for DNS Propagation
- Usually takes 5-30 minutes
- Can take up to 48 hours
- Check status: https://dnschecker.org

### 9.4: Update Nginx with Domain

```bash
sudo nano /etc/nginx/sites-available/costar
```

Change the `server_name` line:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

```bash
sudo nginx -t
sudo systemctl restart nginx
```

### 9.5: Update Frontend .env

```bash
cd ~/costar-algo-trader/frontend
echo 'EXPO_PUBLIC_BACKEND_URL=http://yourdomain.com' > .env

# Restart frontend
pm2 restart frontend
```

---

## Part 10: Setup SSL/HTTPS (Free with Let's Encrypt)

### 10.1: Install Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 10.2: Get SSL Certificate

```bash
# Replace with YOUR domain
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts:
1. Enter your email address
2. Agree to terms: `Y`
3. Share email with EFF: `N` (optional)
4. Redirect HTTP to HTTPS: `2` (recommended)

### 10.3: Verify SSL

Open in browser: `https://yourdomain.com`

You should see:
- 🔒 Lock icon in address bar
- COSTAR login page loads

### 10.4: Auto-Renewal (Already Configured)

Certbot automatically sets up renewal. Test it:
```bash
sudo certbot renew --dry-run
```

### 10.5: Update Frontend for HTTPS

```bash
cd ~/costar-algo-trader/frontend
echo 'EXPO_PUBLIC_BACKEND_URL=https://yourdomain.com' > .env
pm2 restart frontend
```

---

## ✅ Final Checklist

- [ ] EC2 instance running
- [ ] Can SSH into instance
- [ ] MongoDB running
- [ ] Backend running (PM2)
- [ ] Frontend running (PM2)
- [ ] Nginx configured
- [ ] App accessible via IP: `http://YOUR_IP`
- [ ] Domain pointing to EC2 (optional)
- [ ] SSL certificate installed (optional)
- [ ] App accessible via `https://yourdomain.com`

---

## 🔧 Troubleshooting Commands

```bash
# Check all services status
pm2 status
sudo systemctl status nginx
sudo systemctl status mongod

# View logs
pm2 logs backend
pm2 logs frontend
sudo tail -f /var/log/nginx/error.log

# Restart services
pm2 restart all
sudo systemctl restart nginx
sudo systemctl restart mongod

# Check if ports are open
sudo netstat -tlnp | grep -E '80|443|3000|8001'

# Check disk space
df -h

# Check memory
free -m
```

---

## 🆘 Common Issues

### "Connection refused" on port 80
```bash
sudo systemctl start nginx
sudo ufw allow 80
sudo ufw allow 443
```

### Backend not starting
```bash
cd ~/costar-algo-trader/backend
source venv/bin/activate
python -c "from server import app"  # Check for errors
```

### MongoDB connection failed
```bash
sudo systemctl restart mongod
mongo  # Should open mongo shell
```

### SSL certificate failed
- Make sure domain DNS is pointing to EC2
- Wait for DNS propagation (use dnschecker.org)
- Ensure ports 80 and 443 are open in EC2 security group
