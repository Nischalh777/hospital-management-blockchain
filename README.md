# 🏥 Hospital Management System with Blockchain & IPFS

A comprehensive hospital management system featuring decentralized storage using IPFS and blockchain technology for secure, tamper-proof medical records.

## 🌟 Features

### Core Functionality
- **Patient Management** - Registration, profiles, and medical history
- **Doctor Management** - Registration, specializations, and appointments
- **Hospital Management** - Multi-hospital support with admin controls
- **Appointment Booking** - Schedule and manage patient-doctor appointments
- **Medical Records** - Digital storage of prescriptions, reports, and documents

### Advanced Features
- **🔗 Blockchain Integration** - Immutable proof of document uploads on Polygon Amoy
- **📦 IPFS Storage** - Decentralized file storage using Storacha (web3.storage)
- **🔒 End-to-End Encryption** - XOR encryption for sensitive medical documents
- **🤖 AI Medical Chatbot** - Gemini-powered medical advice assistant
- **🔐 Role-Based Access Control** - Secure access for patients, doctors, and hospitals

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         Flask Web Application            │
├─────────────────────────────────────────┤
│                                          │
│  ┌────────────┐  ┌────────────┐        │
│  │   IPFS     │  │ Blockchain │        │
│  │ (Storacha) │  │  (Polygon) │        │
│  └────────────┘  └────────────┘        │
│        │                │               │
│        └────────┬───────┘               │
│                 │                       │
│         ┌───────▼────────┐             │
│         │  MySQL Database │             │
│         └────────────────┘             │
└─────────────────────────────────────────┘
```

### Three-Layer Storage System

1. **IPFS (Storacha)** - Stores actual file content (decentralized)
2. **Blockchain (Polygon Amoy)** - Stores immutable proof of upload
3. **MySQL Database** - Stores metadata for fast queries

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- MySQL Server
- Storacha CLI (for IPFS uploads)
- Tesseract OCR (optional, for image text extraction)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Nischalh777/hospital-management-blockchain.git
cd hospital-management-blockchain
```

2. **Install dependencies**
```bash
pip install flask flask-sqlalchemy pymysql web3 requests beautifulsoup4 google-generativeai pillow pytesseract python-dotenv
```

3. **Set up MySQL database**
```sql
CREATE DATABASE hospital_db;
```

4. **Configure environment variables**

Create a `.env` file in the root directory:
```env
# Blockchain Configuration
RPC_URL=https://rpc-amoy.polygon.technology/
PRIVATE_KEY=your_wallet_private_key
CONTRACT_ADDRESS=your_contract_address
ENCRYPTION_KEY=your_encryption_key

# AI Chatbot
GEMINI_API_KEY=your_gemini_api_key

# Optional
IPFS_ONLY_MODE=false
```

5. **Run the application**
```bash
python app.py
```

6. **Access the application**
```
http://localhost:5000
```

## 📋 Usage

### For Patients

1. **Register** - Create account with email and date of birth
2. **Login** - Use email and DOB as password
3. **Upload Documents** - Upload medical reports, prescriptions, X-rays
4. **Enable Blockchain** - Check "Enable Blockchain Storage" for decentralized storage
5. **Enable Encryption** - Check "Encrypt File" for secure storage
6. **View Documents** - Access your medical records anytime

### For Doctors

1. **Register** - Hospital admin registers doctors
2. **Login** - Use email/phone and password
3. **View Appointments** - See scheduled patient appointments
4. **Access Records** - View patient documents (with permission)
5. **Add Medical Records** - Create diagnosis and prescriptions

### For Hospitals

1. **Register** - Create hospital account
2. **Login** - Access admin dashboard
3. **Register Doctors** - Add doctors to your hospital
4. **Manage Staff** - View and manage doctor profiles

## 🔐 Security Features

### Encryption
- Files encrypted using XOR algorithm before upload
- Encryption key stored securely in environment variables
- Only authorized users can decrypt files

### Access Control
- Role-based authentication (Patient/Doctor/Hospital)
- Patients can only view their own documents
- Doctors can only view documents of their patients
- Session-based security

### Blockchain Security
- Private key never exposed to frontend
- Transactions signed locally
- Immutable records on Polygon blockchain
- Verifiable timestamps

### IPFS Security
- Content-addressed storage (CID = hash of content)
- Tampering changes CID (detectable)
- Distributed across multiple nodes

## 🔗 Blockchain Integration

### Smart Contract

The system uses a Solidity smart contract deployed on Polygon Amoy testnet:

```solidity
contract MedicalRecords {
    struct Record {
        string cid;           // IPFS Content ID
        string patientId;     // Patient identifier
        string metadata;      // Document metadata
        uint256 timestamp;    // Upload timestamp
        address uploader;     // Uploader address
    }
    
    function addRecord(string cid, string patientId, string metadata) public;
    function getRecord(uint256 index) public view returns (Record);
}
```

