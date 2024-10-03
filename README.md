# Optimizing Financial Risk Assessment with Cloud Based Monte Carlo Simulations

This project implements an advanced cloud-native API for performing Monte Carlo simulations to evaluate financial trading strategies, particularly focusing on NVDA stock data. The architecture leverages both Google App Engine (GAE) and Amazon Web Services (AWS) to balance performance, scalability, and cost-efficiency. 

## Project Overview

The project is designed to:
- Dynamically provision AWS Lambda for lightweight tasks and EC2 instances for resource-intensive computations.
- Utilize a pre-configured AMI to automatically set up and configure the necessary infrastructure on AWS.
- Automate the analysis and financial calculations with Python, providing users with insights into financial trading strategies.
- Store the simulation results securely in AWS S3, ensuring both availability and compliance with data privacy standards.

### Key Technologies:
- **Amazon Web Services (AWS)**: EC2, Lambda, S3
- **Google App Engine (GAE)**: For hosting the API and providing global accessibility.
- **Python**: The core language for implementing Monte Carlo simulations and financial analysis.
- **Shell Scripts**: For setting up environments and services within the AWS infrastructure.

## Project Structure

- **Analysis_Lambda.py**: Script designed for lightweight tasks running on AWS Lambda.
- **analysis_script.py**: Python script to run the main Monte Carlo simulations.
- **index.py**: Main entry point for the API, hosting endpoints for financial simulations.
- **requirements.txt**: Lists Python dependencies for the project.
- **setup_analysis_env.sh**: Shell script for setting up the required environment.
- **create_systemd_service.sh**: Script to set up the necessary services in AWS.
- **analysis_app.conf.txt**: Configuration file for the app setup.
- **analysis_script.wsgi.txt**: WSGI configuration for running the analysis API.

## API Endpoints

- **/warmup**: Initializes AWS resources, allowing users to configure the number of EC2 instances or Lambda functions.
- **/analyse**: Triggers the Monte Carlo simulations with user-specified parameters.
- **/get_warmup_cost**: Returns the estimated cost for AWS resource usage during simulations.
- **/scaled_ready**: Confirms that the system is fully provisioned and ready for operations.

## How to Run the Project

1. Clone the repository:
   ```bash
   git clone https://github.com/vi00085/Cloud_Computing_6829480.git

## Project Contributors

- **Venkat Sandeep** (vi00085): Developer.

## References

1. Amazon Web Services, Inc. "Amazon EC2 Instance Types," AWS Documentation. 
2. Wikipedia, "Monte Carlo Simulation." 
3. Google Cloud, "Google App Engine Documentation," Google Cloud Documentation. 
