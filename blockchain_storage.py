"""
Blockchain Storage Module - Storacha CLI Upload + Polygon Amoy
Author: ChatGPT
"""

import os
import json
import time
import tempfile
import subprocess
import re
import requests
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict
from bs4 import BeautifulSoup
from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

# ================================
# ENV VARIABLES
# ================================
RPC_URL = os.getenv('RPC_URL', 'https://rpc-amoy.polygon.technology/')
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
CONTRACT_ADDRESS = os.getenv('CONTRACT_ADDRESS')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
IPFS_ONLY_MODE = os.getenv('IPFS_ONLY_MODE', 'false').lower() == 'true'

# ================================
# WEB3 & BLOCKCHAIN SETUP
# ================================
w3 = Web3(Web3.HTTPProvider(RPC_URL))

def load_contract_abi():
    try:
        with open('contract_abi.json', 'r') as f:
            return json.load(f)
    except:
        return None

CONTRACT_ABI = load_contract_abi()
contract = None

if CONTRACT_ADDRESS and CONTRACT_ABI:
    try:
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=CONTRACT_ABI
        )
    except:
        contract = None

# ================================
# SIMPLE ENCRYPTION HELPERS
# ================================
def generate_encryption_key():
    """Generate a simple 32-byte key"""
    import secrets
    return secrets.token_hex(32)

