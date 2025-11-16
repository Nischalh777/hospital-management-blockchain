# --- Main imports from Login System ---
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_ # <-- Add this import
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string
from datetime import datetime # Needed to parse date strings
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta


# --- Imports from Medical Advice App ---
import pytesseract
from PIL import Image
from dotenv import load_dotenv
from chatbot import process_text # Make sure chatbot.py is in the same directory
import google.generativeai as genai

# --- Blockchain Storage Integration ---
from blockchain_storage import (
    upload_to_storacha,
    download_from_ipfs,
    encrypt_file,
    decrypt_file,
    add_record_to_blockchain,
    verify_blockchain_connection,
    check_configuration
)
import json

# --- App Configuration ---
load_dotenv() # Load environment variables
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# --- Upload Folder Configuration (from Medical Advice App) ---
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB max file size

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Ensure the upload folder exists

# --- Tesseract Configuration (from Medical Advice App) ---
# Make sure to adjust this path if yours is different
try:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"
except Exception:
    print("WARNING: Tesseract not found at C:\\Program Files\\Tesseract-OCR\\tesseract.exe. OCR will fail.")
    print("Please install Tesseract OCR and/or update the path in app.py if you need OCR functionality.")


# --- Database Configuration (MySQL) ---
USER = 'root'
PASSWORD = ''
HOST = '127.0.0.1' # Use 127.0.0.1 for Windows development
PORT = 3306
DATABASE_NAME = 'hospital_db'

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# --- Database Models (No Changes Here) ---
class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    address = db.Column(db.String(200))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    doctors = db.relationship('Doctor', backref='hospital', lazy=True)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(15), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    specialization = db.Column(db.String(100))
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    profiles = db.relationship('PatientProfile', backref='patient', lazy=True)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class PatientProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profile_name = db.Column(db.String(100), nullable=False)
    # --- ADD THESE TWO NEW COLUMNS ---
    date_of_birth = db.Column(db.Date, nullable=True)
    aadhar_no = db.Column(db.String(12), unique=True, nullable=True) # Aadhar is 12 digits
    # --- END OF ADDED COLUMNS ---
    age = db.Column(db.Integer) # You can keep or remove this
    gender = db.Column(db.String(10))
    medical_history = db.Column(db.Text)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
# --- Add this new model to your app.py ---

# In app.py

class PatientDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    
    # --- Doctor relationship ---
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=True)
    doctor = db.relationship('Doctor', backref='uploaded_documents')
    
    # --- BLOCKCHAIN INTEGRATION COLUMNS ---
    ipfs_cid = db.Column(db.String(100), nullable=True)  # IPFS Content ID
    chain_tx = db.Column(db.String(100), nullable=True)  # Blockchain transaction hash
    encrypted = db.Column(db.Boolean, default=False)  # Whether file is encrypted
    encryption_meta = db.Column(db.Text, nullable=True)  # Encryption metadata JSON
    blockchain_enabled = db.Column(db.Boolean, default=False)  # Whether this doc uses blockchain
    # --- END OF BLOCKCHAIN COLUMNS ---
    
    patient = db.relationship('Patient', backref=db.backref('documents', lazy=True))
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    patient_email = db.Column(db.String(120), nullable=False)
    patient_phone = db.Column(db.String(20), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(10), nullable=False)
    reason_for_visit = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Booked')
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    # --- ADD THIS NEW COLUMN AND RELATIONSHIP ---
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    patient = db.relationship('Patient', backref='appointments')
    # --- END OF ADDED COLUMN ---
    doctor = db.relationship('Doctor', backref='appointments')

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    record_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=False) # Doctor's diagnosis, notes
    prescription = db.Column(db.Text, nullable=True) # Medication details
    
    # Foreign keys to link the record
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), unique=True, nullable=False) # Each record is for one specific appointment

    # Relationships
    doctor = db.relationship('Doctor', backref='medical_records')
    patient = db.relationship('Patient', backref='medical_records')
    appointment = db.relationship('Appointment', backref=db.backref('medical_record', uselist=False))

