import os
import sys
import random
import string
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///bukuya.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 5,
    'max_overflow': 0
}
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize database
db = SQLAlchemy(app)

# ============ MODELS ============

class User(db.Model, UserMixin):
    __tablename__ = 'users'  # Explicitly set table name to avoid SQL reserved word
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='staff')
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Member(db.Model):
    __tablename__ = 'members'
    id = db.Column(db.Integer, primary_key=True)
    member_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    truck_no = db.Column(db.String(20))
    email = db.Column(db.String(100))
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    share_capital = db.Column(db.Float, default=0.0)
    savings = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='active')
    
    loans = db.relationship('Loan', backref='member', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='member', lazy=True, cascade='all, delete-orphan')

class Loan(db.Model):
    __tablename__ = 'loans'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    loan_no = db.Column(db.String(20), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, default=5.0)
    period_months = db.Column(db.Integer, nullable=False)
    disbursed_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')
    balance = db.Column(db.Float)
    paid_amount = db.Column(db.Float, default=0.0)
    purpose = db.Column(db.String(200))
    total_repayable = db.Column(db.Float)
    
    repayments = db.relationship('LoanRepayment', backref='loan', lazy=True, cascade='all, delete-orphan')

class LoanRepayment(db.Model):
    __tablename__ = 'loan_repayments'
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loans.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_date = db.Column(db.DateTime, default=datetime.utcnow)
    balance_after = db.Column(db.Float)
    receipt_no = db.Column(db.String(20))

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    reference_no = db.Column(db.String(50), unique=True)

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True)
    value = db.Column(db.String(200))
    description = db.Column(db.String(200))

# ============ LOGIN MANAGER ============

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please login to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except:
        return None

# ============ HELPER FUNCTIONS ============

def generate_member_no():
    year = datetime.now().strftime('%Y')
    count = Member.query.count() + 1
    return f"BM{year}{str(count).zfill(4)}"

def generate_loan_no():
    year = datetime.now().strftime('%Y')
    count = Loan.query.count() + 1
    return f"BL{year}{str(count).zfill(4)}"

def generate_reference():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def generate_receipt_no():
    return f"RCP{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

# ============ ROUTES ============

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            if not username or not password:
                flash('Please enter both username and password.', 'danger')
                return render_template('login.html')
            
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True, duration=timedelta(days=7))
                flash(f'Welcome back, {user.name}!', 'success')
                
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password.', 'danger')
        except Exception as e:
            app.logger.error(f"Login error: {str(e)}")
            flash(f'Login error: {str(e)}', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        total_members = Member.query.count()
        active_members = Member.query.filter_by(status='active').count()
        total_loans = Loan.query.count()
        active_loans = Loan.query.filter_by(status='active').count()
        total_loan_amount = db.session.query(db.func.sum(Loan.amount)).scalar() or 0
        total_loan_balance = db.session.query(db.func.sum(Loan.balance)).scalar() or 0
        total_savings = db.session.query(db.func.sum(Member.savings)).scalar() or 0
        
        recent_transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).limit(10).all()
        recent_loans = Loan.query.order_by(Loan.disbursed_date.desc()).limit(5).all()
        
        loan_stats = db.session.query(
            Loan.status,
            db.func.count(Loan.id).label('count'),
            db.func.sum(Loan.balance).label('balance')
        ).group_by(Loan.status).all()
        
        return render_template('dashboard.html',
                             total_members=total_members,
                             active_members=active_members,
                             total_loans=total_loans,
                             active_loans=active_loans,
                             total_loan_amount=total_loan_amount,
                             total_loan_balance=total_loan_balance,
                             total_savings=total_savings,
                             recent_transactions=recent_transactions,
                             recent_loans=recent_loans,
                             loan_stats=loan_stats)
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('dashboard.html')

# ============ MEMBER ROUTES ============

