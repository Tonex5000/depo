import psycopg2
from psycopg2 import connect, sql
from flask import Flask, jsonify, request, render_template, send_from_directory, current_app
import logging
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
import requests
from flask_cors import CORS
from database import setup_database
import threading
import os
import isodate
import time
from werkzeug.security import generate_password_hash, check_password_hash
import string
import string

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

app.config['TOKEN_EXPIRATION_DAYS'] = 30
app.config['SECRET_KEY'] = '09d607fc4bbd698d4334427605aa78b9899c7798a1d1998c8381cb1ca7712067'  # Ensure this is kept secret and safe



# Configure logging
logging.basicConfig(level=logging.DEBUG)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="dpg-cqn13rdsvqrc73fha82g-a.oregon-postgres.render.com",
            dbname="trading_fdlx",
            user="trading_fdlx_user",
            password="68gZAC3f42icJv3l3uZEOfR2j9Mtbskq",
            port=5432,
            
        )
        c = conn.cursor()

        cursor = conn.cursor()
        return conn, cursor

    except psycopg2.Error as e:
        print(f"Error connecting to PostgresSQL: {e}")
        return None, None

def close_db_connection(conn, cursor):
    if cursor:
        cursor.close()
    if conn:
        conn.close()

# Helper function to create a new JWT token
def create_token(user_id):
    expiration = datetime.utcnow() + timedelta(days=app.config['TOKEN_EXPIRATION_DAYS'])
    payload = {
        'user_id': user_id,
        'exp': expiration
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token

# Function to test token validity
def test_token_validity(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return True, payload['user_id']
    except jwt.ExpiredSignatureError:
        logging.error('Token has expired')
        return False, None
    except jwt.InvalidTokenError:
        logging.error('Invalid token')
        return False, None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        logging.debug(f'Received token: {token}')
        if not token:
            return jsonify({"msg": "Token is missing"}), 401

        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]

        is_valid, user_id = test_token_validity(token)

        if not is_valid:
            return jsonify({"msg": "Token is invalid"}), 401

        return f(user_id, *args, **kwargs)
    return decorated

""" @app._got_first_request
def initialize():
    setup_database() """

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    try:
        if request.content_type == 'application/json':
            data = request.json
        else:
            data = request.form

        email = data.get('email')
        password = data.get('password')
        username = data.get('username')
        phone_number = data.get('phone_number')

        if not email or not password or not username or not phone_number:
            return jsonify({"msg": "Fill in your complete details"}), 400
        conn, c = get_db_connection()
        

        if conn and c:
             #check email existant
            c.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = c.fetchone()

            if user:
              close_db_connection(conn, c)  
              return jsonify({"msg": "Email already registered"}), 400 
            
            
            hashed_password = generate_password_hash(password)

            
            #insert new user
            c.execute(
                "INSERT INTO users (email, password, username, phone_number) VALUES (%s, %s, %s, %s)",
                (email, hashed_password, username, phone_number)
            )
            conn.commit()
            close_db_connection(conn, c)


            logging.debug(f"User {email} registered successfully")
            return jsonify({"msg": "User created successfully"}), 201
        else:
            return jsonify({"msg": "Failed to connect to database"}), 500
   
    except Exception as e:
        logging.exception('Error during registration')
        return str(e), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        if request.content_type == 'application/json':
            data = request.json
        else:
            data = request.form

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"msg": "Email and password are required"}), 400

        conn, c = get_db_connection()
        
        if conn and c:
            c.execute("SELECT id, password FROM users WHERE email = %s", (email,))
            user = c.fetchone()

        
            if user:
                user_id = user[0]
                stored_password = user[1]
                
                if check_password_hash(stored_password, password):
                    token = create_token(user_id)
                    close_db_connection(conn, c)
                    logging.debug(f"User {email} logged in successfully")
                    return jsonify(token=token), 200
                else:
                     logging.warning(f"Failed login attempt for email: {email}")
                     return jsonify({"msg": "Password mismatch"}), 401
     
            else:
                logging.warning(f"User with email {email} not found")
                return jsonify({"msg": "Bad email or password"}), 401
        else:
            return jsonify({"msg": "Failed to connect to database"}), 500
    except Exception as e:
        logging.exception('Error during login')
        return jsonify({"msg": "Internal server error"}), 500


