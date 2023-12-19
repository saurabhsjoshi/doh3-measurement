"""
This module is used for analyzing results. The collected JSON files need to be placed under ./results directory.
"""
import json
import os
from statistics import median, mean
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from prettytable import PrettyTable
from scipy.stats import scoreatpercentile, ttest_ind


class TermColors:
    """
    Terminal style obtained from Stackoverflow
    https://stackoverflow.com/a/293633
    """
    HEADER = '\033[95m'
    OK_BLUE = '\033[94m'
    OK_CYAN = '\033[96m'
    OK_GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END_C = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


result_dir = 'results'


def get_general_stats():
    locations = ['blr1', 'fra1', 'sfo3', 'syd1', 'tor1']
    collected = 0
    errors = 0
    loc_c = [0, 0, 0, 0, 0]
    loc_err = [0, 0, 0, 0, 0]
    res = {
        "do53_result": {
            "name": 'Do53',
            "count": 0,
            "error": 0,
            "total": 0.0,
            "average": 0.0,
            "values": []
        },
        "doh_result": {
            "name": 'DoH',
            "count": 0,
            "error": 0,
            "total": 0.0,
            "average": 0.0,
            "values": []
        },
        "doh3_result": {
            "name": 'DoH3',
            "count": 0,
            "error": 0,
            "total": 0.0,
            "average": 0.0,
            "values": []
        }
    }
    for file in os.scandir(result_dir):
        if not file.path.endswith('.json'):
            continue
        collected = collected + 1
        loc_idx = locations.index(file.name.split('_')[0])
        loc_c[loc_idx] = loc_c[loc_idx] + 1

        r = json.load(open(file))
        if "tt" not in r:
            errors = errors + 1
            loc_err[loc_idx] = loc_err[loc_idx] + 1
            continue
        data = r['data']
        for d in data:
            for attr in d:
                if attr == 'w':
                    continue
                w_result = d[attr]
                for w_attr in w_result:
                    res[w_attr]["count"] = res[w_attr]["count"] + 1
                    if 'er' in w_result[w_attr]:
                        res[w_attr]["error"] = res[w_attr]["error"] + 1
                        continue
                    res[w_attr]['values'].append(w_result[w_attr]['ms'])
                    res[w_attr]['total'] = res[w_attr]['total'] + w_result[w_attr]['ms']

    print(TermColors.UNDERLINE, "Collection Stats", TermColors.END_C)
    table = PrettyTable(['Location', 'Total', 'Errors'])
    for idx, loc in enumerate(locations):
        table.add_row([loc, loc_c[idx], loc_err[idx]])
    table.add_row(['Total', collected, errors])
    print(table)

    print(TermColors.UNDERLINE, "Query Stats", TermColors.END_C)
    table = PrettyTable(['Query Type', 'Total', 'Errors', 'Average(ms)', 'Median(ms)', '95th Percentile'])
    for entry in res:
        count = res[entry]['count'] - res[entry]['error']
        res[entry]['average'] = res[entry]['total'] / float(count)
        table.add_row([res[entry]['name'], res[entry]['count'], res[entry]['error'], res[entry]['average'],
                       median(res[entry]['values']), scoreatpercentile(res[entry]['values'], 95)])

    print(table)


class Entry:
    website: str = ''
    type: str = ''
    dns_provider = ''
    location = ''
    timestamp = ''
    value: float = -1.0

    def __init__(self, w, t, dns, loc, time, val):
        self.website = w
        self.type = t
        self.dns_provider = dns
        self.location = loc
        self.timestamp = time
        self.value = val


def build_histogram(loc_data: list[float]):
    x = pd.Series(loc_data)
    bins = np.geomspace(x.min(), x.max(), 8)
    plt.hist(x, density=True, bins=bins)
    plt.xscale('log')
    plt.ylabel('Probability')
    plt.xlabel('Time(ms)')

    # q25 = scoreatpercentile(loc_data, 25)
    # q75 = scoreatpercentile(loc_data, 75)
    # bin_width = 2 * (q75 - q25) * len(loc_data) ** (-1 / 3)
    # bins = round((max(loc_data) - min(loc_data)) / bin_width)
    # plt.hist(loc_data, density=True, bins=8)
    # plt.ylabel('Probability')
    # plt.xlabel('Data')
    # plt.hist(loc_data, bins=8, density=True, cumulative=True, label='CDF',
    #          histtype='step', alpha=0.8, color='k')


