# DNS-over-HTTP/3 measurements

# Setup Project

This project requires Python 3.9 and above. It was tested on Python 3.11 and Ubuntu 22.04. Following dependencies need
to be installed:

- `apt install libssl-dev python3-dev`
- `pip install -r requirements.txt`

The script requires Digital Ocean token to be populated in a environment variable called `DIGITALOCEAN_ACCESS_TOKEN`

# Project Structure

- `main` : Main script that will be executed on remote server to gather measurements
- `input` : Directory that contains input for the main script including list of DNS servers and list of websites to be
  tested
- `output`: Directory that will contain the output after the script has been run
- `deploy`: Deployer that deploys the main script to remote Digital Ocean droplets
- `teardown`: Script to download results and then stop and delete DO all droplets
  - <span style="color:red">WARNING: This script deletes **ALL** droplets, please review script before using</span> 