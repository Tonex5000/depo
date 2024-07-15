import psycopg2

def setup_database():
    conn = psycopg2.connect(host="dpg-cqagoarv2p9s73d13og0-a", dbname="trading_db_key1", user="trading_db_key1_user", password="wEHeCbekgEA29Q0RNJVKA8jz38kO9AKZ", port=5432)
    c = conn.cursor()

    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        username TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        paper_balance REAL DEFAULT 0
    )''')

    # Create deposits table
    c.execute('''CREATE TABLE IF NOT EXISTS deposits (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        timestamp REAL,
        amount REAL,
        balance_usd REAL,
        status TEXT,
        wallet_address TEXT,  -- New column for wallet address
        transaction_hash TEXT,
        contract_address TEXT,
        transaction_fee REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

        # Create spot_grids table
    c.execute('''CREATE TABLE IF NOT EXISTS spot_grids (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        trading_pair TEXT,
        trading_strategy TEXT,
        roi REAL,
        pnl REAL,
        runtime TEXT,
        min_investment REAL,
        status TEXT,
        user_count INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    # Create trades table
    c.execute('''CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        symbol TEXT,
        type TEXT,
        side TEXT,
        amount REAL,
        price REAL,
        timestamp INTEGER,
        spot_grid_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(spot_grid_id) REFERENCES spot_grids(id) ON DELETE CASCADE
    )''')

    conn.commit()
    print("Successfully created")
    conn.close()

if __name__ == '__main__':
    setup_database()
