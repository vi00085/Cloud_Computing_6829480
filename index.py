import boto3
import json
import random
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import yfinance as yf
import matplotlib.pyplot as plt
import io
import base64
import time

app = Flask(__name__)

# Initialize Boto3 clients for EC2, Lambda, and S3
region_name = 'us-east-1'
ec2_client = boto3.client('ec2', region_name=region_name)
lambda_client = boto3.client('lambda', region_name=region_name)
s3_client = boto3.client('s3')

instance_ids_dict = {
    'ec2': [],
    'lambda': 'Analysis_Lambda'
}

analysis_results = {
    's3_path': None,
    'results': []
}

audit_log = []
start_time = None
services_initialized = False  # Flag to track if services are initialized

def check_lambda_function(function_name):
    try:
        lambda_client.get_function(FunctionName=function_name)
        return True
    except:
        return False

def invoke_lambda_function(function_name, payload):
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    response_payload = json.loads(response['Payload'].read().decode('utf-8'))
    return json.loads(response_payload['body'])

def get_ec2_instance_status(instance_ids):
    response = ec2_client.describe_instance_status(InstanceIds=instance_ids)
    statuses = response.get('InstanceStatuses', [])
    return all(status['InstanceState']['Name'] == 'running' for status in statuses)

def invoke_ec2_analysis_script(instance_ids, payload):
    results = []
    for instance_id in instance_ids:
        instance_public_dns = ec2_client.describe_instances(InstanceIds=[instance_id])['Reservations'][0]['Instances'][0]['PublicDnsName']
        response = requests.post(f'http://{instance_public_dns}:5000/analyse', json=payload)
        if response.status_code == 200:
            response_json = response.json()
            if 'results' in response_json:
                results.extend(response_json['results'])
            else:
                print(f"Missing 'results' key in EC2 response: {response_json}")
    return results

def save_results_to_s3(results, s3_path):
    s3_bucket, s3_key = s3_path.replace('s3://', '').split('/', 1)
    s3_client.put_object(Bucket=s3_bucket, Key=s3_key, Body=json.dumps(results))

@app.route('/warmup', methods=['POST'])
def warmup():
    global r, start_time, services_initialized
    data = request.get_json()
    service = data.get('s')
    r = data.get('r', 1)
    start_time = time.time()

    if service == 'ec2':
        image_id = 'ami-0391de34153ad3ef9'
        instance_type = 't2.micro'
        key_name = 'CLD-CW-KP'
        response = ec2_client.run_instances(
            ImageId=image_id,
            InstanceType=instance_type,
            KeyName=key_name,
            MinCount=r,
            MaxCount=r
        )
        instance_ids = [instance['InstanceId'] for instance in response['Instances']]
        instance_ids_dict['ec2'] = instance_ids
        services_initialized = True
        return jsonify({"result": "ok", "instances": instance_ids})

    elif service == 'lambda':
        function_name = instance_ids_dict['lambda']
        if check_lambda_function(function_name):
            services_initialized = True
            return jsonify({"result": "ok"})
        else:
            return jsonify({"result": "error", "message": "Lambda function not found"}), 500

    return jsonify({"result": "invalid service"}), 400

@app.route('/scaled_ready', methods=['GET'])
def scaled_ready():
    if instance_ids_dict['ec2'] and get_ec2_instance_status(instance_ids_dict['ec2']):
        return jsonify({"warm": True})
    elif instance_ids_dict['lambda']:
        return jsonify({"warm": True})
    return jsonify({"warm": False})

@app.route('/get_warmup_cost', methods=['GET'])
def get_warmup_cost():
    global r
    cost_per_hour = 0.0134
    cost_per_request_lambda = 0.0000166667
    memory_gb_lambda = 1
    time_seconds_lambda = 1

    if instance_ids_dict['ec2']:
        time_seconds = r * 3600
        cost = r * cost_per_hour
        return jsonify({"billable_time": time_seconds, "cost": cost})

    elif instance_ids_dict['lambda']:
        cost = r * memory_gb_lambda * time_seconds_lambda * cost_per_request_lambda
        return jsonify({"billable_time": r * time_seconds_lambda, "cost": cost})

    return jsonify({"result": "invalid service"}), 400

