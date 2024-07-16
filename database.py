import psycopg2

def setup_database():
    try:
        conn = psycopg2.connect(
            host="dpg-cqb9bpij1k6c73aof69g-a.oregon-postgres.render.com",
            dbname="bot_db_u735",
            user="bot_db_u735_user",
            password="gPCwV9bQP0r8AB3IuJcKf0rFmGjxoRmP",
            port=5432,
            
        )
        c = conn.cursor()

        # Create users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            username TEXT NOT NULL,
            phone_number TEXT NOT NULL
        )''')

        # Create deposits table
        c.execute('''CREATE TABLE IF NOT EXISTS deposits (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            timestamp REAL,
            amount REAL,
            balance_usd REAL,
            status TEXT,
            wallet_address TEXT,
            transaction_hash TEXT,
            contract_address TEXT,
            transaction_fee REAL,
            paper_balance REAL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')

        # Create spot_grids table
        c.execute('''CREATE TABLE IF NOT EXISTS spot_grids (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
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
        print("Successfully created and updated tables")
        conn.close()

    except Exception as e:
        print(f"Error during database setup: {e}")

if __name__ == '__main__':
    setup_database()