def simple_encrypt(data, key):
    """Simple XOR-based encryption with key stretching"""
    if isinstance(data, str):
        data = data.encode()
    if isinstance(key, str):
        key = key.encode()
    
    # Stretch key to match data length
    key_repeated = (key * (len(data) // len(key) + 1))[:len(data)]
    
    # XOR encryption
    encrypted = bytes(a ^ b for a, b in zip(data, key_repeated))
    return encrypted

def simple_decrypt(encrypted_data, key):
    """Simple XOR-based decryption (same as encryption for XOR)"""
    if isinstance(key, str):
        key = key.encode()
    
    # Stretch key to match data length
    key_repeated = (key * (len(encrypted_data) // len(key) + 1))[:len(encrypted_data)]
    
    # XOR decryption (same operation as encryption)
    decrypted = bytes(a ^ b for a, b in zip(encrypted_data, key_repeated))
    return decrypted

def encrypt_file(file_bytes):
    """Encrypt file using simple XOR encryption"""
    if not ENCRYPTION_KEY:
        raise ValueError("Encryption key not configured. Please set ENCRYPTION_KEY in .env file")
    try:
        encrypted = simple_encrypt(file_bytes, ENCRYPTION_KEY)
        metadata = {
            "algorithm": "XOR",
            "encrypted_at": datetime.utcnow().isoformat(),
            "size": len(encrypted)
        }
        print(f"[ENCRYPT] Original: {len(file_bytes)} bytes -> Encrypted: {len(encrypted)} bytes")
        return encrypted, metadata
    except Exception as e:
        raise Exception(f"Encryption failed: {str(e)}")

def decrypt_file(encrypted_bytes):
    """Decrypt file using simple XOR decryption"""
    if not ENCRYPTION_KEY:
        raise ValueError("Encryption key not configured. Please set ENCRYPTION_KEY in .env file")
    try:
        print(f"[DECRYPT] Attempting to decrypt {len(encrypted_bytes)} bytes")
        decrypted = simple_decrypt(encrypted_bytes, ENCRYPTION_KEY)
        print(f"[DECRYPT] Successfully decrypted to {len(decrypted)} bytes")
        return decrypted
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise Exception(f"Decryption failed: {str(e)}")

# ================================
# STORACHA CLI UPLOAD
# ================================
def upload_to_storacha(file_bytes, filename):
    """
    Upload file to Storacha using --no-wrap to get direct file CID
    Returns dict with cid and filename
    """
    try:
        # Write temp file with correct filename
        tmpdir = tempfile.mkdtemp(prefix="storacha_up_")
        tmp_path = Path(tmpdir) / secure_filename(filename)
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(file_bytes)

        # Run CLI upload with --no-wrap to avoid directory wrapping
        cmd = ["storacha.cmd", "up", str(tmp_path), "--no-wrap"]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=120
        )

        # Cleanup temp file
        try:
            tmp_path.unlink(missing_ok=True)
            Path(tmpdir).rmdir()
        except:
            pass

        if proc.returncode != 0:
            raise Exception(f"Storacha CLI error: {proc.stderr}")

        # Extract CID from output
        out = proc.stdout + "\n" + proc.stderr
        
        # Try to find CID (bafy... or bafk... or bafyb...)
        m = re.search(r"(baf[a-z0-9]{50,})", out, re.IGNORECASE)
        if not m:
            # Try to find in URL format
            m2 = re.search(r"https?://\S+/(baf[a-z0-9]{50,})", out, re.IGNORECASE)
            if m2:
                cid = m2.group(1)
            else:
                raise Exception(f"Could not find CID in storacha output:\n{out}")
        else:
            cid = m.group(1)
        
        # Validate CID format
        if not cid.startswith("baf"):
            raise ValueError(f"Invalid CID extracted: {cid}")

        print(f"[UPLOAD] File CID (no-wrap): {cid}")
        return cid

    except subprocess.TimeoutExpired:
        raise Exception("Storacha CLI upload timed out")
    except FileNotFoundError:
        raise Exception("Storacha CLI not installed or not in PATH")

# ================================
# IPFS DOWNLOAD HELPERS
# ================================

# IPFS Gateways to try (ordered by reliability)
IPFS_GATEWAYS = [
    "https://{cid}.ipfs.w3s.link",
    "https://w3s.link/ipfs/{cid}",
    "https://dweb.link/ipfs/{cid}",
    "https://ipfs.io/ipfs/{cid}",
]

def download_from_ipfs(cid, filename=None):
    """
    Download from IPFS using multiple strategies:
    1. Try direct gateway URLs (works with --no-wrap uploads)
    2. Try Storacha CLI as fallback
    3. Parse directory HTML if needed
    """
    print(f"[DOWNLOAD] Downloading CID: {cid}")
    
    # Strategy 1: Try direct gateway downloads with retry logic
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*'
    }
    
    for gateway_template in IPFS_GATEWAYS:
        gateway_url = gateway_template.format(cid=cid)
        
        # Retry each gateway up to 3 times
        for attempt in range(3):
            try:
                print(f"[DOWNLOAD] Trying: {gateway_url[:60]}... (attempt {attempt + 1}/3)")
                r = requests.get(gateway_url, headers=headers, timeout=30, stream=True)
                r.raise_for_status()
                
                content_type = r.headers.get('Content-Type', '')
                
                # Check if we got actual file content (not HTML)
                if 'text/html' not in content_type:
                    # Stream the content
                    content = b''
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            content += chunk
                    
                    # Validate it's not corrupted/HTML
                    if content.startswith(b'<!DOCTYPE') or content.startswith(b'<html'):
                        print(f"[DOWNLOAD] Got HTML error page, trying next...")
                        break  # Try next gateway
                    
                    if len(content) < 10:
                        print(f"[DOWNLOAD] File too small ({len(content)} bytes), likely corrupted")
                        break  # Try next gateway
                    
                    print(f"[DOWNLOAD] Success! Downloaded {len(content)} bytes")
                    return content
                
                print(f"[DOWNLOAD] Got HTML content-type, trying next gateway...")
                break  # Try next gateway
                
            except Exception as e:
                print(f"[DOWNLOAD] Attempt {attempt + 1} failed: {str(e)[:80]}")
                if attempt < 2:  # Don't sleep on last attempt
                    time.sleep(1)  # Wait 1 second before retry
                continue
        
        # If all retries failed for this gateway, try next gateway
    
    # Strategy 2: Try Storacha CLI
    try:
        print(f"[DOWNLOAD] Trying Storacha CLI...")
        fd, tmp_path = tempfile.mkstemp()
        os.close(fd)
        
        proc = subprocess.run(
            ["storacha.cmd", "get", cid, "-o", tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        
        if proc.returncode == 0 and os.path.exists(tmp_path):
            with open(tmp_path, 'rb') as f:
                content = f.read()
            os.unlink(tmp_path)
            print(f"[DOWNLOAD] CLI Success! Downloaded {len(content)} bytes")
            return content
        else:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"[DOWNLOAD] CLI failed: {e}")
    
    raise Exception(f"Download failed for CID {cid} from all sources")

# ================================
# BLOCKCHAIN FUNCTIONS
# ================================
def verify_blockchain_connection():
    try:
        if not w3.is_connected():
            return False, "Not connected"

        block = w3.eth.block_number
        chain = w3.eth.chain_id
        network = "Polygon Amoy" if chain == 80002 else f"Chain {chain}"

        if contract:
            try:
                total = contract.functions.totalRecords().call()
                return True, f"{network}, Block: {block}, Records={total}"
            except:
                return True, f"{network}, Block: {block}"

        return True, f"{network}, Block: {block}"
    except Exception as e:
        return False, str(e)

def add_record_to_blockchain(cid, patient_id, metadata):
    # IPFS-only mode: Skip blockchain, return mock tx hash
    if IPFS_ONLY_MODE:
        import hashlib
        mock_tx = hashlib.sha256(f"{cid}{patient_id}{time.time()}".encode()).hexdigest()
        print(f"[IPFS-ONLY MODE] Skipping blockchain, mock TX: {mock_tx[:16]}...")
        return f"0x{mock_tx}"
    
    if not contract:
        raise ValueError("Contract not initialized")
    acct = w3.eth.account.from_key(PRIVATE_KEY)

    meta_string = json.dumps(metadata)
    nonce = w3.eth.get_transaction_count(acct.address)

    gas_est = 300000
    try:
        gas_est = contract.functions.addRecord(cid, str(patient_id), meta_string).estimate_gas({
            "from": acct.address
        })
    except:
        pass

    tx = contract.functions.addRecord(
        cid, str(patient_id), meta_string
    ).build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "gas": int(gas_est * 1.2),
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id
    })

    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    
    # Handle both old and new web3.py versions
    try:
        raw_tx = signed.rawTransaction  # web3.py < 6.0
    except AttributeError:
        raw_tx = signed.raw_transaction  # web3.py >= 6.0
    
    tx_hash = w3.eth.send_raw_transaction(raw_tx)

    return tx_hash.hex()

def get_record_from_blockchain(index):
    r = contract.functions.getRecord(index).call()
    return {
        "cid": r[0],
        "patient_id": r[1],
        "meta": json.loads(r[2]) if r[2] else {},
        "timestamp": r[3],
        "uploader": r[4]
    }

# ================================
# CONFIG CHECKER
# ================================
def check_configuration():
    issues = []
    if not RPC_URL: issues.append("RPC_URL missing")
    if not PRIVATE_KEY: issues.append("PRIVATE_KEY missing")
    if not CONTRACT_ADDRESS: issues.append("CONTRACT_ADDRESS missing")
    if not ENCRYPTION_KEY: issues.append("ENCRYPTION_KEY missing")
    if not CONTRACT_ABI: issues.append("contract_abi.json missing or invalid")
    return len(issues) == 0, issues

# ================================
# FLASK HANDLERS
# ================================
def upload_document_handler(db, session):
    try:
        if "file" not in request.files:
            return jsonify({"status": "error", "message": "No file"}), 400

        file = request.files["file"]
        filename = secure_filename(file.filename)
        patient_id = request.form.get("patient_id")
        uploader_id = request.form.get("uploader_id")
        encrypt = request.form.get("encrypt", "false").lower() == "true"

        file_bytes = file.read()
        encryption_meta = None

        if encrypt:
            file_bytes, encryption_meta = encrypt_file(file_bytes)

        cid = upload_to_storacha(file_bytes, filename)

        metadata = {
            "encrypted": encrypt,
            "filename": filename,
            "uploader_id": uploader_id
        }

        tx_hash = add_record_to_blockchain(cid, patient_id, metadata)

        from app import PatientDocument
        doc = PatientDocument(
            patient_id=patient_id,
            uploader_id=uploader_id,
            filename=filename,
            ipfs_cid=cid,
            chain_tx=tx_hash,
            encrypted=encrypt,
            encryption_meta=json.dumps(encryption_meta) if encryption_meta else None,
            uploaded_at=datetime.utcnow(),
        )
        db.session.add(doc)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "cid": cid,
            "tx": tx_hash,
            "doc_id": doc.id,
            "encrypted": encrypt
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def get_document_handler(db, session, doc_id):
    try:
        from app import PatientDocument
        doc = PatientDocument.query.get(doc_id)

        data = download_from_ipfs(doc.ipfs_cid)

        if doc.encrypted:
            data = decrypt_file(data)

        return send_file(
            BytesIO(data),
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=doc.filename
        )
    except Exception as e:
        return jsonify({"error": str(e)})