@app.route('/get_endpoints', methods=['GET'])
def get_endpoints():
    server_address = request.host_url.rstrip('/')

    endpoints = [
        {"endpoint": f"curl -X POST -H \"Content-Type: application/json\" -d '{{\"s\": \"ec2\", \"r\": 3}}' {server_address}/warmup"},
        {"endpoint": f"curl -X POST -H \"Content-Type: application/json\" -d '{{\"s\": \"lambda\", \"r\": 3}}' {server_address}/warmup"},
        {"endpoint": f"curl -X GET {server_address}/scaled_ready"},
        {"endpoint": f"curl -X GET {server_address}/get_warmup_cost"},
        {"endpoint": f"curl -X POST -H \"Content-Type: application/json\" -d '{{\"h\": 5, \"d\": 10000, \"t\": \"buy\", \"p\": 7}}' {server_address}/analyse"},
        {"endpoint": f"curl -X GET {server_address}/get_sig_vars9599"},
        {"endpoint": f"curl -X GET {server_address}/get_avg_vars9599"},
        {"endpoint": f"curl -X GET {server_address}/get_sig_profit_loss"},
        {"endpoint": f"curl -X GET {server_address}/get_tot_profit_loss"},
        {"endpoint": f"curl -X GET {server_address}/get_chart_url"},
        {"endpoint": f"curl -X GET {server_address}/get_time_cost"},
        {"endpoint": f"curl -X GET {server_address}/get_audit"},
        {"endpoint": f"curl -X GET {server_address}/reset"},
        {"endpoint": f"curl -X GET {server_address}/terminate"},
        {"endpoint": f"curl -X GET {server_address}/scaled_terminated"}
    ]
    
    return jsonify(endpoints)

