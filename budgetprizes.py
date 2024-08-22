from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
import stripe
from datetime import datetime

app = Flask(__name__)

# Configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/budget_leaderboard'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Optimization 1
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # Optimization 2

db = SQLAlchemy(app)
jwt = JWTManager(app)

# Stripe Configuration
stripe.api_key = 'your_stripe_secret_key'

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    subscription_status = db.Column(db.String(50), nullable=False, default="inactive")
    prize_eligible = db.Column(db.Boolean, default=False)
    subscription = db.relationship('Subscription', backref='user', uselist=False)  # Optimization 3

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    prize_contribution = db.Column(db.Float, nullable=False)
    next_payment_date = db.Column(db.Date, nullable=False)

class PrizePool(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    last_distributed = db.Column(db.Date, nullable=True)

# Routes
@app.route('/subscribe', methods=['POST'])
@jwt_required()
def subscribe():
    user_id = get_jwt_identity()
    data = request.get_json()

    try:
        customer = stripe.Customer.create(email=data['email'], source=data['token'])
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'plan': data['plan']}],
        )

        amount = subscription['plan']['amount'] / 100.0
        prize_contribution = amount * 0.2

        user = User.query.get(user_id)
        if user.subscription:
            user.subscription.plan = data['plan']
            user.subscription.amount = amount
            user.subscription.prize_contribution = prize_contribution
            user.subscription.next_payment_date = datetime.utcnow()  # Optimization 4
        else:
            new_subscription = Subscription(user_id=user_id, plan=data['plan'], amount=amount,
                                            prize_contribution=prize_contribution, next_payment_date=datetime.utcnow())
            db.session.add(new_subscription)

        user.subscription_status = "active"
        user.prize_eligible = True

        prize_pool = PrizePool.query.first()
        if not prize_pool:
            prize_pool = PrizePool()
            db.session.add(prize_pool)
        prize_pool.total_amount += prize_contribution

        db.session.commit()

        return jsonify({'message': 'Subscription successful and prize pool updated'}), 201
    except stripe.error.StripeError as e:
        return jsonify({'message': f'Error with payment: {str(e)}'}), 400

@app.route('/distribute_prizes', methods=['POST'])
def distribute_prizes():
    top_savers = User.query.join(Subscription).order_by(User.id.desc()).limit(3).all()  # Optimization 5

    prize_pool = PrizePool.query.first()
    if not prize_pool or prize_pool.total_amount == 0:
        return jsonify({'message': 'No prizes to distribute'}), 400

    prize_amount = prize_pool.total_amount / len(top_savers)

    for user in top_savers:
        # Implement prize distribution logic here
        prize_pool.total_amount = 0.0
        prize_pool.last_distributed = datetime.utcnow()
        db.session.commit()

    return jsonify({'message': 'Prizes distributed successfully'}), 200

if __name__ == '__main__':
    with app.app_context():  # Optimization 6
        db.create_all()
    app.run(debug=True)