class Measurements:
    dns_providers = {
        "1": "Google",
        "2": "Cloudflare",
        "3": "NextDNS",
        "4": "AdGuard",
        "5": "ControlD"
    }
    data: list[Entry] = []

    def __init__(self):
        self.data = []

    def load(self):
        """
        Creates an internal structure containing all measurements for further analysis
        """
        for file in os.scandir(result_dir):
            if not file.path.endswith('.json'):
                continue
            result = json.load(open(file))

            # Ignore invalid measurements JSON
            if "tt" not in result:
                continue

            filename_split = file.name.split('_')
            location = filename_split[0]
            timestamp = filename_split[1].split('.')[0]
            data = result['data']
            for w in data:
                website = w['w']
                for attr in w:
                    if attr == 'w':
                        continue

                    result = w[attr]
                    # For Google & Cloudflare add Do53
                    if attr == '1' or attr == '2':
                        self.add_result(
                            website,
                            self.dns_providers[attr],
                            location,
                            timestamp,
                            'Do53',
                            result['do53_result'])

                    self.add_result(
                        website,
                        self.dns_providers[attr],
                        location,
                        timestamp,
                        'DoH',
                        result['doh_result'])

                    self.add_result(
                        website,
                        self.dns_providers[attr],
                        location,
                        timestamp,
                        'DoH3',
                        result['doh3_result'])

    def add_result(self, website, dns, location, timestamp, m_type, obj):
        if 'er' not in obj:
            entry = Entry(w=website, t=m_type, dns=dns, loc=location, time=timestamp, val=obj['ms'])
            self.data.append(entry)

    def get_values(self, m_type=None, location=None) -> list[float]:
        vals: list[float] = []
        for dat in self.data:
            if m_type is not None and dat.type != m_type:
                continue
            if location is not None and dat.location != location:
                continue
            vals.append(dat.value)
        return vals

    def mean_median_by_loc(self, m_type):
        vals: dict[str, list[float]] = {}
        for dat in self.data:
            if dat.type != m_type:
                continue
            if dat.location not in vals:
                vals[dat.location] = []
            vals[dat.location].append(dat.value)

        table = PrettyTable(
            ['Location', 'Mean(ms)', '25th Percentile', 'Median(ms)', '75th Percentile', '95th Percentile'])
        for val in vals:
            table.add_row([
                val,
                round(mean(vals[val]), 3),
                round(scoreatpercentile(vals[val], 25), 3),
                round(median(vals[val]), 3),
                round(scoreatpercentile(vals[val], 75), 3),
                round(scoreatpercentile(vals[val], 95), 3)
            ])
        print(table)

        return vals

    def mean_median_by_provider(self, m_type):
        vals: dict[str, list[float]] = {}
        for dat in self.data:
            if dat.type != m_type:
                continue
            if dat.dns_provider not in vals:
                vals[dat.dns_provider] = []
            vals[dat.dns_provider].append(dat.value)

        table = PrettyTable(
            ['Provider', 'Mean(ms)', '25th Percentile', 'Median(ms)', '75th Percentile', '95th Percentile'])
        for val in vals:
            table.add_row([
                val,
                round(mean(vals[val]), 2),
                round(scoreatpercentile(vals[val], 25), 2),
                round(median(vals[val]), 2),
                round(scoreatpercentile(vals[val], 75), 2),
                round(scoreatpercentile(vals[val], 95), 2)
            ])
        print(table)

        return vals

    def mean_median_by_type(self):
        vals: dict[str, list[float]] = {}
        for dat in self.data:
            # if dat.dns_provider != 'Google' and dat.dns_provider != 'Cloudflare':
            #     continue

            if dat.type not in vals:
                vals[dat.type] = []
            vals[dat.type].append(dat.value)

        table = PrettyTable(
            ['Type', 'Mean(ms)', '25th Percentile', 'Median(ms)', '75th Percentile', '95th Percentile'])
        for val in vals:
            table.add_row([
                val,
                round(mean(vals[val]), 2),
                round(scoreatpercentile(vals[val], 25), 2),
                round(median(vals[val]), 2),
                round(scoreatpercentile(vals[val], 75), 2),
                round(scoreatpercentile(vals[val], 95), 2)
            ])
        print(table)

        return vals

    def mean_median_by_loc_and_type(self):
        vals: dict[(str, str), list[float]] = {}
        for dat in self.data:
            # if dat.dns_provider != 'Google' and dat.dns_provider != 'Cloudflare':
            #     continue
            if (dat.location, dat.type) not in vals:
                vals[(dat.location, dat.type)] = []
            vals[(dat.location, dat.type)].append(dat.value)

        table = PrettyTable(
            ['Type', 'Mean(ms)', '25th Percentile', 'Median(ms)', '75th Percentile', '95th Percentile'])
        for val in vals:
            table.add_row([
                val,
                round(mean(vals[val]), 3),
                round(scoreatpercentile(vals[val], 25), 3),
                round(median(vals[val]), 3),
                round(scoreatpercentile(vals[val], 75), 3),
                round(scoreatpercentile(vals[val], 95), 3)
            ])
        print(table)

        return vals

    def mean_median_by_provider_and_type(self):
        vals: dict[(str, str), list[float]] = {}
        for dat in self.data:
            # if dat.dns_provider != 'Google' and dat.dns_provider != 'Cloudflare':
            #     continue

            if (dat.dns_provider, dat.type) not in vals:
                vals[(dat.dns_provider, dat.type)] = []

            vals[(dat.dns_provider, dat.type)].append(dat.value)

        table = PrettyTable(
            ['Type', 'Mean(ms)', '25th Percentile', 'Median(ms)', '95th Percentile'])
        for val in vals:
            table.add_row([
                val,
                round(mean(vals[val]), 2),
                round(scoreatpercentile(vals[val], 25), 2),
                round(median(vals[val]), 2),
                round(scoreatpercentile(vals[val], 95), 2)
            ])
        print(table)

        return vals

    def mean_median_by_top_bottom_websites(self):
        vals: dict[(str, str), list[float]] = {}
        top_websites = ['google.com', 'amazonaws.com', 'facebook.com', 'microsoft.com', 'apple.com']
        middle_websites = ['eldoradosfun.xyz', 'mayflower.dk', 'volnacasino-serdce12.top', 'champions.host', 'trivago.com.co']
        bottom_websites = ['vavadaz.com', 'search12.online', 'salewings.com', 'ix.ua', 'uscbinc.com']
        for dat in self.data:
            if dat.website in top_websites:
                if ('TOP5', dat.type) not in vals:
                    vals[('TOP5', dat.type)] = []
                vals[('TOP5', dat.type)].append(dat.value)

            elif dat.website in middle_websites:
                if ('MIDDLE5', dat.type) not in vals:
                    vals[('MIDDLE5', dat.type)] = []
                vals[('MIDDLE5', dat.type)].append(dat.value)

            elif dat.website in bottom_websites:
                if ('BOTTOM5', dat.type) not in vals:
                    vals[('BOTTOM5', dat.type)] = []
                vals[('BOTTOM5', dat.type)].append(dat.value)
            else:
                continue

        table = PrettyTable(
            ['Type', 'Mean(ms)', 'Median(ms)', '95th Percentile'])
        for val in vals:
            table.add_row([
                val,
                round(mean(vals[val]), 2),
                round(median(vals[val]), 2),
                round(scoreatpercentile(vals[val], 95), 2)
            ])
        print(table)

        return vals