@app.route('/analyse', methods=['POST'])
def analyse():
    global start_time, services_initialized
    if not services_initialized:
        return jsonify({"result": "error", "message": "Services not initialized. Please run warmup first."}), 400

    data_input = request.get_json()

    # Extract parameters
    h = data_input.get('h')
    d = data_input.get('d')
    t = data_input.get('t')
    p = data_input.get('p')

    # Prepare stock data (this part is specific to your application)
    today = datetime.today()
    past_time = today - timedelta(days=3*365)
    data = yf.download('NVDA', start=past_time, end=today)
    data.reset_index(inplace=True)
    data['Buy'] = 0
    data['Sell'] = 0

    for i in range(2, len(data)):
        body = 0.01  # Threshold for price change to consider
        if (data.loc[i, 'Close'] - data.loc[i, 'Open']) >= body:
            data.at[i, 'Buy'] = 1 if data.loc[i, 'Close'] > data.loc[i - 1, 'Close'] else data.at[i, 'Buy']
            data.at[i, 'Sell'] = 1 if data.loc[i, 'Close'] < data.loc[i - 1, 'Close'] else data.at[i, 'Sell']

    data['Date'] = data['Date'].dt.strftime('%Y-%m-%d')
    simplified_data = data[['Date', 'Close', 'Buy', 'Sell']].to_dict('records')

    payload = {
        'data': simplified_data,
        'minhistory': h,
        'shots': d,
        't': t,
        'p': p
    }

    global analysis_results
    analysis_results['results'] = []

    if instance_ids_dict['lambda']:
        function_name = instance_ids_dict['lambda']
        for _ in range(r):
            response_payload = invoke_lambda_function(function_name, payload)
            if 'results' in response_payload:
                analysis_results['results'].extend(response_payload['results'])
            else:
                print(f"Missing 'results' key in Lambda response: {response_payload}")

    elif instance_ids_dict['ec2']:
        if get_ec2_instance_status(instance_ids_dict['ec2']):
            results = invoke_ec2_analysis_script(instance_ids_dict['ec2'], payload)
            analysis_results['results'].extend(results)
        else:
            return jsonify({"result": "error", "message": "EC2 instances not running"}), 500
    else:
        return jsonify({"result": "invalid service"}), 400

    # Calculate averages
    var95_values = [result['var95'] for result in analysis_results['results']]
    var99_values = [result['var99'] for result in analysis_results['results']]
    total_profit_loss = sum(result['profit_loss'] for result in analysis_results['results'] if result['profit_loss'] is not None)

    average_var95 = sum(var95_values) / len(var95_values) if var95_values else 0
    average_var99 = sum(var99_values) / len(var99_values) if var99_values else 0

    analysis_results['averages'] = {
        'total_profit_loss': total_profit_loss,
        'average_var95': average_var95,
        'average_var99': average_var99
    }

    combined_results_s3_path = 's3://analyse-result-storage/results/combined_results.json'
    save_results_to_s3(analysis_results, combined_results_s3_path)
    analysis_results['s3_path'] = combined_results_s3_path

    end_time = time.time()
    total_time_seconds = end_time - start_time
    cost = 0

    if instance_ids_dict['ec2']:
        cost_per_hour = 0.0134
        cost = (total_time_seconds / 3600) * len(instance_ids_dict['ec2']) * cost_per_hour

    elif instance_ids_dict['lambda']:
        cost_per_request_lambda = 0.0000166667
        memory_gb_lambda = 1
        time_seconds_lambda = total_time_seconds
        cost = r * memory_gb_lambda * time_seconds_lambda * cost_per_request_lambda

    # Log audit
    audit_entry = {
        "s": "ec2" if instance_ids_dict['ec2'] else "lambda",
        "r": r,
        "h": h,
        "d": d,
        "t": t,
        "p": p,
        "profit_loss": analysis_results['averages']['total_profit_loss'],
        "av95": analysis_results['averages']['average_var95'],
        "av99": analysis_results['averages']['average_var99'],
        "time": total_time_seconds,
        "cost": cost
    }
    audit_log.append(audit_entry)

    return jsonify({"result": "ok", "analysis_results_path": {"s3_path": combined_results_s3_path}})

def get_s3_file_content(bucket_name, file_key):
    obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    return json.loads(obj['Body'].read())

@app.route('/get_sig_vars9599', methods=['GET'])
def get_sig_vars9599():
    s3_path = analysis_results['s3_path']
    if not s3_path:
        return jsonify({"result": "error", "message": "No analysis results available"}), 400

    bucket_name, file_key = s3_path.replace('s3://', '').split('/', 1)
    content = get_s3_file_content(bucket_name, file_key)

    var95 = [item['var95'] for item in content['results']]
    var99 = [item['var99'] for item in content['results']]

    return jsonify({"var95": var95, "var99": var99})

@app.route('/get_avg_vars9599', methods=['GET'])
def get_avg_vars9599():
    s3_path = analysis_results['s3_path']
    if not s3_path:
        return jsonify({"result": "error", "message": "No analysis results available"}), 400

    bucket_name, file_key = s3_path.replace('s3://', '').split('/', 1)
    content = get_s3_file_content(bucket_name, file_key)

    var95 = [item['var95'] for item in content['results']]
    var99 = [item['var99'] for item in content['results']]

    avg_var95 = sum(var95) / len(var95) if var95 else 0
    avg_var99 = sum(var99) / len(var99) if var99 else 0

    return jsonify({"var95": avg_var95, "var99": avg_var99})

@app.route('/get_sig_profit_loss', methods=['GET'])
def get_sig_profit_loss():
    s3_path = analysis_results['s3_path']
    if not s3_path:
        return jsonify({"result": "error", "message": "No analysis results available"}), 400

    bucket_name, file_key = s3_path.replace('s3://', '').split('/', 1)
    content = get_s3_file_content(bucket_name, file_key)

    profit_loss = [item['profit_loss'] for item in content['results'] if item['profit_loss'] is not None]

    return jsonify({"profit_loss": profit_loss})