# --- MERGED ROUTES START HERE ---
def generate_password(length=8):
    """Generates a random password."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))


# --- Routes for the Medical Advice / Main Landing Page ---
@app.route('/')
def index():
    # This is the main landing page of your whole project.
    # It used to be your separate "index.html" for the advice app.
    return render_template("index.html")

@app.route("/medical_advice")
def medical_advice():
    return render_template("medical_advice.html")

@app.route("/inperson")
def inperson():
    hospitals = Hospital.query.order_by(Hospital.name).all()
    return render_template("inperson.html", hospitals=hospitals)


@app.route("/upload", methods=["POST"])
def upload_file():
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(filepath)
            try:
                image = Image.open(filepath)
                extracted_text = pytesseract.image_to_string(image)
                response = process_text(extracted_text)
                return jsonify({"text": extracted_text, "response": response})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    return jsonify({"error": "No file uploaded"}), 400

@app.route('/upload_document', methods=['POST'])
def upload_document():
    if session.get('user_type') != 'patient' or 'user_id' not in session:
        flash('You must be logged in as a patient to upload documents.', 'danger')
        return redirect(url_for('patient_login'))

    if 'document' not in request.files:
        flash('No file part in the request.', 'danger')
        return redirect(url_for('patient_dashboard'))
        
    file = request.files['document']
    doc_type = request.form.get('document_type')
    use_blockchain = request.form.get('use_blockchain', 'false').lower() == 'true'
    encrypt_file_flag = request.form.get('encrypt', 'false').lower() == 'true'

    if file.filename == '':
        flash('No selected file.', 'warning')
        return redirect(url_for('patient_dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{session['user_id']}_{int(datetime.now().timestamp())}_{filename}"
        
        original_file_bytes = file.read()
        file_bytes_to_store = original_file_bytes
        ipfs_cid = None
        chain_tx = None
        encryption_meta = None
        actually_encrypted = False
        
        # --- BLOCKCHAIN STORAGE LOGIC ---
        if use_blockchain:
            try:
                # Encrypt if requested
                if encrypt_file_flag:
                    print(f"[UPLOAD] Encrypting file: {unique_filename}")
                    file_bytes_to_store, encryption_meta = encrypt_file(original_file_bytes)
                    actually_encrypted = True
                    print(f"[UPLOAD] Encrypted: {len(original_file_bytes)} → {len(file_bytes_to_store)} bytes")
                
                # Upload to IPFS via Storacha
                print(f"[UPLOAD] Uploading to IPFS...")
                ipfs_cid = upload_to_storacha(file_bytes_to_store, unique_filename)
                print(f"[UPLOAD] Uploaded to IPFS: {ipfs_cid}")
                
                # Record on blockchain
                metadata = {
                    "encrypted": actually_encrypted,
                    "filename": unique_filename,
                    "document_type": doc_type,
                    "uploader_type": "patient",
                    "uploader_id": session['user_id']
                }
                chain_tx = add_record_to_blockchain(ipfs_cid, session['user_id'], metadata)
                print(f"[UPLOAD] Blockchain TX: {chain_tx}")
                
                flash(f'Document uploaded to blockchain! CID: {ipfs_cid[:20]}... | TX: {chain_tx[:20]}...', 'success')
                
            except Exception as e:
                print(f"[UPLOAD ERROR] Blockchain upload failed: {e}")
                import traceback
                traceback.print_exc()
                flash(f'Blockchain upload failed: {str(e)}. Saving locally instead.', 'warning')
                use_blockchain = False
                # Reset to original unencrypted data for local storage
                file_bytes_to_store = original_file_bytes
                actually_encrypted = False
        
        # --- LOCAL STORAGE (fallback or if blockchain not used) ---
        if not use_blockchain:
            # Save locally (always unencrypted for local storage)
            with open(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename), 'wb') as f:
                f.write(file_bytes_to_store)
            flash('Document uploaded successfully!', 'success')
        
        # --- SAVE TO DATABASE ---
        new_document = PatientDocument(
            filename=unique_filename,
            document_type=doc_type,
            patient_id=session['user_id'],
            ipfs_cid=ipfs_cid,
            chain_tx=chain_tx,
            encrypted=actually_encrypted,  # Only True if actually encrypted AND uploaded to blockchain
            encryption_meta=json.dumps(encryption_meta) if encryption_meta else None,
            blockchain_enabled=use_blockchain
        )
        db.session.add(new_document)
        db.session.commit()
        
        print(f"[UPLOAD] Saved to database: ID={new_document.id}, encrypted={actually_encrypted}, blockchain={use_blockchain}")
        
    else:
        flash('File type not allowed.', 'danger')
        
    return redirect(url_for('patient_dashboard'))


# This is an API endpoint that your JavaScript will call
@app.route('/api/doctors/<int:hospital_id>')
def get_doctors_for_hospital(hospital_id):
    doctors = Doctor.query.filter_by(hospital_id=hospital_id).all()
    
    # Convert the list of doctor objects into a list of dictionaries
    doctor_list = []
    for doctor in doctors:
        doctor_list.append({
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization
            # Add any other doctor info you want to display
        })
    
    return jsonify(doctors=doctor_list)


# --- ADD this new route to your app.py ---
# This route handles the form submission
# --- REPLACE your old /book_appointment route with this ---
@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    try:
        data = request.get_json()
        phone = data['phone']
        email = data['email']
        
        # Check if patient already exists by phone or email
        patient = Patient.query.filter((Patient.phone == phone) | (Patient.email == email)).first()
        
        # --- LOGIC CHANGE: We no longer need a generated password ---
        # The password will be their Date of Birth string 'YYYY-MM-DD'
        
        if not patient:
            # --- This is a NEW patient, create an account for them ---
            dob_string = data['dob'] # The password is the DOB string from the form
            
            if not dob_string:
                return jsonify({'success': False, 'message': 'Date of Birth is required for new patients.'}), 400

            # Create the main patient record for login
            new_patient = Patient(
                name=data['firstName'] + ' ' + data.get('lastName', ''),
                phone=phone,
                email=email
            )
            # --- CRITICAL CHANGE: Set password to the DOB string ---
            new_patient.set_password(dob_string) 
            db.session.add(new_patient)
            
            # --- CRITICAL FIX: Create the PatientProfile at the same time ---
            # We need to flush to get the new_patient.id before committing
            db.session.flush() 
            
            new_profile = PatientProfile(
                profile_name=f"{new_patient.name}'s Profile",
                date_of_birth=datetime.strptime(dob_string, '%Y-%m-%d').date(),
                aadhar_no=data.get('aadhar') if data.get('aadhar') else None,
                patient_id=new_patient.id
            )
            db.session.add(new_profile)
            patient = new_patient # Set the patient object to the newly created one
        
        # --- Create the appointment for either the new or existing patient ---
        new_appointment = Appointment(
            patient_name=data['firstName'] + ' ' + data.get('lastName', ''),
            patient_email=email,
            patient_phone=phone,
            appointment_date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
            appointment_time=data['time'],
            reason_for_visit=data.get('reason', ''),
            doctor_id=data['doctorId'],
            patient_id=patient.id
        )
        
        db.session.add(new_appointment)
        db.session.commit()
        
        # --- LOGIC CHANGE: Update the response to the user ---
        response_data = {
            'success': True, 
            'message': 'Appointment booked successfully!',
            'new_user': (not patient.profiles) # True if a new user was just created
        }
            
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        print(f"Error booking appointment: {e}")
        return jsonify({'success': False, 'message': 'An error occurred. Please check your details and try again.'}), 500
# --- THE CRITICAL CHANGE: THE LOGIN ROUTE ---
@app.route("/login")
def login():
    # When a user clicks a "Login" button on your main page,
    # this redirects them to the start of the hospital login system.
    return redirect(url_for('hospital_selection'))


# --- Routes for the Hospital/Doctor/Patient Login System ---
@app.route('/hospitals')
def hospital_selection():
    hospitals = Hospital.query.all()
    return render_template('hospital_selection.html', hospitals=hospitals)

@app.route('/hospital_register', methods=['GET', 'POST'])
def hospital_register():
    if request.method == 'POST':
        name, address, email, password = request.form.get('name'), request.form.get('address'), request.form.get('email'), request.form.get('password')
        if Hospital.query.filter_by(email=email).first():
            flash('This email is already registered.')
            return redirect(url_for('hospital_register'))
        new_hospital = Hospital(name=name, address=address, email=email)
        new_hospital.set_password(password)
        db.session.add(new_hospital)
        db.session.commit()
        flash('Hospital registered successfully! Please log in.')
        return redirect(url_for('hospital_login'))
    return render_template('hospital_register.html')

@app.route('/hospital_login', methods=['GET', 'POST'])
def hospital_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        hospital = Hospital.query.filter_by(email=email).first()
        if hospital and hospital.check_password(password):
            session['user_id'] = hospital.id
            session['user_type'] = 'hospital'
            return redirect(url_for('doctor_register'))
        else:
            flash('Invalid hospital credentials.')
    return render_template('hospital_login.html')

# --- Doctor Routes ---
@app.route('/doctor_register', methods=['GET', 'POST'])
def doctor_register():
    if session.get('user_type') != 'hospital':
        flash('Please log in as a hospital to register doctors.')
        return redirect(url_for('hospital_login'))
    if request.method == 'POST':
        name, email, phone, password, specialization = request.form.get('name'), request.form.get('email'), request.form.get('phone'), request.form.get('password'), request.form.get('specialization')
        hospital_id = session.get('user_id')
        if Doctor.query.filter((Doctor.email == email) | (Doctor.phone == phone)).first():
            flash('Email or phone already registered.')
            return redirect(url_for('doctor_register'))
        doctor = Doctor(name=name, email=email, phone=phone, specialization=specialization, hospital_id=hospital_id)
        doctor.set_password(password)
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor registered successfully!')
        return redirect(url_for('doctor_register'))
    hospital = Hospital.query.get(session.get('user_id'))
    return render_template('doctor_register.html', hospital=hospital)

@app.route('/doctor_login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')
        doctor = Doctor.query.filter((Doctor.email == identifier) | (Doctor.phone == identifier)).first()
        if doctor and doctor.check_password(password):
            session['user_id'] = doctor.id
            session['user_type'] = 'doctor'
            return redirect(url_for('doctor_dashboard'))
        else:
            flash('Invalid doctor credentials.')
    return render_template('doctor_login.html')

# --- MODIFY your existing /doctor_dashboard route ---
@app.route('/doctor_dashboard')
def doctor_dashboard():
    if session.get('user_type') != 'doctor':
        return redirect(url_for('doctor_login'))
        
    doctor_id = session.get('user_id')
    doctor = Doctor.query.get(doctor_id)
    
    # --- NEW LOGIC TO FETCH APPOINTMENTS ---
    # Order by date and time to show upcoming appointments first
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date >= datetime.utcnow().date()
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).all()
    
    return render_template(
        'doctor_dashboard.html', 
        doctor=doctor,
        appointments=upcoming_appointments
    )
# --- Patient Routes (Password-based, No OTP) ---
@app.route('/patient_register', methods=['GET', 'POST'])
def patient_register():
    if request.method == 'POST':
        name, phone, email, password = request.form.get('name'), request.form.get('phone'), request.form.get('email'), request.form.get('password')
        if Patient.query.filter((Patient.phone == phone) | (Patient.email == email)).first():
            flash('Phone number or email already registered.')
            return redirect(url_for('patient_register'))
        patient = Patient(name=name, phone=phone, email=email)
        patient.set_password(password)
        db.session.add(patient)
        profile = PatientProfile(profile_name=f"{name}'s Profile", age=request.form.get('age'), gender=request.form.get('gender'), patient=patient)
        db.session.add(profile)
        db.session.commit()
        flash('Registration successful! Please log in.')
        return redirect(url_for('patient_login'))
    return render_template('patient_register.html')

# --- REPLACE your old patient_login function with this new one ---
# --- REPLACE your old patient_login route with this ---
@app.route('/patient_login', methods=['GET', 'POST'])
def patient_login():
    if request.method == 'POST':
        identifier = request.form.get('identifier')
        dob_string = request.form.get('dob') # The password is the DOB string 'YYYY-MM-DD'

        if not identifier or not dob_string:
            flash('Please provide both your identifier and date of birth.', 'warning')
            return redirect(url_for('patient_login'))

        # Find the patient by their email or phone
        patient = Patient.query.filter(or_(Patient.email == identifier, Patient.phone == identifier)).first()

        # --- CRITICAL CHANGE: Check the password hash ---
        # We check if a patient was found AND if their hashed password matches the dob_string
        if patient and patient.check_password(dob_string):
            # Login successful
            session['user_id'] = patient.id
            session['user_type'] = 'patient'
            
            if len(patient.profiles) > 1:
                return redirect(url_for('select_profile'))
            else:
                session['profile_id'] = patient.profiles[0].id
                return redirect(url_for('patient_dashboard'))
        else:
            # If no match or password check fails, the credentials are wrong
            flash('Invalid credentials. Please check your details and try again.', 'danger')
            return redirect(url_for('patient_login'))
            
    return render_template('patient_login.html')
# --- Shared & Profile Routes ---
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('hospital_selection'))

@app.route('/patient_dashboard')
def patient_dashboard():
    if 'user_id' not in session or session.get('user_type') != 'patient':
        return redirect(url_for('login_selection'))

    if 'profile_id' not in session:
        return redirect(url_for('select_profile'))

    patient = Patient.query.get(session.get('user_id'))
    active_profile = PatientProfile.query.get(session.get('profile_id'))
    
    # --- NEW LOGIC TO FETCH DOCUMENTS ---
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    
    # Check if the patient has any recent appointments
    has_recent_appointment = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        Appointment.appointment_date >= (datetime.utcnow().date() - timedelta(days=3))
    ).first()

    # Fetch documents uploaded within the last 3 days
    recent_documents = PatientDocument.query.filter(
        PatientDocument.patient_id == patient.id,
        PatientDocument.upload_date >= three_days_ago
    ).order_by(PatientDocument.upload_date.desc()).all()
    
    # --- END OF NEW LOGIC ---

    return render_template(
        'patient_dashboard.html', 
        patient=patient, 
        profile=active_profile,
        has_recent_appointment=has_recent_appointment,
        documents=recent_documents
    )

# --- ADD a new route to serve the uploaded files securely ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # Security check: ensure only logged-in users can access files
    if 'user_id' not in session:
        return "Access denied", 403
    
    # Find the document in the database
    if session.get('user_type') == 'patient':
        doc = PatientDocument.query.filter_by(filename=filename, patient_id=session['user_id']).first()
    elif session.get('user_type') == 'doctor':
        # Doctors can access files for their patients
        doc = PatientDocument.query.filter_by(filename=filename).first()
        if doc:
            # Verify doctor has appointment with this patient
            appointment = Appointment.query.filter_by(
                doctor_id=session['user_id'],
                patient_id=doc.patient_id
            ).first()
            if not appointment:
                return "Access denied", 403
    else:
        return "Access denied", 403
    
    if not doc:
        return "File not found or access denied", 404
    
    # --- BLOCKCHAIN DOWNLOAD LOGIC ---
    if doc.blockchain_enabled and doc.ipfs_cid:
        try:
            # Download from IPFS
            file_data = download_from_ipfs(doc.ipfs_cid)
            
            # Decrypt if encrypted
            if doc.encrypted:
                file_data = decrypt_file(file_data)
            
            # Determine mimetype based on file extension
            import mimetypes
            mimetype, _ = mimetypes.guess_type(doc.filename)
            if not mimetype:
                mimetype = 'application/octet-stream'
            
            # Return file from memory
            from io import BytesIO
            return send_file(
                BytesIO(file_data),
                mimetype=mimetype,
                as_attachment=False,  # Allow browser to display if possible
                download_name=doc.filename
            )
        except Exception as e:
            flash(f'Blockchain download failed: {str(e)}. File may still be propagating (wait 2-3 minutes).', 'warning')
            # Fall back to local file if available
    
    # --- LOCAL FILE DOWNLOAD ---
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    # --- FALLBACK: Try IPFS if local file doesn't exist ---
    if doc.ipfs_cid:
        try:
            file_data = download_from_ipfs(doc.ipfs_cid)
            if doc.encrypted:
                file_data = decrypt_file(file_data)
            
            import mimetypes
            mimetype, _ = mimetypes.guess_type(doc.filename)
            if not mimetype:
                mimetype = 'application/octet-stream'
            
            from io import BytesIO
            return send_file(
                BytesIO(file_data),
                mimetype=mimetype,
                as_attachment=False,
                download_name=doc.filename
            )
        except Exception as e:
            return f"Error: File not found: {str(e)}", 404
    
    return "File not found", 404

@app.route('/view_document/<int:doc_id>')
def view_document(doc_id):
    """View document inline (for images and PDFs)"""
    if 'user_id' not in session:
        return "Access denied", 403
    
    # Find the document in the database
    if session.get('user_type') == 'patient':
        doc = PatientDocument.query.filter_by(id=doc_id, patient_id=session['user_id']).first()
    elif session.get('user_type') == 'doctor':
        doc = PatientDocument.query.get(doc_id)
        if doc:
            # Verify doctor has appointment with this patient
            appointment = Appointment.query.filter_by(
                doctor_id=session['user_id'],
                patient_id=doc.patient_id
            ).first()
            if not appointment:
                return "Access denied", 403
    else:
        return "Access denied", 403
    
    if not doc:
        return "Document not found or access denied", 404
    
    # --- BLOCKCHAIN DOWNLOAD LOGIC ---
    if doc.blockchain_enabled and doc.ipfs_cid:
        try:
            # Download from IPFS
            print(f"[DEBUG] Downloading from IPFS: {doc.ipfs_cid}")
            file_data = download_from_ipfs(doc.ipfs_cid)
            print(f"[DEBUG] Downloaded {len(file_data)} bytes")
            
            # Decrypt if encrypted
            if doc.encrypted:
                print(f"[DEBUG] File is encrypted, decrypting...")
                try:
                    file_data = decrypt_file(file_data)
                    print(f"[DEBUG] Decrypted successfully, {len(file_data)} bytes")
                except Exception as decrypt_error:
                    print(f"[ERROR] Decryption failed: {decrypt_error}")
                    return f"Error decrypting document: {str(decrypt_error)}", 500
            
            # Determine mimetype based on file extension
            import mimetypes
            mimetype, _ = mimetypes.guess_type(doc.filename)
            if not mimetype:
                mimetype = 'application/octet-stream'
            
            print(f"[DEBUG] Serving file with mimetype: {mimetype}")
            
            # Return file from memory for inline viewing
            from io import BytesIO
            return send_file(
                BytesIO(file_data),
                mimetype=mimetype,
                as_attachment=False,
                download_name=doc.filename
            )
        except Exception as e:
            print(f"[ERROR] Error loading document: {e}")
            import traceback
            traceback.print_exc()
            return f"Error loading document: {str(e)}", 500
    
    # --- LOCAL FILE VIEWING ---
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
    if os.path.exists(filepath):
        import mimetypes
        mimetype, _ = mimetypes.guess_type(doc.filename)
        if not mimetype:
            mimetype = 'application/octet-stream'
        return send_from_directory(app.config['UPLOAD_FOLDER'], doc.filename, mimetype=mimetype)
    
    # --- FALLBACK: Try IPFS if local file doesn't exist but CID is available ---
    if doc.ipfs_cid:
        try:
            print(f"[DEBUG] Local file not found, downloading from IPFS: {doc.ipfs_cid}")
            file_data = download_from_ipfs(doc.ipfs_cid)
            
            if doc.encrypted:
                file_data = decrypt_file(file_data)
            
            import mimetypes
            mimetype, _ = mimetypes.guess_type(doc.filename)
            if not mimetype:
                mimetype = 'application/octet-stream'
            
            from io import BytesIO
            return send_file(
                BytesIO(file_data),
                mimetype=mimetype,
                as_attachment=False,
                download_name=doc.filename
            )
        except Exception as e:
            print(f"[ERROR] IPFS fallback failed: {e}")
            return f"Error: File not found locally or on IPFS: {str(e)}", 404
    
    return "File not found", 404
@app.route('/select_profile')
def select_profile():
    if session.get('user_type') != 'patient':
        return redirect(url_for('patient_login'))
    patient = Patient.query.get(session.get('user_id'))
    return render_template('select_profile.html', profiles=patient.profiles)

@app.route('/set_profile/<int:profile_id>')
def set_profile(profile_id):
    if session.get('user_type') != 'patient':
        return redirect(url_for('patient_login'))
    profile = PatientProfile.query.get(profile_id)
    if profile and profile.patient_id == session.get('user_id'):
        session['profile_id'] = profile_id
        return redirect(url_for('patient_dashboard'))
    flash('Invalid profile selected.')
    return redirect(url_for('select_profile'))
@app.route('/doctor/view_patient/<int:patient_id>/from_appt/<int:appointment_id>')
def view_patient_details(patient_id, appointment_id):
    # --- Security Check 1: Ensure user is a doctor ---
    if session.get('user_type') != 'doctor':
        flash("Access denied.", "danger")
        return redirect(url_for('doctor_login'))

    doctor_id = session.get('user_id')

    # --- Security Check 2: Ensure this patient has an appointment with THIS doctor ---
    appointment = Appointment.query.filter_by(
        id=appointment_id, 
        doctor_id=doctor_id, 
        patient_id=patient_id
    ).first()

    if not appointment:
        flash("You do not have permission to view this patient's records.", "danger")
        return redirect(url_for('doctor_dashboard'))

    # If security checks pass, fetch all patient data
    patient = Patient.query.get_or_404(patient_id)
    
    # Fetch all of the patient's past documents and medical records (notes from doctors)
    past_documents = PatientDocument.query.filter_by(patient_id=patient_id).order_by(PatientDocument.upload_date.desc()).all()
    past_medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.record_date.desc()).all()

    return render_template(
        'view_patient.html', 
        patient=patient,
        appointment=appointment,
        past_documents=past_documents,
        past_medical_records=past_medical_records
    )

@app.route('/doctor/add_medical_record', methods=['POST'])
def add_medical_record():
    # Security Check
    if session.get('user_type') != 'doctor':
        return "Access Denied", 403

    doctor_id = session.get('user_id')
    patient_id = request.form.get('patient_id')
    appointment_id = request.form.get('appointment_id')
    notes = request.form.get('notes')
    prescription = request.form.get('prescription')
    
    # Verify this doctor is allowed to add a record for this appointment
    appointment = Appointment.query.filter_by(id=appointment_id, doctor_id=doctor_id, patient_id=patient_id).first()
    if not appointment:
        flash("Invalid request.", "danger")
        return redirect(url_for('doctor_dashboard'))
        
    # Check if a record already exists for this appointment
    if appointment.medical_record:
        flash("A medical record for this appointment already exists.", "warning")
        return redirect(url_for('view_patient_details', patient_id=patient_id, appointment_id=appointment_id))

    # Create and save the new medical record
    new_record = MedicalRecord(
        notes=notes,
        prescription=prescription,
        doctor_id=doctor_id,
        patient_id=patient_id,
        appointment_id=appointment_id
    )
    db.session.add(new_record)
    db.session.commit()

    flash("Medical record added successfully.", "success")
    return redirect(url_for('view_patient_details', patient_id=patient_id, appointment_id=appointment_id))



# --- Initialize the OpenAI client right after your app config ---
# It will automatically read the OPENAI_API_KEY from your .env file
# Get API key from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
    # Initialize the Gemini model to be used for analysis
    gemini_model = genai.GenerativeModel("gemini-2.5-flash") 
    print("Gemini configured successfully.")
except Exception as e:
    gemini_model = None
    print(f"WARNING: Could not configure Gemini. Analysis will fail. Error: {e}")
# --- END OF GEMINI CONFIG BLOCK ---


# --- ADD THIS NEW ROUTE for the doctor to upload files ---
@app.route('/doctor/upload_for_patient', methods=['POST'])
def doctor_upload_for_patient():
    if session.get('user_type') != 'doctor':
        return "Access Denied", 403

    patient_id = request.form.get('patient_id')
    doc_type = request.form.get('document_type')
    file = request.files.get('document')
    use_blockchain = request.form.get('use_blockchain', 'false').lower() == 'true'
    encrypt_file_flag = request.form.get('encrypt', 'false').lower() == 'true'
    
    # Security: Verify this doctor is allowed to upload for this patient
    appointment_exists = Appointment.query.filter_by(
        doctor_id=session['user_id'],
        patient_id=patient_id
    ).first()

    if not appointment_exists:
        flash("You do not have permission to upload documents for this patient.", "danger")
        return redirect(url_for('doctor_dashboard'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"doc_{patient_id}_{int(datetime.now().timestamp())}_{filename}"
        
        original_file_bytes = file.read()
        file_bytes_to_store = original_file_bytes
        ipfs_cid = None
        chain_tx = None
        encryption_meta = None
        actually_encrypted = False
        
        # --- BLOCKCHAIN STORAGE LOGIC ---
        if use_blockchain:
            try:
                # Encrypt if requested
                if encrypt_file_flag:
                    print(f"[DOCTOR UPLOAD] Encrypting file: {unique_filename}")
                    file_bytes_to_store, encryption_meta = encrypt_file(original_file_bytes)
                    actually_encrypted = True
                    print(f"[DOCTOR UPLOAD] Encrypted: {len(original_file_bytes)} → {len(file_bytes_to_store)} bytes")
                
                # Upload to IPFS via Storacha
                print(f"[DOCTOR UPLOAD] Uploading to IPFS...")
                ipfs_cid = upload_to_storacha(file_bytes_to_store, unique_filename)
                print(f"[DOCTOR UPLOAD] Uploaded to IPFS: {ipfs_cid}")
                
                # Record on blockchain
                metadata = {
                    "encrypted": actually_encrypted,
                    "filename": unique_filename,
                    "document_type": doc_type,
                    "uploader_type": "doctor",
                    "uploader_id": session['user_id'],
                    "patient_id": patient_id
                }
                chain_tx = add_record_to_blockchain(ipfs_cid, patient_id, metadata)
                print(f"[DOCTOR UPLOAD] Blockchain TX: {chain_tx}")
                
                flash(f'Document uploaded to blockchain! CID: {ipfs_cid[:20]}...', 'success')
                
            except Exception as e:
                print(f"[DOCTOR UPLOAD ERROR] Blockchain upload failed: {e}")
                import traceback
                traceback.print_exc()
                flash(f'Blockchain upload failed: {str(e)}. Saving locally instead.', 'warning')
                use_blockchain = False
                # Reset to original unencrypted data for local storage
                file_bytes_to_store = original_file_bytes
                actually_encrypted = False
        
        # --- LOCAL STORAGE (fallback or if blockchain not used) ---
        if not use_blockchain:
            with open(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename), 'wb') as f:
                f.write(file_bytes_to_store)
            flash('Document uploaded successfully!', 'success')
        
        # --- SAVE TO DATABASE ---
        new_document = PatientDocument(
            filename=unique_filename,
            document_type=doc_type,
            patient_id=patient_id,
            doctor_id=session['user_id'],
            ipfs_cid=ipfs_cid,
            chain_tx=chain_tx,
            encrypted=actually_encrypted,  # Only True if actually encrypted AND uploaded to blockchain
            encryption_meta=json.dumps(encryption_meta) if encryption_meta else None,
            blockchain_enabled=use_blockchain
        )
        db.session.add(new_document)
        db.session.commit()
        
        print(f"[DOCTOR UPLOAD] Saved to database: ID={new_document.id}, encrypted={actually_encrypted}, blockchain={use_blockchain}")
    else:
        flash('Invalid file or file type.', 'danger')
        
    return redirect(url_for('view_patient_details', patient_id=patient_id, appointment_id=appointment_exists.id))


# --- REPLACE your entire old /analyze_document route with this ---
import fitz # PyMuPDF

# --- BLOCKCHAIN STATUS AND INFO ROUTES ---
@app.route('/blockchain/status')
def blockchain_status():
    """Check blockchain connection status"""
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 403
    
    try:
        connected, message = verify_blockchain_connection()
        config_ok, issues = check_configuration()
        
        # Check encryption key
        from blockchain_storage import cipher_suite, ENCRYPTION_KEY
        encryption_ok = cipher_suite is not None and ENCRYPTION_KEY is not None
        
        return jsonify({
            "connected": connected,
            "message": message,
            "config_ok": config_ok,
            "issues": issues if not config_ok else [],
            "encryption_configured": encryption_ok,
            "encryption_key_length": len(ENCRYPTION_KEY) if ENCRYPTION_KEY else 0
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/debug/document/<int:doc_id>')
def debug_document(doc_id):
    """Debug endpoint to check document details"""
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 403
    
    # Find document
    if session.get('user_type') == 'patient':
        doc = PatientDocument.query.filter_by(id=doc_id, patient_id=session['user_id']).first()
    elif session.get('user_type') == 'doctor':
        doc = PatientDocument.query.get(doc_id)
    else:
        return jsonify({"error": "Access denied"}), 403
    
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    return jsonify({
        "id": doc.id,
        "filename": doc.filename,
        "document_type": doc.document_type,
        "encrypted": doc.encrypted,
        "blockchain_enabled": doc.blockchain_enabled,
        "ipfs_cid": doc.ipfs_cid,
        "chain_tx": doc.chain_tx,
        "upload_date": doc.upload_date.isoformat() if doc.upload_date else None,
        "patient_id": doc.patient_id,
        "doctor_id": doc.doctor_id
    })

@app.route('/debug')
def debug_panel():
    """Debug panel for testing"""
    if 'user_id' not in session:
        flash('Please log in to access debug panel', 'warning')
        return redirect(url_for('patient_login'))
    return render_template('debug_panel.html')

@app.route('/document/<int:doc_id>/blockchain_info')
def document_blockchain_info(doc_id):
    """Get blockchain information for a specific document"""
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 403
    
    # Find document and verify access
    if session.get('user_type') == 'patient':
        doc = PatientDocument.query.filter_by(id=doc_id, patient_id=session['user_id']).first()
    elif session.get('user_type') == 'doctor':
        doc = PatientDocument.query.get(doc_id)
        if doc:
            appointment = Appointment.query.filter_by(
                doctor_id=session['user_id'],
                patient_id=doc.patient_id
            ).first()
            if not appointment:
                return jsonify({"error": "Access denied"}), 403
    else:
        return jsonify({"error": "Access denied"}), 403
    
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    if not doc.blockchain_enabled:
        return jsonify({"blockchain_enabled": False})
    
    return jsonify({
        "blockchain_enabled": True,
        "ipfs_cid": doc.ipfs_cid,
        "chain_tx": doc.chain_tx,
        "encrypted": doc.encrypted,
        "ipfs_url": f"https://w3s.link/ipfs/{doc.ipfs_cid}" if doc.ipfs_cid else None,
        "polygonscan_url": f"https://amoy.polygonscan.com/tx/{doc.chain_tx}" if doc.chain_tx else None,
        "upload_date": doc.upload_date.isoformat()
    })

@app.route('/analyze_document/<int:doc_id>', methods=['POST'])
def analyze_document(doc_id):
    if session.get('user_type') != 'patient':
        return jsonify({"error": "Access Denied"}), 403

    # Security: Ensure the document belongs to the logged-in patient
    doc = PatientDocument.query.filter_by(id=doc_id, patient_id=session['user_id']).first()
    if not doc:
        return jsonify({"error": "Document not found or access denied"}), 404

    # Check if Gemini was configured correctly on startup
    if not gemini_model:
        return jsonify({"error": "AI analysis service is not configured. Please contact support."}), 500

    extracted_text = ""
    file_data = None

    try:
        # --- GET FILE DATA (from blockchain or local) ---
        temp_filepath = None
        if doc.blockchain_enabled and doc.ipfs_cid:
            try:
                # Download from IPFS
                print(f"[ANALYZE DEBUG] Downloading from IPFS: {doc.ipfs_cid}")
                file_data = download_from_ipfs(doc.ipfs_cid)
                print(f"[ANALYZE DEBUG] Downloaded {len(file_data)} bytes")
                
                # Decrypt if encrypted
                if doc.encrypted:
                    print(f"[ANALYZE DEBUG] File is encrypted, decrypting...")
                    try:
                        file_data = decrypt_file(file_data)
                        print(f"[ANALYZE DEBUG] Decrypted successfully, {len(file_data)} bytes")
                    except Exception as decrypt_error:
                        print(f"[ANALYZE ERROR] Decryption failed: {decrypt_error}")
                        import traceback
                        traceback.print_exc()
                        return jsonify({"error": f"Decryption failed: {str(decrypt_error)}"}), 500
                
                # Save temporarily for processing
                import tempfile
                file_ext = os.path.splitext(doc.filename)[1]
                temp_fd, temp_filepath = tempfile.mkstemp(suffix=file_ext)
                os.close(temp_fd)  # Close the file descriptor
                
                print(f"[ANALYZE DEBUG] Saving to temp file: {temp_filepath}")
                # Write the file data
                with open(temp_filepath, 'wb') as tmp:
                    tmp.write(file_data)
                
                filepath = temp_filepath
            except Exception as e:
                print(f"[ANALYZE ERROR] Blockchain download error: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": f"Could not download from blockchain: {str(e)}"}), 500
        else:
            # Use local file
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
            print(f"[ANALYZE DEBUG] Using local file: {filepath}")
        
        # --- Text extraction logic ---
        print(f"[ANALYZE DEBUG] Extracting text from: {doc.filename}")
        try:
            if doc.filename.lower().endswith('.pdf'):
                print(f"[ANALYZE DEBUG] Processing as PDF")
                with fitz.open(filepath) as pdf_doc:
                    for page in pdf_doc:
                        extracted_text += page.get_text()
            elif doc.filename.lower().split('.')[-1] in ['png', 'jpg', 'jpeg', 'gif']:
                print(f"[ANALYZE DEBUG] Processing as image with OCR")
                try:
                    image = Image.open(filepath)
                    print(f"[ANALYZE DEBUG] Image opened, size: {image.size}")
                    extracted_text = pytesseract.image_to_string(image)
                    print(f"[ANALYZE DEBUG] OCR extracted {len(extracted_text)} characters")
                except Exception as ocr_error:
                    print(f"[ANALYZE ERROR] OCR failed: {ocr_error}")
                    # Clean up temp file
                    if temp_filepath:
                        try:
                            os.unlink(temp_filepath)
                        except:
                            pass
                    
                    # Check if it's a Tesseract installation issue
                    if "tesseract" in str(ocr_error).lower() or "not installed" in str(ocr_error).lower():
                        return jsonify({
                            "error": "Tesseract OCR Not Installed",
                            "analysis": "**⚠️ Text Extraction Not Available**\n\nThe document analysis feature requires Tesseract OCR to extract text from images.\n\n**To enable this feature:**\n\n1. Download Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki\n2. Install it to `C:\\Program Files\\Tesseract-OCR`\n3. Restart the Flask server\n\n**Alternative:** You can still view and download the image using the View and Download buttons."
                        }), 200  # Return 200 so modal shows the message
                    else:
                        return jsonify({
                            "error": "Text extraction failed",
                            "analysis": f"**⚠️ Could not extract text from image**\n\nError: {str(ocr_error)}\n\nYou can still view and download the image using the other buttons."
                        }), 200
            else:
                # Clean up temp file before returning error
                if temp_filepath:
                    try:
                        os.unlink(temp_filepath)
                    except:
                        pass
                return jsonify({"error": "Unsupported file type for analysis."}), 400
        except Exception as extract_error:
            print(f"[ANALYZE ERROR] Text extraction failed: {extract_error}")
            import traceback
            traceback.print_exc()
            # Clean up temp file
            if temp_filepath:
                try:
                    os.unlink(temp_filepath)
                except:
                    pass
            return jsonify({"error": f"Text extraction failed: {str(extract_error)}"}), 500
        
        # Clean up temp file if we created one
        if temp_filepath:
            try:
                os.unlink(temp_filepath)
            except:
                pass
        
        if not extracted_text.strip():
            return jsonify({"analysis": "Could not find any text in the document to analyze."})

        # --- THIS IS THE NEW GEMINI LOGIC ---
        # Create the prompt for Gemini
        prompt = f"""
        You are a helpful medical assistant. Your role is to analyze a medical document for a patient and explain it in simple, easy-to-understand language. Do not provide a direct diagnosis. Use clean Markdown for formatting with headings and bullet points.

        Based on the following document text, provide a summary with these exact sections:
        
        ### Summary of Document
        Start with a brief, one-sentence summary of what this document is (e.g., "This is a report for a chest X-ray.").

        ### Key Findings
        Use a bulleted list to highlight the most important results, measurements, or observations mentioned in the report.

        ### Explanation of Terms
        Use a bulleted list to explain any complex medical terms from the findings in simple language. If there are no complex terms, state "All terms are standard."

        ### Recommendations (if mentioned)
        Use a bulleted list to summarize any next steps, precautions, or follow-up advice mentioned in the document. If none are mentioned, state "No specific recommendations were mentioned in this report."

        Here is the document text:
        ---
        {extracted_text}
        ---
        """
        
        # Send the prompt to the Gemini model
        response = gemini_model.generate_content(prompt)
        
        # Safely get the text from the response
        if response and response.candidates:
            analysis = response.candidates[0].content.parts[0].text.strip()
        else:
            analysis = "Could not get a valid analysis from the AI model."
        
        return jsonify({"analysis": analysis})
        # --- END OF NEW GEMINI LOGIC ---

    except Exception as e:
        print(f"Analysis Error: {e}")
        return jsonify({"error": "An error occurred during analysis."}), 500


# --- Main execution ---
if __name__ == '__main__':
    # Important: Before running for the first time, make sure you have:
    # 1. A MySQL database named 'hospital_db' created.
    # 2. Run the commands in your terminal to create the tables:
    #    - set FLASK_APP=app.py  (or export FLASK_APP=app.py)
    #    - flask shell
    #    - from app import db
    #    - db.create_all()
    #    - exit()
    app.run(debug=True, host='0.0.0.0')