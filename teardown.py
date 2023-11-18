import json

import digitalocean
import paramiko
from paramiko.client import SSHClient
from scp import SCPClient
from datetime import datetime


def download_results(do_ip, output_path):
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(do_ip, username='root')
    with SCPClient(ssh.get_transport()) as scp:
        scp.get('/var/log/cloud-init-output.log', output_path + '.log')
        scp.get('/root/doh3-measurements/doh3-measurement-main/output/result.json', output_path + '.json')


if __name__ == "__main__":
    manager = digitalocean.Manager()
    droplets = manager.get_all_droplets()
    now = datetime.now().strftime("%Y%m%d%H%M%S")

    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    # WARNING: THIS WILL DELETE ALL DROPLETS IN ASSOCIATED ACCOUNT
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    for droplet in droplets:
        droplet.load()
        print("Downloading results from", droplet.region['slug'])
        result_path = 'output/' + droplet.region['slug'] + '_' + now
        try:
            download_results(droplet.ip_address, result_path)
        except Exception as ex:
            with open(result_path + '.json', 'w') as output_file:
                json.dump({
                    "download_error": str(ex)
                }, output_file)
            print(ex)
        droplet.destroy()
