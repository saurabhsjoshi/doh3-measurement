import asyncio
import base64
import csv
import datetime
import json
from typing import cast
from urllib.parse import urlparse

import httpx
from aioquic.asyncio.client import connect
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from dnslib import DNSRecord

from http3_client import H3Transport

HTTP_CLIENT_TIMEOUT = 4.0


async def doh2(query):
    """
    Perform DNS-over-HTTPS query.
    :param query: URI consisting of the DNS query URI
    :return: dictionary containing the result
    """
    async with httpx.AsyncClient(http2=True, timeout=HTTP_CLIENT_TIMEOUT) as client:
        response = await client.get(query)
        elapsed_ms = round(response.elapsed.microseconds * .001, 6)
        return {
            'time_ms': elapsed_ms,
            'http_status': str(response.status_code),
            'http_version': str(response.http_version)
        }


async def doh3(query):
    """
    Performs DNS-over-HTTP/3 query using the aioquic library
    :param query: URI consisting of the DNS query URI
    :return: dictionary containing the result
    """
    parsed = urlparse(query)
    host = parsed.hostname
    port = 443
    configuration = QuicConfiguration(is_client=True, alpn_protocols=H3_ALPN)
    configuration.idle_timeout = HTTP_CLIENT_TIMEOUT
    async with connect(
            host=host,
            port=port,
            configuration=configuration,
            create_protocol=H3Transport
    ) as transport:
        async with httpx.AsyncClient(transport=cast(httpx.AsyncBaseTransport, transport),
                                     timeout=HTTP_CLIENT_TIMEOUT) as client:
            start = datetime.datetime.now()
            response = await client.get(query, headers={"accept": "application/dns-message"})
            end = datetime.datetime.now()
            delta = end - start
            elapsed_ms = round(delta.microseconds * .001, 6)
            return {
                'time_ms': elapsed_ms,
                'http_status': str(response.status_code),
                'http_version': str(response.http_version),
                # DNS response has been removed as it increases result size
                # 'response': str(DNSRecord.parse(response.content))
            }


def get_dns_query(url):
    """
    Creates a DNS question query and returns it as a base 64 encoded string as defined in RFC 8484
    :param url: URL of the website that is to be queried (Ex: google.com)
    :return: base 64 encoded string that can be used to query a DNS server
    """
    query = DNSRecord.question(url)
    data = base64.urlsafe_b64encode(query.pack())
    return data.decode("ascii").strip("=")


if __name__ == "__main__":
    total_start_time = datetime.datetime.now()
    print("Start Time: ", total_start_time)

    # Use the following capture mechanism to capture a pcap file to analyze network traffic
    # with capture_packets() as pcap:
    # pcap.tarball(path="/home/saurabh/Desktop/test3.tar.gz")

    results = []
    dns_servers = json.load(open('input/dns_servers.json'))
    with open("input/websites.csv", "r") as f:
        websites = csv.reader(f)
        for website in websites:
            for server in dns_servers:
                # Check if DNS server has been marked to not execute
                if not server.get("execute", True):
                    continue

                query_url = "https://" + server['address'] + "/dns-query?dns=" + get_dns_query(website[1])

                # Construct result
                result = {
                    "website": website[1],
                    "dns_server": server['name']
                }

                try:
                    result["doh_result"] = asyncio.run(doh2(query=query_url))
                except Exception as ex:
                    result["doh_result"] = dict({
                        'time_ms': -1,
                        'http_status': '-1',
                        'http_version': '-1',
                        'error': str(ex)
                    })

                try:
                    result["doh3_result"] = asyncio.run(doh3(query=query_url))
                except Exception as ex:
                    result["doh3_result"] = dict({
                        'time_ms': -1,
                        'http_status': '-1',
                        'http_version': '-1',
                        'error': str(ex)
                    })

                results.append(result)

            print("Completed website ", website[0])

        total_end_time = datetime.datetime.now()
        print("End Time: ", total_end_time)
        total_delta = total_end_time - total_start_time

        with open('output/result.json', 'w') as output_file:
            json.dump({
                "data": results,
                "total_time": total_delta.seconds
            }, output_file)