### Upload Flow

```
1. User uploads document
   ↓
2. System encrypts file (if enabled)
   ↓
3. Upload to IPFS → Get CID
   ↓
4. Record on blockchain → Get TX Hash
   ↓
5. Save metadata to database
   ↓
6. User receives confirmation
```

### Verification

- **IPFS**: Visit `https://ipfs.io/ipfs/{CID}`
- **Blockchain**: Visit `https://amoy.polygonscan.com/tx/{TX_HASH}`

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask (Python) |
| Database | MySQL |
| ORM | SQLAlchemy |
| Blockchain | Polygon Amoy Testnet |
| Smart Contract | Solidity |
| Web3 Library | Web3.py |
| Storage | IPFS (Storacha) |
| Encryption | XOR Algorithm |
| AI Chatbot | Google Gemini |
| OCR | Tesseract |
| Frontend | HTML/CSS/JavaScript |

## 📁 Project Structure

```
hospital-management-blockchain/
├── app.py                      # Main Flask application
├── blockchain_storage.py       # IPFS & blockchain integration
├── chatbot.py                  # AI medical chatbot
├── config.py                   # Configuration settings
├── contract_abi.json          # Smart contract ABI
├── .env                       # Environment variables
├── templates/                 # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── patient_dashboard.html
│   ├── doctor_dashboard.html
│   └── ...
├── static/                    # CSS, JS, images
│   ├── css/
│   ├── js/
│   └── images/
└── uploads/                   # Local file storage
```

## 🔧 Configuration

### Blockchain Setup

1. **Get Test MATIC**
   - Visit: https://faucet.polygon.technology/
   - Select: Polygon Amoy
   - Get free test MATIC for transactions

2. **Deploy Smart Contract**
   - Compile `MedicalRecords.sol`
   - Deploy to Polygon Amoy
   - Copy contract address to `.env`

3. **Configure Wallet**
   - Export private key from MetaMask
   - Add to `.env` file (keep secure!)

### IPFS Setup

1. **Install Storacha CLI**
```bash
npm install -g @storacha/cli
```

2. **Login to Storacha**
```bash
storacha login your@email.com
```

3. **Create Space**
```bash
storacha space create my-hospital-space
```

## 📊 Performance

| Operation | Time | Cost |
|-----------|------|------|
| File Upload | ~5 seconds | ~$0.01 (testnet free) |
| File Download | ~2 seconds | Free |
| Blockchain Query | <1 second | Free |
| Database Query | <0.1 second | Free |

## 🎯 Key Features Explained

### Decentralized Storage
- Files stored on IPFS (not on central server)
- Accessible from anywhere via IPFS gateways
- No single point of failure

### Blockchain Proof
- Every upload recorded on blockchain
- Immutable timestamp
- Cryptographic proof of authenticity
- Publicly verifiable

### Encryption
- Files encrypted before upload
- Only authorized users can decrypt
- Secure key management

## 🐛 Troubleshooting

### Common Issues

**Issue: "Insufficient funds for gas"**
- Solution: Get test MATIC from faucet

**Issue: "Storacha CLI not found"**
- Solution: Install Storacha CLI: `npm install -g @storacha/cli`

**Issue: "Download failed from IPFS"**
- Solution: Wait 2-3 minutes for IPFS propagation

**Issue: "Decryption failed"**
- Solution: Check ENCRYPTION_KEY in .env matches upload key

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👥 Authors

- Your Name - Initial work

## 🙏 Acknowledgments

- Polygon for blockchain infrastructure
- Storacha (web3.storage) for IPFS storage
- Google Gemini for AI capabilities
- Flask community for excellent documentation

## 📞 Support

For support, email your@email.com or open an issue in the repository.

## 🔮 Future Enhancements

- [ ] Multi-chain support (Ethereum, BSC)
- [ ] NFT-based medical records
- [ ] Zero-knowledge proofs for privacy
- [ ] Mobile application
- [ ] Telemedicine integration
- [ ] Insurance claim automation
- [ ] Analytics dashboard

## 📈 Project Status

✅ **Completed Features:**
- Patient/Doctor/Hospital management
- Appointment booking system
- Document upload/download
- IPFS integration
- Blockchain recording
- Encryption/Decryption
- AI medical chatbot
- Access control

⏳ **In Progress:**
- Mobile responsive design
- Advanced analytics
- Multi-language support

---

**Made with ❤️ for better healthcare data management**

*This project demonstrates practical application of blockchain technology in healthcare, providing security, transparency, and patient control over medical records.*
