import asyncio
import base64
import csv
import datetime
import json
import socket
from typing import cast
from urllib.parse import urlparse

import httpx
from aioquic.asyncio.client import connect
from aioquic.h3.connection import H3_ALPN
from aioquic.quic.configuration import QuicConfiguration
from dnslib import DNSRecord, QTYPE

from http3_client import H3Transport

HTTP_CLIENT_TIMEOUT = 1.5


async def resolve_dns_server(dns_server):
    # Ask the DNS provider for the best IP address to use for their service
    query = "https://1.1.1.1/dns-query?dns=" + get_dns_query(dns_server)
    async with httpx.AsyncClient(http2=True, timeout=HTTP_CLIENT_TIMEOUT + 1.0) as client:
        response = await client.get(query)
        record = DNSRecord.parse(response.content)
        ip_addr = ""
        for rr in record.rr:
            if rr.rtype == QTYPE.A:
                ip_addr = str(rr.rdata)
                break

        if not ip_addr:
            raise Exception("Could not resolve IP address for DNS Server")

        return ip_addr


def do53(dns_server, query):
    """
    Perform traditional DNS query over port 53
    :param dns_server: IP of the DNS server
    :param query: Raw DNS query
    :return: dictionary containing the result
    """
    address = (dns_server, 53)
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(HTTP_CLIENT_TIMEOUT)
    start = datetime.datetime.now()
    client.sendto(query, address)
    response, _ = client.recvfrom(1024)
    end = datetime.datetime.now()
    delta = end - start
    elapsed_ms = round(delta.microseconds * .001, 6)
    return dict({
        'ms': elapsed_ms,
    })


async def doh2(query):
    """
    Perform DNS-over-HTTPS query.
    :param query: DNS query that is to be executed
    :return: dictionary containing the result
    """
    async with httpx.AsyncClient(http2=True, timeout=HTTP_CLIENT_TIMEOUT, verify=False) as client:
        response = await client.get(query)
        elapsed_ms = round(response.elapsed.microseconds * .001, 6)
        return dict({
            'ms': elapsed_ms
        })


async def doh3(query):
    """
    Performs DNS-over-HTTP/3 query using the aioquic library
    :param query: DNS query that is to be executed
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
                                     timeout=HTTP_CLIENT_TIMEOUT, verify=False) as client:
            start = datetime.datetime.now()
            await client.get(query, headers={"accept": "application/dns-message"})
            end = datetime.datetime.now()
            delta = end - start
            elapsed_ms = round(delta.microseconds * .001, 6)
            return dict({
                'ms': elapsed_ms,
                # DNS response and response has been removed as it increases result size
                # 'http_status': str(response.status_code),
                # 'http_version': str(response.http_version),
                # 'response': str(DNSRecord.parse(response.content))
            })


def get_raw_dns_query(url):
    """
    Creates a raw DNS question query
    :param url: URL of the website that is to be queried (Ex: google.com)
    :return: raw dns question query
    """
    query = DNSRecord.question(url)
    return query.pack()


def get_dns_query(url):
    """
    Creates a DNS question query and returns it as a base 64 encoded string as defined in RFC 8484
    :param url: URL of the website that is to be queried (Ex: google.com)
    :return: base 64 encoded string that can be used to query a DNS server
    """
    data = base64.urlsafe_b64encode(get_raw_dns_query(url))
    return data.decode("ascii").strip("=")


if __name__ == "__main__":
    total_start_time = datetime.datetime.now()
    print("Start Time: ", total_start_time)

    # Use the following capture mechanism to capture a pcap file to analyze network traffic
    # with capture_packets() as pcap:
    # pcap.tarball(path="/home/saurabh/Desktop/test3.tar.gz")

    results = []
    cached_dns = {}
    dns_servers = json.load(open('input/dns_servers.json'))
    with open("input/websites.csv", "r") as f:
        websites = csv.reader(f)
        for website in websites:
            # Construct result for website
            website_result = dict({
                "w": website[1]
            })
            for server in dns_servers:
                # Check if DNS server has been marked to not execute
                if not server.get("execute", True):
                    continue

                # Construct result
                result = dict({})

                # Check if DNS server requires resolution
                if server.get('requires_resolution', False):
                    if server['id'] not in cached_dns:
                        try:
                            addr = asyncio.run(resolve_dns_server(server['address']))
                            cached_dns[server['id']] = addr
                        except Exception as ex:
                            print(ex)
                            # DNS Resolution Failed
                            result["drf"] = dict({
                                "er": str(ex)
                            })
                            website_result[server['id']] = result
                            continue
                    server['address'] = cached_dns[server['id']]

                if not server.get('disable_do53', False):
                    try:
                        result['do53_result'] = do53(server['address'], get_raw_dns_query(website[1]))
                    except Exception as ex:
                        result["do53_result"] = dict({
                            'ms': -1.0,
                            'er': str(ex)
                        })

                # Create URI for DNS-over-HTTP queries
                query_url = "https://" + server['address'] + "/dns-query?dns=" + get_dns_query(website[1])

                try:
                    result["doh_result"] = asyncio.run(doh2(query=query_url))
                except Exception as ex:
                    result["doh_result"] = dict({
                        'ms': -1.0,
                        'er': str(ex)
                    })

                try:
                    result["doh3_result"] = asyncio.run(doh3(query=query_url))
                except Exception as ex:
                    result["doh3_result"] = dict({
                        'ms': -1.0,
                        'er': str(ex)
                    })
                website_result[server['id']] = result

            results.append(website_result)
            print("Completed website ", website[0], flush=True)

        total_end_time = datetime.datetime.now()
        print("End Time: ", total_end_time)
        total_delta = total_end_time - total_start_time

        with open('output/result.json', 'w') as output_file:
            json.dump({
                "tt": total_delta.seconds,
                "data": results,
            }, output_file)
