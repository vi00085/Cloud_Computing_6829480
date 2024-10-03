import json
import random
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/analyse', methods=['POST'])
def analyse():
    event = request.get_json()

    # Extracting values from the payload with defaults
    data = event.get('data', [])
    minhistory = int(event.get('minhistory', 101))
    shots = int(event.get('shots', 10000))
    transaction_type = event.get('t', 'buy')
    check_days = int(event.get('p', 7))

    results = []
    total_profit_loss = 0
    total_var95 = 0
    total_var99 = 0

    # Process the data if it exists
    if data:
        for i in range(minhistory, len(data)):
            if data[i][transaction_type.capitalize()] == 1:
                close_prices = [data[j]['Close'] for j in range(i - minhistory, i)]
                returns = [(close_prices[k] - close_prices[k - 1]) / close_prices[k - 1] for k in range(1, len(close_prices))]
                mean = sum(returns) / len(returns)
                std = (sum((x - mean) ** 2 for x in returns) / len(returns)) ** 0.5

                simulated = [random.gauss(mean, std) for _ in range(shots)]
                simulated.sort(reverse=True)
                var95 = simulated[int(len(simulated) * 0.05)]
                var99 = simulated[int(len(simulated) * 0.01)]
                total_var95 += var95
                total_var99 += var99

                # Calculate profit or loss after specified days
                future_index = i + check_days
                profit_loss = None
                if future_index < len(data):
                    future_price = data[future_index]['Close']
                    current_price = data[i]['Close']
                    profit_loss = (future_price - current_price) / current_price if current_price else None
                    total_profit_loss += profit_loss if profit_loss else 0

                results.append({
                    'signal_date': i,
                    'var95': var95,
                    'var99': var99,
                    'profit_loss': profit_loss,
                    'type': transaction_type.capitalize()
                })

    # Calculate averages for audit
    count_signals = len(results)
    average_var95 = total_var95 / count_signals if count_signals else 0
    average_var99 = total_var99 / count_signals if count_signals else 0

    return jsonify({
        'results': results,
        'averages': {
            'average_var95': average_var95,
            'average_var99': average_var99,
            'total_profit_loss': total_profit_loss
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