@app.route('/members')
@login_required
def members():
    try:
        search = request.args.get('search', '')
        if search:
            members = Member.query.filter(
                db.or_(
                    Member.name.ilike(f'%{search}%'),
                    Member.member_no.ilike(f'%{search}%'),
                    Member.phone.ilike(f'%{search}%'),
                    Member.truck_no.ilike(f'%{search}%')
                )
            ).order_by(Member.join_date.desc()).all()
        else:
            members = Member.query.order_by(Member.join_date.desc()).all()
        
        return render_template('members.html', members=members, search=search)
    except Exception as e:
        app.logger.error(f"Members error: {str(e)}")
        flash(f'Error loading members: {str(e)}', 'danger')
        return render_template('members.html', members=[])

@app.route('/members/add', methods=['GET', 'POST'])
@login_required
def add_member():
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            phone = request.form.get('phone')
            truck_no = request.form.get('truck_no')
            email = request.form.get('email')
            share_capital = float(request.form.get('share_capital', 0))
            savings = float(request.form.get('savings', 0))
            
            member = Member(
                member_no=generate_member_no(),
                name=name,
                phone=phone,
                truck_no=truck_no,
                email=email,
                share_capital=share_capital,
                savings=savings
            )
            
            db.session.add(member)
            db.session.commit()
            flash(f'Member {name} added successfully!', 'success')
            return redirect(url_for('members'))
        except Exception as e:
            app.logger.error(f"Add member error: {str(e)}")
            flash(f'Error adding member: {str(e)}', 'danger')
    
    return render_template('add_member.html')