@app.route('/market-data', methods=['GET'])
@token_required
def get_market_data(user_id):
    try:
        response = requests.get('https://api.coingecko.com/api/v3/simple/price', 
                                params={'ids': 'bitcoin', 'vs_currencies': 'usd'})
        if response.status_code != 200:
            logging.error('Failed to fetch market data from CoinGecko')
            return jsonify({"error": "Failed to fetch market data"}), 500

        market_data = response.json()
        logging.debug(f"Fetched market data: {market_data}")

        ticker = {
            "symbol": "BTC/USDT",
            "price": market_data['bitcoin']['usd']
        }

        return jsonify(ticker)
    except Exception as e:
        logging.exception('Error fetching market data')
        return str(e), 500

@app.route('/deposit', methods=['POST'])
@token_required
def deposit(user_id):
    try:
        if request.content_type == 'application/json':
            data = request.json
            deposit_date = data['date']
            amount_bnb = data.get('amount_bnb')
            amount_usd = data.get('amount_usd')
            status = data['status']
            transaction_hash = data.get('transactionHash', 'N/A')
            contract_address = data.get('contractAddress', 'N/A')
            wallet_address = data.get('wallet_address', 'N/A')


            if amount_bnb is not None and amount_bnb != '0':
                amount_bnb = float(amount_bnb)
            elif amount_usd is not None and amount_usd != '0':
                amount_usd = float(amount_usd)
            else:
                return jsonify({"message": "Enter a deposited value in USD or BNB"}), 400
        

           # Convert BNB to USD using CoinGecko API
            try:
                response = requests.get('https://api.coingecko.com/api/v3/simple/price', 
                                        params={'ids': 'binancecoin', 'vs_currencies': 'usd'})
                response_data = response.json()
                rate = float(response_data['binancecoin']['usd'])
            except KeyError:
                logging.exception('Error fetching BNB to USD rate: KeyError')
                return jsonify({'message': 'Failed to fetch BNB to USD conversion rate'}), 500
            except Exception as e:
                logging.exception('Error fetching BNB to USD rate')
                return jsonify({'message': 'Failed to fetch BNB to USD conversion rate'}), 500

            if amount_bnb is not None:
                balance_usd = round(amount_bnb * rate, 2)
            else:
                balance_usd = amount_usd


            logging.debug(f'Deposit request: user_id={user_id}, amount_bnb={amount_bnb},amount_usd={amount_usd} balance_usd={balance_usd}, status={status}, transaction_hash={transaction_hash}, contract_address={contract_address}')

            deposited_amount = amount_bnb if amount_bnb is not None else amount_usd

            conn, cursor = get_db_connection()
            try:
                cursor.execute(sql.SQL("""
                    INSERT INTO deposits (user_id, amount, balance_usd, status, timestamp, transaction_hash, contract_address, wallet_address, paper_balance) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)
                """), (user_id, deposited_amount, balance_usd, status, datetime.strptime(deposit_date, '%Y-%m-%dT%H:%M:%S.%fZ').timestamp(), transaction_hash, contract_address, wallet_address))

                if status == 'Successful':
                    cursor.execute(sql.SQL("""
                         UPDATE deposits SET paper_balance = paper_balance + %s WHERE wallet_address = %s
                    """), (balance_usd, wallet_address))
    
                     # Fetch the updated paper_balance
                    cursor.execute(sql.SQL("""
                         SELECT paper_balance FROM deposits WHERE wallet_address = %s
                    """), (wallet_address,))
    
                    paper_balance = cursor.fetchone()
                    conn.commit()

                    if paper_balance:
                        paper_balance = paper_balance[0]
                    else:
                        paper_balance = 0

            except Exception as e:
                conn.rollback()
                logging.exception('Error during deposit transaction')
                return jsonify({'message': 'Failed to process deposit'}), 500
            finally:   
                close_db_connection(conn, cursor)

            logging.debug(f'Deposit successful for user_id={user_id}, amount_usd={balance_usd}')
            return jsonify({'wallet_address': wallet_address , 'paper_balance': paper_balance})
        else:
            return jsonify({'message': 'Content-Type must be application/json'}), 400

    except Exception as e:
        logging.exception('Error during deposit')
        return str(e), 500


