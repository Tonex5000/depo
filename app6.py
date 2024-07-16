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
                return jsonify({"error": f"Missing required parameter: {field}"}), 400

        symbol = data['symbol']
        lower_price = data['lower_price']
        upper_price = data['upper_price']
        grid_intervals = data['grid_intervals']
        investment_amount = data['investment_amount']
        wallet_address = data['wallet_address']
        runtime = data['runtime']

        try:
            duration = isodate.parse_duration(runtime)
            runtime_seconds = int(duration.total_seconds())
        except (ValueError, TypeError) as e:
            app.logger.error(f"Invalid runtime format: {runtime}")
            return jsonify({"error": "Invalid runtime format. Use ISO 8601 duration format."}), 400

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
            return jsonify({"error": "Insufficient funds"}), 400

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
            return jsonify({"error": "Unsupported trading pair"}), 400

        response = requests.get('https://api.coingecko.com/api/v3/simple/price', 
                                params={'ids': coingecko_symbol, 'vs_currencies': 'usd'})
        response_data = response.json()
        if coingecko_symbol not in response_data or 'usd' not in response_data[coingecko_symbol]:
            app.logger.error(f"Unable to retrieve market price for symbol: {symbol}")
            return jsonify({"error": "Unable to retrieve market price"}), 500

        market_price = response_data[coingecko_symbol]['usd']

        grid_prices = [lower_price + x * (upper_price - lower_price) / (grid_intervals - 1) for x in range(grid_intervals)]
        if market_price not in grid_prices:
            grid_prices.append(market_price)
            grid_prices.sort()

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
                'timestamp': int(time.time())
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
                'timestamp': int(time.time())
            }
            trades.append(sell_trade)

        cursor.execute(
            "INSERT INTO spot_grids (user_id, trading_pair, trading_strategy, roi, pnl, runtime, min_investment, status, user_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (user_id, symbol, trading_strategy, roi, pnl, runtime, investment_amount, "Active", 1)
        )
        spot_grid_id = cursor.fetchone()[0]

        for trade in trades:
            cursor.execute(
                "INSERT INTO trades (user_id, symbol, type, side, amount, price, timestamp, spot_grid_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (trade['user_id'], trade['symbol'], trade['type'], trade['side'], trade['amount'], trade['price'], trade['timestamp'], spot_grid_id)
            )

        # Start a new thread to update the user's paper balance after the runtime duration
        threading.Thread(target=update_balance_after_delay, args=(user_id, wallet_address, total_sell_value, runtime_seconds)).start()

        conn.commit()
        close_db_connection(conn, cursor)

        app.logger.debug(f'Spot grid trading started successfully for user_id={user_id}, trades={trades}')
        return jsonify({"msg": "Grid trading started successfully", "trades": trades}), 200
    except Exception as e:
        app.logger.error(f"Error during spot grid: {e}")
        return jsonify({"error": str(e)}), 500