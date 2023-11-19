import asyncio
import time

import digitalocean

# regions = ['sfo3']
# size = "s-1vcpu-512mb-10gb"

regions = ['sfo3', 'tor1', 'fra1', 'blr1', 'syd1']
size = 's-1vcpu-1gb'  # 1GB RAM, 1 vCPU

cmd = f"""#!/bin/bash
apt install -y python3.11-venv unzip libssl-dev python3-dev
mkdir -p ~/doh3-measurements
cd ~/doh3-measurements
wget -O main.zip https://github.com/saurabhsjoshi/doh3-measurement/archive/refs/heads/main.zip
unzip main.zip
cd doh3-measurement-main
python3.11 -m venv ./venv
source ./venv/bin/activate
pip install -r requirements.txt
echo 'Starting main script'
./venv/bin/python3 main.py
echo 'Completed script'
"""


def create_droplet(do_region):
    """
    Start Digital Ocean droplets in given region
    :param do_region: Digital Ocean Region (Ex: sfo3)
    :return: created droplet
    """
    try:
        manager = digitalocean.Manager()
        keys = manager.get_all_sshkeys()
        droplet = digitalocean.Droplet(name=do_region + '-measurement',
                                       region=do_region,
                                       image='ubuntu-23-10-x64',
                                       size_slug=size,
                                       ssh_keys=keys,
                                       backups=False,
                                       user_data=cmd)
        droplet.create()

        actions = droplet.get_actions()
        droplet_ready = False
        while not droplet_ready:
            time.sleep(5)
            for action in actions:
                action.load()
                if action.status != 'in-progress':
                    droplet_ready = True
            print('Waiting for droplet readiness ', do_region)

        return droplet

    except Exception as e:
        print(e)


async def run_tasks():
    """
    Start droplets in given regions in parallel
    """
    result = await asyncio.gather(*(asyncio.to_thread(create_droplet, region) for region in regions))
    print(result)


if __name__ == "__main__":
    asyncio.run(run_tasks())