@app.route('/spot-grid', methods=['POST'])
@token_required
def spot_grid(user_id):
    conn = None
    cursor = None
    try:
        data = request.json
        app.logger.debug(f"Received request data: {data}")

        required_fields = ['symbol', 'lower_price', 'upper_price', 'grid_intervals', 'investment_amount', 'wallet_address', 'runtime']
        for field in required_fields:
            if field not in data:
                app.logger.error(f'Missing required parameter: {field}')
                return jsonify({"msg": f"Missing required parameter: {field}"}), 400

        symbol = data['symbol']
        lower_price = data['lower_price']
        upper_price = data['upper_price']
        grid_intervals = data['grid_intervals']
        investment_amount = data['investment_amount']
        wallet_address = data['wallet_address']
        runtime = data['runtime']

        try:
            if runtime.endswith('Z'):
                runtime_datetime = datetime.fromisoformat(runtime[:-1]).replace(tzinfo=timezone.utc)
            else:
                runtime_datetime = datetime.fromisoformat(runtime)

            current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
            if runtime_datetime <= current_time:
                raise ValueError("Runtime must be a future date and time")
            runtime_seconds = int((runtime_datetime - current_time).total_seconds())
        except (ValueError, TypeError) as e:
            app.logger.error(f"Invalid runtime format: {runtime}")
            return jsonify({"msg": "Invalid runtime format. Use ISO 8601 date and time format."}), 400

        trading_strategy = "Spot Grid"
        roi = data.get('roi', 0)
        pnl = data.get('pnl', 0)

        app.logger.debug(f'Spot grid request: user_id={user_id}, wallet_address={wallet_address}, symbol={symbol}, lower_price={lower_price}, upper_price={upper_price}, grid_intervals={grid_intervals}, investment_amount={investment_amount}, runtime={runtime}')

        conn, cursor = get_db_connection()
        cursor.execute("SELECT paper_balance FROM deposits WHERE wallet_address = %s", (wallet_address,))
        result = cursor.fetchone()
        if result:
            paper_balance = result[0]
        else:
            paper_balance = None

        if paper_balance is None or paper_balance < investment_amount:
            app.logger.debug(f'Insufficient funds: paper_balance={paper_balance}, investment_amount={investment_amount}')
            return jsonify({"msg": "Insufficient funds"}), 400

        # Deduct investment_amount from paper_balance
        cursor.execute("UPDATE deposits SET paper_balance = paper_balance - %s WHERE wallet_address = %s", (investment_amount, wallet_address))
        conn.commit()

        # Fetch the appropriate conversion rate for the selected trading pair
        symbol_map = {
            'BTC/USD': 'bitcoin',
            'ETH/USD': 'ethereum',
            'BNB/USD': 'binancecoin'
        }

        coingecko_symbol = symbol_map.get(symbol)
        if not coingecko_symbol:
            app.logger.error(f"Unsupported trading pair: {symbol}")
            return jsonify({"msg": "Unsupported trading pair"}), 400

        response = requests.get('https://api.coingecko.com/api/v3/simple/price', 
                                params={'ids': coingecko_symbol, 'vs_currencies': 'usd'})
        response_data = response.json()
        if coingecko_symbol not in response_data or 'usd' not in response_data[coingecko_symbol]:
            app.logger.error(f"Unable to retrieve market price for symbol: {symbol}")
            return jsonify({"msg": "Unable to retrieve market price"}), 500

        market_price = response_data[coingecko_symbol]['usd']

        grid_prices = [lower_price + x * (upper_price - lower_price) / (grid_intervals - 1) for x in range(grid_intervals)]
        if market_price not in grid_prices:
            grid_prices.append(market_price)
            grid_prices.sort()
        
        runtime_unix_timestamp = int(runtime_datetime.timestamp())

        trades = []
        total_sell_value = 0
        for price in grid_prices:
            buy_amount = investment_amount / grid_intervals / price
            buy_trade = {
                'user_id': user_id,
                'symbol': symbol,
                'type': 'limit',
                'side': 'buy',
                'amount': buy_amount,
                'price': price,
                'timestamp': runtime_unix_timestamp
            }
            trades.append(buy_trade)

            sell_price = price * 1.01
            sell_amount = buy_amount
            sell_value = sell_price * sell_amount  # Calculate the value of the sell trade
            total_sell_value += sell_value  # Accumulate the total sell value

            sell_trade = {
                'user_id': user_id,
                'symbol': symbol,
                'type': 'limit',
                'side': 'sell',
                'amount': sell_amount,
                'price': sell_price,
                'timestamp': runtime_unix_timestamp
            }
            trades.append(sell_trade)

        cursor.execute(
            "INSERT INTO spot_grids (user_id, trading_pair, trading_strategy, roi, pnl, runtime, min_investment, status, user_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, symbol, trading_strategy, roi, pnl, runtime, investment_amount, "Active", 1)
        )
        spot_grid_id = cursor.fetchone()[0]

        for trade in trades:
            cursor.execute(
                "INSERT INTO trades (user_id, symbol, type, side, amount, price, timestamp, spot_grid_id, wallet_address) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (trade['user_id'], trade['symbol'], trade['type'], trade['side'], trade['amount'], trade['price'], trade['timestamp'], spot_grid_id, wallet_address)
            )
            

       # Start a new thread to update the user's paper balance after the runtime duration
        threading.Thread(target=update_balance_after_delay, args=(user_id, wallet_address, total_sell_value, runtime_seconds)).start()

        conn.commit()
        close_db_connection(conn, cursor)

        app.logger.debug(f'Spot grid trading started successfully for user_id={user_id}, trades={trades}')
        return jsonify({"msg": "Grid trading started successfully", "trades": trades}), 200
    except Exception as e:
        app.logger.error(f"Error during spot grid: {e}")
        return jsonify({"msg": str(e)}), 500