@app.route('/get_tot_profit_loss', methods=['GET'])
def get_tot_profit_loss():
    s3_path = analysis_results['s3_path']
    if not s3_path:
        return jsonify({"result": "error", "message": "No analysis results available"}), 400

    bucket_name, file_key = s3_path.replace('s3://', '').split('/', 1)
    content = get_s3_file_content(bucket_name, file_key)

    profit_loss = sum(item['profit_loss'] for item in content['results'] if item['profit_loss'] is not None)

    return jsonify({"profit_loss": profit_loss})

@app.route('/get_chart_url', methods=['GET'])
def get_chart_url():
    s3_path = analysis_results['s3_path']
    if not s3_path:
        return jsonify({"result": "error", "message": "No analysis results available"}), 400

    bucket_name, file_key = s3_path.replace('s3://', '').split('/', 1)
    content = get_s3_file_content(bucket_name, file_key)

    var95 = [item['var95'] for item in content['results']]
    var99 = [item['var99'] for item in content['results']]

    plt.figure(figsize=(10, 5))
    plt.plot(var95, label='VaR 95%')
    plt.plot(var99, label='VaR 99%')
    plt.legend()
    plt.title('VaR 95% and 99% Over Time')

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode()

    s3_bucket = bucket_name
    s3_key = 'results/chart.png'
    s3_client.put_object(Bucket=s3_bucket, Key=s3_key, Body=base64.b64decode(img_base64))

    chart_url = f"https://{s3_bucket}.s3.amazonaws.com/{s3_key}"

    return jsonify({"url": chart_url})

@app.route('/get_time_cost', methods=['GET'])
def get_time_cost():
    global start_time
    end_time = time.time()
    total_time_seconds = end_time - start_time
    cost = 0

    if instance_ids_dict['ec2']:
        cost_per_hour = 0.0134
        cost = (total_time_seconds / 3600) * len(instance_ids_dict['ec2']) * cost_per_hour

    elif instance_ids_dict['lambda']:
        cost_per_request_lambda = 0.0000166667
        memory_gb_lambda = 1
        time_seconds_lambda = total_time_seconds
        cost = r * memory_gb_lambda * time_seconds_lambda * cost_per_request_lambda

    return jsonify({"time": total_time_seconds, "cost": cost})

@app.route('/get_audit', methods=['GET'])
def get_audit():
    return jsonify(audit_log)

@app.route('/reset', methods=['GET'])
def reset():
    global analysis_results
    analysis_results = {
        's3_path': None,
        'results': []
    }

    # Clear the results from the S3 bucket
    s3_bucket = 'analyse-result-storage'
    s3_prefix = 'results/'
    objects_to_delete = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
    if 'Contents' in objects_to_delete:
        delete_keys = [{'Key': obj['Key']} for obj in objects_to_delete['Contents']]
        s3_client.delete_objects(Bucket=s3_bucket, Delete={'Objects': delete_keys})

    return jsonify({"result": "ok"})

@app.route('/terminate', methods=['GET'])
def terminate():
    global services_initialized
    if instance_ids_dict['ec2']:
        ec2_client.terminate_instances(InstanceIds=instance_ids_dict['ec2'])
        instance_ids_dict['ec2'] = []
    services_initialized = False
    return jsonify({"result": "ok"})

@app.route('/scaled_terminated', methods=['GET'])
def scaled_terminated():
    if not instance_ids_dict['ec2']:
        return jsonify({"terminated": True})

    # Describe the instances to get their current state
    response = ec2_client.describe_instances(InstanceIds=instance_ids_dict['ec2'])
    
    # Check the state of each instance
    all_terminated = True
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            if instance['State']['Name'] != 'terminated':
                all_terminated = False
                break
    
    return jsonify({"terminated": all_terminated})

if __name__ == '__main__':
    app.run(debug=True)