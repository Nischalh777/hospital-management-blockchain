# 🚀 Quick Setup Guide

## Prerequisites

- Python 3.8 or higher
- MySQL Server
- Git
- Node.js (for Storacha CLI)

## Step-by-Step Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/hospital-management-blockchain.git
cd hospital-management-blockchain
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up MySQL Database

```sql
CREATE DATABASE hospital_db;
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
```env
RPC_URL=https://rpc-amoy.polygon.technology/
PRIVATE_KEY=your_wallet_private_key
CONTRACT_ADDRESS=your_contract_address
ENCRYPTION_KEY=your_encryption_key
GEMINI_API_KEY=your_gemini_api_key
```

### 5. Install Storacha CLI (Optional)

```bash
npm install -g @storacha/cli
storacha login your@email.com
```

### 6. Run Application

```bash
python app.py
```

### 7. Access Application

Open browser: `http://localhost:5000`

## Getting API Keys

### Gemini API Key
1. Visit: https://makersuite.google.com/app/apikey
2. Create new API key
3. Copy to `.env`

### Polygon Wallet
1. Install MetaMask
2. Create wallet
3. Export private key
4. Copy to `.env`

### Test MATIC
1. Visit: https://faucet.polygon.technology/
2. Select Polygon Amoy
3. Paste your wallet address
4. Get free test MATIC

## Troubleshooting

**Issue: Module not found**
```bash
pip install -r requirements.txt
```

**Issue: Database connection error**
- Check MySQL is running
- Verify database credentials in `app.py`

**Issue: Storacha not found**
```bash
npm install -g @storacha/cli
```

## Next Steps

1. Create hospital account
2. Register doctors
3. Create patient account
4. Upload test document
5. Verify on blockchain

## Support

For issues, open a GitHub issue or contact support.

Happy coding! 🎉