def update_balance_after_delay(user_id, wallet_address, total_sell_value, delay):
    time.sleep(delay)
    conn, cursor = get_db_connection()
    cursor.execute("UPDATE deposits SET paper_balance = paper_balance + %s WHERE wallet_address = %s", (total_sell_value, wallet_address))
    conn.commit()
    close_db_connection(conn, cursor)
    app.logger.debug(f'Paper balance updated for user_id={user_id}, wallet_address={wallet_address}, added_value={total_sell_value}')



@app.route('/get-paper-balance', methods=['GET', 'POST'])
@token_required
def get_paper_balance(user_id):
    conn = None
    cursor = None
    try:
        if request.method == 'GET':
            wallet_address = request.args.get('wallet_address')
        elif request.method == 'POST':
            data = request.get_json()
            wallet_address = data.get('wallet_address')

        if not wallet_address:
            app.logger.error('Missing required parameter: wallet_address')
            return jsonify({"msg": "0"}), 400

        conn, cursor = get_db_connection()
        cursor.execute("SELECT paper_balance FROM deposits WHERE wallet_address = %s", (wallet_address,))
        result = cursor.fetchone()

        if result:
            paper_balance = result[0]
            app.logger.debug(f'Fetched paper_balance for user_id={user_id}, wallet_address={wallet_address}: {paper_balance}')
            return jsonify({"wallet_address": wallet_address, "paper_balance": paper_balance}), 200
        else:
            app.logger.error(f'Wallet address not found: {wallet_address}')
            return jsonify({"msg": "0"}), 404

    except Exception as e:
        app.logger.error(f"Error fetching paper balance: {e}")
        return jsonify({"msg": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            close_db_connection(conn, cursor)




@app.route('/marketplace', methods=['GET'])
@token_required
def get_marketplace(user_id):
    try:
        sort_by = request.args.get('sort_by', 'roi')

        conn, c = get_db_connection()
        if (sort_by == 'roi'):
            c.execute("SELECT id, trading_pair, roi, pnl, runtime, min_investment, user_count FROM spot_grids WHERE status = 'Active' ORDER BY roi DESC")
        elif (sort_by == 'pnl'):
            c.execute("SELECT id, trading_pair, roi, pnl, runtime, min_investment, user_count FROM spot_grids WHERE status = 'Active' ORDER BY pnl DESC")
        elif (sort_by == 'copied'):
            c.execute("SELECT id, trading_pair, roi, pnl, runtime, min_investment, user_count FROM spot_grids WHERE status = 'Active' ORDER BY user_count DESC")
        else:
            close_db_connection(conn, c)
            logging.error(f"Invalid sorting parameter: {sort_by}")
            return jsonify({"msg": "Invalid sorting parameter"}), 400

        spot_grids = c.fetchall()
        close_db_connection(conn, c)

        bot_list = []
        for grid in spot_grids:
            bot_list.append({
                "id": grid[0],
                "trading_pair": grid[1],
                "roi": grid[2],
                "pnl": grid[3],
                "runtime": grid[4],
                "min_investment": grid[5],
                "user_count": grid[6]
            })

        logging.debug(f"Fetched marketplace data: {bot_list}")
        return jsonify(bot_list)
    except Exception as e:
        logging.exception('Error fetching marketplace data')
        return str(e), 500

@app.route('/paper-trades', methods=['GET'])
@token_required
def get_paper_trades(user_id):
    try:
        conn, c = get_db_connection()
        trades = c.execute("SELECT * FROM trades WHERE user_id = %s", (user_id,)).fetchall()
        close_db_connection(conn, c)

        trade_list = []
        for trade in trades:
            trade_list.append({
                "id": trade[0],
                "user_id": trade[1],
                "symbol": trade[2],
                "type": trade[3],
                "side": trade[4],
                "amount": trade[5],
                "price": trade[6],
                "timestamp": trade[7],
                "spot_grid_id": trade[8]
            })

        logging.debug(f"Fetched paper trades for user_id={user_id}: {trade_list}")
        return jsonify(trade_list)
    except Exception as e:
        logging.exception('Error fetching paper trades')
        return str(e), 500

@app.route('/spot-grids', methods=['GET'])
@token_required
def get_spot_grids(user_id):
    try:
        conn, c = get_db_connection()
        spot_grids = c.execute("SELECT * FROM spot_grids WHERE user_id = %s", (user_id,)).fetchall()
        close_db_connection(conn, c)

        grid_list = []
        for grid in spot_grids:
            grid_list.append({
                "id": grid[0],
                "user_id": grid[1],
                "trading_pair": grid[2],
                "trading_strategy": grid[3],
                "roi": grid[4],
                "pnl": grid[5],
                "runtime": grid[6],
                "min_investment": grid[7],
                "status": grid[8],
                "user_count": grid[9]
            })

        logging.debug(f"Fetched spot grids for user_id={user_id}: {grid_list}")
        return jsonify(grid_list)
    except Exception as e:
        logging.exception('Error fetching spot grids')
        return str(e), 500

@app.route('/trade_history', methods=['POST'])
@token_required
def trade_history(user_id):
    conn, cursor = None, None
    try:
        data = request.json
        app.logger.debug(f"Received request data: {data}")

        if 'wallet_address' not in data:
            app.logger.error('Missing required parameter: wallet_address')
            return jsonify({"msg": "Missing required parameter: wallet_address"}), 400

        wallet_address = data['wallet_address']

        conn, cursor = get_db_connection()
        if not conn or not cursor:
            return jsonify({"msg": "Database connection failed"}), 500

        cursor.execute(
            "SELECT timestamp, symbol, type, side, amount, price FROM trades WHERE user_id = %s AND wallet_address = %s",
            (user_id, wallet_address)
        )
        trades = cursor.fetchall()

        trade_history = []
        for trade in trades:
            trade_history.append({
                "timestamp": trade[0],
                "symbol": trade[1],
                "type": trade[2],
                "side": trade[3],
                "amount": trade[4],
                "price": trade[5]
            })

        return jsonify(trade_history)
    except Exception as e:
        app.logger.error(f"Error fetching trade history: {e}")
        return jsonify({"msg": str(e)}), 500
    finally:
        if conn and cursor:
            close_db_connection(conn, cursor)



@app.route('/deposit_history', methods=['POST'])
@token_required
def get_deposit_history(user_id):
    conn, cursor = None, None
    try:
        data = request.get_json()
        wallet_address = data.get('wallet_address')
        if not wallet_address:
            return jsonify({'msg': 'Wallet address is required'}), 400

        logging.debug(f'Fetching deposit history for wallet_address: {wallet_address}')

        conn, cursor = get_db_connection()
        if not conn or not cursor:
            return jsonify({'msg': 'Database connection failed'}), 500

        cursor.execute("SELECT amount, status, timestamp, transaction_hash, contract_address FROM deposits WHERE user_id = %s AND wallet_address = %s", (user_id, wallet_address))
        deposits = cursor.fetchall()

        deposit_history = []
        for deposit in deposits:
            deposit_history.append({
                'amount': deposit[0],
                'status': deposit[1],
                'timestamp': deposit[2],
                'transaction_hash': deposit[3],
                'contract_address': deposit[4]
            })

        return jsonify(deposit_history)
    except Exception as e:
        logging.exception('Error fetching deposit history')
        return jsonify({'msg': str(e)}), 500
    finally:
        close_db_connection(conn, cursor)


if __name__ == '__main__':
    setup_database()
    app.run(port=5000)
    app.run(debug=True)
