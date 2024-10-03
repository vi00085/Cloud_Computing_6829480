import json
import random
import boto3
from datetime import datetime

def lambda_handler(event, context):
    # Parse the JSON body from the event if it exists
    event = json.loads(event['body']) if 'body' in event else event

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
    s3 = boto3.resource('s3')
    bucket_name = 'analyse-result-storage'

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

    # Append results to S3
    results_file_name = f'results_{transaction_type}.json'
    results_s3_path = 'results/' + results_file_name
    combined_results_s3_path = 'results/combined_results.json'
    
    try:
        existing_results = json.loads(s3.Object(bucket_name, results_s3_path).get()['Body'].read().decode('utf-8'))
    except s3.meta.client.exceptions.NoSuchKey:
        existing_results = {'results': []}
    
    combined_results = existing_results['results'] + results
    s3.Object(bucket_name, results_s3_path).put(Body=json.dumps({'results': combined_results}))
    
    try:
        existing_combined_results = json.loads(s3.Object(bucket_name, combined_results_s3_path).get()['Body'].read().decode('utf-8'))
    except s3.meta.client.exceptions.NoSuchKey:
        existing_combined_results = {'results': []}
    
    combined_results_all = existing_combined_results['results'] + results
    s3.Object(bucket_name, combined_results_s3_path).put(Body=json.dumps({'results': combined_results_all}))

    # Calculate averages for audit
    count_signals = len(results)
    average_var95 = total_var95 / count_signals if count_signals else 0
    average_var99 = total_var99 / count_signals if count_signals else 0

    # Prepare audit entry
    audit_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'parameters': {
            'minhistory': minhistory,
            'shots': shots,
            'transaction_type': transaction_type,
            'check_days': check_days
        },
        'results': {
            'average_var95': average_var95,
            'average_var99': average_var99,
            'total_profit_loss': total_profit_loss
        },
        'results_s3_path': f's3://{bucket_name}/{results_s3_path}'
    }

    # Append audit data to S3
    audit_file_key = 'audit/audit_log.json'
    try:
        audit_content = s3.Object(bucket_name, audit_file_key).get()['Body'].read().decode('utf-8')
        audit_entries = json.loads(audit_content)
    except s3.meta.client.exceptions.NoSuchKey:
        audit_entries = []

    audit_entries.append(audit_data)
    s3.Object(bucket_name, audit_file_key).put(Body=json.dumps(audit_entries))

    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Results and audit data saved to S3', 'results': results, 'results_s3_path': f's3://{bucket_name}/{results_s3_path}'})
    }