@app.route('/members/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_member(id):
    member = Member.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            member.name = request.form.get('name')
            member.phone = request.form.get('phone')
            member.truck_no = request.form.get('truck_no')
            member.email = request.form.get('email')
            member.share_capital = float(request.form.get('share_capital', 0))
            member.savings = float(request.form.get('savings', 0))
            member.status = request.form.get('status')
            
            db.session.commit()
            flash('Member updated successfully!', 'success')
            return redirect(url_for('members'))
        except Exception as e:
            app.logger.error(f"Edit member error: {str(e)}")
            flash(f'Error updating member: {str(e)}', 'danger')
    
    return render_template('edit_member.html', member=member)

@app.route('/members/<int:id>/delete', methods=['POST'])
@login_required
def delete_member(id):
    try:
        member = Member.query.get_or_404(id)
        if member.loans:
            flash('Cannot delete member with active loans.', 'danger')
            return redirect(url_for('members'))
        
        db.session.delete(member)
        db.session.commit()
        flash('Member deleted successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Delete member error: {str(e)}")
        flash(f'Error deleting member: {str(e)}', 'danger')
    
    return redirect(url_for('members'))

@app.route('/members/<int:id>')
@login_required
def member_detail(id):
    member = Member.query.get_or_404(id)
    return render_template('member_detail.html', member=member)

# ============ LOAN ROUTES ============

@app.route('/loans')
@login_required
def loans():
    try:
        status = request.args.get('status', 'all')
        search = request.args.get('search', '')
        
        query = Loan.query
        
        if status != 'all':
            query = query.filter_by(status=status)
        
        if search:
            query = query.join(Member).filter(
                db.or_(
                    Member.name.ilike(f'%{search}%'),
                    Member.member_no.ilike(f'%{search}%'),
                    Loan.loan_no.ilike(f'%{search}%')
                )
            )
        
        loans = query.order_by(Loan.disbursed_date.desc()).all()
        return render_template('loans.html', loans=loans, status=status, search=search)
    except Exception as e:
        app.logger.error(f"Loans error: {str(e)}")
        flash(f'Error loading loans: {str(e)}', 'danger')
        return render_template('loans.html', loans=[])

@app.route('/loans/apply', methods=['GET', 'POST'])
@login_required
def apply_loan():
    members = Member.query.filter_by(status='active').all()
    
    if request.method == 'POST':
        try:
            member_id = request.form.get('member_id')
            amount = float(request.form.get('amount'))
            interest_rate = float(request.form.get('interest_rate', 5.0))
            period_months = int(request.form.get('period_months'))
            purpose = request.form.get('purpose')
            
            member = Member.query.get(member_id)
            if not member:
                flash('Member not found.', 'danger')
                return redirect(url_for('apply_loan'))
            
            total_repayable = amount + (amount * interest_rate / 100)
            due_date = datetime.utcnow() + timedelta(days=period_months * 30)
            
            loan = Loan(
                loan_no=generate_loan_no(),
                member_id=member_id,
                amount=amount,
                interest_rate=interest_rate,
                period_months=period_months,
                due_date=due_date,
                balance=total_repayable,
                total_repayable=total_repayable,
                purpose=purpose
            )
            
            db.session.add(loan)
            
            transaction = Transaction(
                member_id=member_id,
                type='loan_disbursement',
                amount=amount,
                description=f'Loan disbursement - {loan.loan_no}',
                reference_no=generate_reference()
            )
            db.session.add(transaction)
            
            db.session.commit()
            flash(f'Loan {loan.loan_no} applied successfully!', 'success')
            return redirect(url_for('loans'))
        except Exception as e:
            app.logger.error(f"Apply loan error: {str(e)}")
            flash(f'Error applying loan: {str(e)}', 'danger')
    
    return render_template('apply_loan.html', members=members)

@app.route('/loans/<int:id>')
@login_required
def loan_detail(id):
    loan = Loan.query.get_or_404(id)
    return render_template('loan_details.html', loan=loan)

@app.route('/loans/<int:id>/repay', methods=['POST'])
@login_required
def repay_loan(id):
    try:
        loan = Loan.query.get_or_404(id)
        amount = float(request.form.get('amount'))
        
        if amount > loan.balance:
            flash('Amount exceeds loan balance.', 'danger')
            return redirect(url_for('loan_detail', id=id))
        
        repayment = LoanRepayment(
            loan_id=loan.id,
            amount=amount,
            balance_after=loan.balance - amount,
            receipt_no=generate_receipt_no()
        )
        db.session.add(repayment)
        
        loan.balance -= amount
        loan.paid_amount += amount
        
        if loan.balance <= 0:
            loan.status = 'paid'
        
        transaction = Transaction(
            member_id=loan.member_id,
            type='loan_repayment',
            amount=amount,
            description=f'Loan repayment - {loan.loan_no}',
            reference_no=generate_reference()
        )
        db.session.add(transaction)
        
        db.session.commit()
        flash(f'Payment of {amount} recorded successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Repay loan error: {str(e)}")
        flash(f'Error recording payment: {str(e)}', 'danger')
    
    return redirect(url_for('loan_detail', id=id))

@app.route('/loans/<int:id>/delete', methods=['POST'])
@login_required
def delete_loan(id):
    try:
        loan = Loan.query.get_or_404(id)
        if loan.status == 'paid':
            flash('Cannot delete paid loan.', 'danger')
            return redirect(url_for('loans'))
        
        db.session.delete(loan)
        db.session.commit()
        flash('Loan deleted successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Delete loan error: {str(e)}")
        flash(f'Error deleting loan: {str(e)}', 'danger')
    
    return redirect(url_for('loans'))

# ============ TRANSACTION ROUTES ============

@app.route('/transactions')
@login_required
def transactions():
    try:
        search = request.args.get('search', '')
        type_filter = request.args.get('type', 'all')
        
        query = Transaction.query
        
        if type_filter != 'all':
            query = query.filter_by(type=type_filter)
        
        if search:
            query = query.join(Member).filter(
                db.or_(
                    Member.name.ilike(f'%{search}%'),
                    Transaction.reference_no.ilike(f'%{search}%')
                )
            )
        
        transactions = query.order_by(Transaction.transaction_date.desc()).all()
        return render_template('transactions.html', transactions=transactions, type_filter=type_filter, search=search)
    except Exception as e:
        app.logger.error(f"Transactions error: {str(e)}")
        flash(f'Error loading transactions: {str(e)}', 'danger')
        return render_template('transactions.html', transactions=[])

@app.route('/transactions/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    members = Member.query.filter_by(status='active').all()
    
    if request.method == 'POST':
        try:
            member_id = request.form.get('member_id')
            type = request.form.get('type')
            amount = float(request.form.get('amount'))
            description = request.form.get('description')
            
            member = Member.query.get(member_id)
            if not member:
                flash('Member not found.', 'danger')
                return redirect(url_for('add_transaction'))
            
            if type == 'deposit':
                member.savings += amount
            elif type == 'withdrawal':
                if member.savings < amount:
                    flash('Insufficient savings.', 'danger')
                    return redirect(url_for('add_transaction'))
                member.savings -= amount
            
            transaction = Transaction(
                member_id=member_id,
                type=type,
                amount=amount,
                description=description,
                reference_no=generate_reference()
            )
            
            db.session.add(transaction)
            db.session.commit()
            flash('Transaction recorded successfully!', 'success')
            return redirect(url_for('transactions'))
        except Exception as e:
            app.logger.error(f"Add transaction error: {str(e)}")
            flash(f'Error adding transaction: {str(e)}', 'danger')
    
    return render_template('add_transaction.html', members=members)

# ============ REPORTS ROUTES ============

@app.route('/reports')
@login_required
def reports():
    try:
        total_loans = Loan.query.count()
        active_loans = Loan.query.filter_by(status='active').count()
        paid_loans = Loan.query.filter_by(status='paid').count()
        total_disbursed = db.session.query(db.func.sum(Loan.amount)).scalar() or 0
        total_repaid = db.session.query(db.func.sum(Loan.paid_amount)).scalar() or 0
        total_outstanding = db.session.query(db.func.sum(Loan.balance)).scalar() or 0
        
        total_members = Member.query.count()
        active_members = Member.query.filter_by(status='active').count()
        total_savings = db.session.query(db.func.sum(Member.savings)).scalar() or 0
        total_share_capital = db.session.query(db.func.sum(Member.share_capital)).scalar() or 0
        
        transaction_summary = db.session.query(
            Transaction.type,
            db.func.count(Transaction.id).label('count'),
            db.func.sum(Transaction.amount).label('total')
        ).group_by(Transaction.type).all()
        
        return render_template('reports.html',
                             total_loans=total_loans,
                             active_loans=active_loans,
                             paid_loans=paid_loans,
                             total_disbursed=total_disbursed,
                             total_repaid=total_repaid,
                             total_outstanding=total_outstanding,
                             total_members=total_members,
                             active_members=active_members,
                             total_savings=total_savings,
                             total_share_capital=total_share_capital,
                             transaction_summary=transaction_summary)
    except Exception as e:
        app.logger.error(f"Reports error: {str(e)}")
        flash(f'Error loading reports: {str(e)}', 'danger')
        return render_template('reports.html')

# ============ INIT DATABASE ============

@app.route('/init_db')
def init_db():
    try:
        db.create_all()
        
        admin = User.query.filter_by(username='manager').first()
        if not admin:
            admin = User(
                username='manager',
                password=generate_password_hash('Manager@2026'),
                role='admin',
                name='System Manager'
            )
            db.session.add(admin)
            db.session.commit()
            return jsonify({'message': 'Database initialized with admin user!'})
        else:
            return jsonify({'message': 'Admin user already exists!'})
    except Exception as e:
        app.logger.error(f"Init DB error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f"500 error: {str(error)}")
    return render_template('500.html'), 500

# ============ MAIN ============

if __name__ == '__main__':
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            
            # Create admin user if not exists
            admin = User.query.filter_by(username='manager').first()
            if not admin:
                admin = User(
                    username='manager',
                    password=generate_password_hash('Manager@2026'),
                    role='admin',
                    name='System Manager'
                )
                db.session.add(admin)
                db.session.commit()
                print("=" * 50)
                print("✅ BUKUYA Driver's SACCO System")
                print("=" * 50)
                print("👤 Admin User Created:")
                print("   Username: manager")
                print("   Password: Manager@2026")
                print("=" * 50)
            else:
                print("=" * 50)
                print("✅ BUKUYA Driver's SACCO System Ready")
                print("=" * 50)
                print("👤 Login with:")
                print("   Username: manager")
                print("   Password: Manager@2026")
                print("=" * 50)
        except Exception as e:
            print(f"Error initializing database: {e}")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