if __name__ == "__main__":
    m = Measurements()
    m.load()

    # ##GET GENERAL STATS##
    # get_general_stats()

    # ## GET DATA BASED ON PROVIDER
    # provider_type_data = m.mean_median_by_provider_and_type()
    # fig = plt.figure(figsize=(6, 3), layout="constrained")
    # plt.ecdf(provider_type_data[('Cloudflare', 'DoH')], label="DoH", linewidth=2)
    # plt.ecdf(provider_type_data[('Cloudflare', 'Do53')], label="Do53", linewidth=2)
    # plt.ecdf(provider_type_data[('Cloudflare', 'DoH3')], label="DoH3", linewidth=2)
    # plt.legend()
    # plt.grid(True)
    # plt.xlabel("Response Time (ms)")
    # plt.ylabel("Probability")

    provider_type_data = m.mean_median_by_top_bottom_websites()
    fig = plt.figure(figsize=(6, 3), layout="constrained")
    plt.ecdf(provider_type_data[('TOP5', 'DoH3')], label="Top 5", linewidth=2)
    plt.ecdf(provider_type_data[('MIDDLE5', 'DoH3')], label="Middle 5", linewidth=2)
    plt.ecdf(provider_type_data[('BOTTOM5', 'DoH3')], label="Bottom 5", linewidth=2)
    plt.legend()
    plt.grid(True)
    plt.xlabel("Response Time (ms)")
    plt.ylabel("Probability")

    # ## GET DATA BASED ON Type (DoH, Do53, DoH3)
    # type_data = m.mean_median_by_type()
    # fig = plt.figure(figsize=(6, 3), layout="constrained")
    # plt.ecdf(type_data['DoH'], label="DoH", linewidth=2)
    # plt.ecdf(type_data['Do53'], label="DoH", linewidth=2)
    # plt.ecdf(type_data['DoH3'], label="DoH3", linewidth=2)
    # plt.legend()
    # plt.grid(True)
    # plt.xlabel("Response Time (ms)")
    # plt.ylabel("Probability")

    # ## GET DATA BASED ON LOCATION AND TYPE
    # loc_data = m.mean_median_by_loc_and_type()
    # fig = plt.figure(figsize=(6, 3), layout="constrained")
    # plt.ecdf(loc_data[('tor1', 'DoH')], label="DoH", linewidth=2)
    # plt.ecdf(loc_data[('tor1', 'DoH3')], label="DoH3", linewidth=2)
    # plt.legend()
    # plt.grid(True)
    # plt.xlabel("Response Time (ms)")
    # plt.ylabel("Probability")

    # axs = fig.subplots(1, 2, sharex=True, sharey=True)
    # # Cumulative distributions.plt.rcParams.update({'legend.linewidth': 10})
    # axs[0].ecdf(type_data['DoH'], label="DoH")1
    # axs[0].ecdf(type_data['DoH3'], label="DoH3")
    # x = np.linspace(min(data), max(data))
    # y = ((1 / (np.sqrt(2 * np.pi) * 25)) *
    #      np.exp(-0.5 * (1 / 25 * (x - 200)) ** 2))
    # y = y.cumsum()
    # y /= y[-1]
    # fig.suptitle("Cumulative distributions")
    # for ax in axs:
    #     ax.grid(True)
    #     ax.legend()
    #     ax.set_xlabel("Response Time (ms)")
    #     ax.set_ylabel("Probability")
    #     ax.label_outer()

    # plt.show()

    # First we test variation DoH3 between all locations
    # l_data = m.mean_median_by_loc("DoH3")

    # m.mean_median_by_provider("DoH")

    # h3_provider_data = m.mean_median_by_provider("DoH3")

    # print(round(ttest_ind(h3_provider_data['ControlD'], h3_provider_data['NextDNS']).pvalue, 5))

    # plt.rcParams.update({'figure.figsize': (7, 5), 'figure.dpi': 100})
    # plt.figure(1)
    # plt.title("Bangalore")
    # build_histogram(l_data['blr1'])
    # plt.figure(2)
    # plt.title("Frankfurt")
    # build_histogram(l_data['fra1'])
    # plt.figure(3)
    # plt.title("San Fransisco")
    # build_histogram(l_data['sfo3'])
    # plt.figure(4)
    # plt.title("Sydney")
    # build_histogram(l_data['syd1'])
    # plt.figure(5)
    # plt.title("Toronto")
    # build_histogram(l_data['tor1'])

    plt.show()
