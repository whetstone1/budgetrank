import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import pandas as pd
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/budget_leaderboard'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Optimization 1

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Utility function to check file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    budgets = db.relationship('Budget', backref='user', lazy='dynamic')  # Optimization 2

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_income = db.Column(db.Float, nullable=False)
    total_expenses = db.Column(db.Float, nullable=False)
    savings_percentage = db.Column(db.Float, nullable=False)
    income_tier = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, total_income, total_expenses, user_id):
        self.total_income = total_income
        self.total_expenses = total_expenses
        self.savings_percentage = ((total_income - total_expenses) / total_income) * 100 if total_income > 0 else 0  # Optimization 3
        self.income_tier = self.determine_income_tier(total_income)
        self.user_id = user_id

    @staticmethod
    def determine_income_tier(income):
        if income < 50000:
            return "Below 50k"
        elif income < 100000:
            return "50k-100k"
        elif income < 150000:
            return "100k-150k"
        else:
            return "150k and above"

# Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(username=data['username'], password=hashed_password)
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except IntegrityError:  # Optimization 4
        db.session.rollback()
        return jsonify({'message': 'Username already exists'}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity=user.id)
        return jsonify({'access_token': access_token}), 200
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/budget', methods=['POST'])
@jwt_required()
def add_budget():
    user_id = get_jwt_identity()
    data = request.get_json()
    new_budget = Budget(total_income=data['total_income'], total_expenses=data['total_expenses'], user_id=user_id)
    db.session.add(new_budget)
    db.session.commit()
    return jsonify({'message': 'Budget added successfully'}), 201

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    user_id = get_jwt_identity()
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'message': 'Invalid file'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    try:
        df = pd.read_excel(filepath)
        total_income = df['Total Income'].sum()
        total_expenses = df['Total Expenses'].sum()
        new_budget = Budget(total_income=total_income, total_expenses=total_expenses, user_id=user_id)
        db.session.add(new_budget)
        db.session.commit()
        return jsonify({'message': 'File uploaded and budget added successfully'}), 201
    except Exception as e:
        return jsonify({'message': f'Error processing file: {str(e)}'}), 500

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    income_tier = request.args.get('income_tier')
    query = Budget.query.join(User).with_entities(User.username, Budget.savings_percentage)  # Optimization 5
    
    if income_tier:
        query = query.filter(Budget.income_tier == income_tier)
    
    leaderboard = query.order_by(Budget.savings_percentage.desc()).all()
    return jsonify([{'username': username, 'savings_percentage': savings_percentage} for username, savings_percentage in leaderboard]), 200

if __name__ == '__main__':
    with app.app_context():  # Optimization 6
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        db.create_all()
    app.run(debug=True)