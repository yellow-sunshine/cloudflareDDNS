from urllib3.exceptions import HTTPError as BaseHTTPError
import sys
import re
import json
import requests
import random
import datetime
import os
import argparse
from pathlib import Path
'''
cloudflareDDNS
This was created so I could update dns records on cloudflare when my IP address changed
It uses ipify.org api to get your remote IP then updates the specified zone's dns on cloudflare
Requires Python 3.7 or later
Brent Russsell
www.brentrussell.com


Usage:
    - Using conguration built into cloudflare_ddns.py
    python3 cloudflare_ddns.py

    - Using an external config file
    python3 cloudflare_ddns.py /path/to/file/myzones.json


    

'''


# ['ZONE', 'RECORD', 'GLOBAL API_KEY at https://dash.cloudflare.com/profile', 'EMAIL@DOMAIN.COM', 'Proxy the domain', 'Enabled' ]
config = [
    ["myexample.com", "www.myexample.com", "API_KEY_HERE", "EMAIL@DOMAIN.COM", True, True],
    ["myexample.com", "@", "API_KEY_HERE", "EMAIL@DOMAIN.COM", True, True],
    ["ourexample.com", "ourexample.com", "API_KEY_HERE", "EMAIL@DOMAIN.COM", True, True],
    ["ourexample.com", "*.ourexample.com", "API_KEY_HERE", "EMAIL@DOMAIN.COM", True, True],
    ["yourexample.com", "home.yourexample.com", "API_KEY_HERE", "EMAIL@DOMAIN.COM", True, True]
]


if float(str(sys.version_info[0]) + '.' + str(sys.version_info[1])) < 3.6:
    raise_ex("Please upgrade to Python 3.7 or later", True)


def raise_ex(msg, terminate):
    print(msg)
    if terminate:
        resetIpJson()
        sys.exit(1)


def getURL(url, rtype, headers='', payload=''):
    try:
        if rtype.lower() == 'put':
            r = requests.put(url, headers=headers, data=payload)
        else:
            r = requests.get(url, headers=headers)
    except requests.exceptions.Timeout:
        raise_ex("Connection to " + url + " Timmed out", True)
    except requests.exceptions.TooManyRedirects:
        raise_ex(url + " has redirected too many times", True)
    except requests.exceptions.HTTPError as e:
        raise_ex('HTTP Error ' + e.response.status_code, True)
    except (requests.exceptions.ConnectionError, requests.exceptions.RequestException):
        raise_ex("Connection Error, could not connect to " + url, True)
    else:
        return r


def getIpProvider():
    ipProviders = {
        'https://api.ipify.org?format=json': 'ip',
        'https://ipapi.co/json/': 'ip',
        'https://api.bigdatacloud.net/data/client-ip': 'ipString',
        'https://checkip.amazonaws.com/': '',
        'https://ifconfig.me/ip': ''
    }
    return random.choice(list(ipProviders.items()))


def validIP(ipString):
    if re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ipString):
        return True
    else:
        return False


def remoteIP():
    try:
        provider, key = getIpProvider()
        ip = getURL(provider, 'get')
        if ip.content:
            if key:
                data = json.loads(ip.content)
                if not data[key]:
                    raise_ex("No IP returned from " + provider, True)
                elif not validIP(data[key]):
                    raise_ex("remoteIP method. A valid IP was not returned from " + provider, True)
                else:
                    return data[key].strip()
            elif validIP(ip.text):
                return ip.text.strip()
        else:
            raise_ex("remoteIP method. No content returned from " + provider, True)
    except KeyError:
        raise_ex("remoteIP method. Unable to find required key in json response from " + provider, False)
    except json.decoder.JSONDecodeError:
        raise_ex("remoteIP method. Not a valid json response from " + provider, True)


def updateNeeded(remote_ip):
    try:
        ipFile = open('ip.json', 'r')
        ipFilejson = json.load(ipFile)
        currentip = ipFilejson['currentip']
        lastip1 = ipFilejson['lastip1']
        lastip2 = ipFilejson['lastip2']
        lastip3 = ipFilejson['lastip3']
        lastip4 = ipFilejson['lastip4']
        ipFile.close()
    except FileNotFoundError:
        raise_ex("updateNeeded method. ip.json was not found", True)
    except PermissionError:
        raise_ex("updateNeeded method. Dont have permissions to open ip.json", True)
    except KeyError:
        raise_ex("updateNeeded method. Unable to find required keys in ip.json", True)
    except json.decoder.JSONDecodeError:
        raise_ex("updateNeeded method. ip.json does not contain proper json", True)
    if currentip != remote_ip:
        current_date = datetime.date.today()
        newjson = {
            "currentip": remote_ip,
            "lastip1": currentip,
            "lastip2": lastip1,
            "lastip3": lastip2,
            "lastip4": lastip3,
            "date": current_date
        }
        try:
            json_object = json.dumps(newjson, sort_keys=True, default=str, indent=4)
            with open("ip.json", "w") as ipFile:
                ipFile.write(json_object)
            ipFile.close()
        except PermissionError:
            raise_ex("Dont have permissions to write to ip.json", True)
        return True
    else:
        return False


def resetIpJson():
    try:
        ipFile = open('ip.json', 'r')
        ipFilejson = json.load(ipFile)
        ipFile.close()
        newjson = {
            "currentip": '0.0.0.0',
            "date": ipFilejson['date'],
            "lastip1": ipFilejson['lastip1'],
            "lastip2": ipFilejson['lastip2'],
            "lastip3": ipFilejson['lastip3'],
            "lastip4": ipFilejson['lastip4']
        }
        json_object = json.dumps(newjson, sort_keys=True, default=str, indent=4)
        with open("ip.json", "w") as ipFile:
            ipFile.write(json_object)
        ipFile.close()
    except PermissionError:
        raise_ex("Dont have permissions to write to ip.json", True)


def zoneData(headers, zone):
    try:
        zoneURL = 'https://api.cloudflare.com/client/v4/zones?name=' + zone
        data = getURL(zoneURL, 'get', headers)
        zone_data = json.loads(data.content)
        if len(zone_data['result']) > 0:
            if not zone_data['result'][0]['id']:
                raise_ex('zoneData method. Zone ' + zone + ' not found', False)
            else:
                return zone_data['result'][0]['id']
        else:
            return False
    except json.decoder.JSONDecodeError:
        raise_ex("zoneData method. Not a valid json response from Cloudflare", False)
    except TypeError:
        raise_ex("zoneData method. TypeError. This usually happens when the record does not exist", False)
    except KeyError:
        raise_ex("zoneData method. Unable to find result key in json response from Cloudflare", False)


def recordData(headers, zone_id, record):
    try:
        data = getURL('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records?name=' + record, 'get', headers)
        record_data = json.loads(data.content)
        print(record)
        if len(record_data['result']) > 0:
            if not record_data['result'][0]['id']:
                raise_ex('recordData method. Record ' + record + ' not found', False)
            else:
                return record_data['result'][0]['id']
        else:
            return False
    except json.decoder.JSONDecodeError:
        raise_ex("recordData method. Not a valid json response from Cloudflare", False)
    except KeyError:
        raise_ex("recordData method. Unable to find result key in json response from Cloudflare", False)
    except TypeError:
        raise_ex("recordData method. TypeError. This usually happens when the record does not exist", False)


def listToDict(lst):
    op = {lst[i]: lst[i + 1] for i in range(0, len(lst), 2)}
    return op


def updateRecord(headers, zone_id, record, record_id, remote_ip, proxied_state):
    try:
        payload = dict(type="A", name=record, content=remote_ip, ttl=1, proxied=proxied_state)
        data = getURL('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records/' + record_id, 'put', headers, json.dumps(payload))
        update = json.loads(data.content)
        if update['success']:
            return 'success'
        else:
            return update['errors'][0]['message']
    except KeyError:
        raise_ex("updateRecord method. Unable to find required key in json response from Cloudflare api", False)
    except json.decoder.JSONDecodeError:
        raise_ex("updateRecord method. Not a valid json response from Cloudflare api", False)
    except TypeError:
        raise_ex("updateRecord method. TypeError. This usually happens when the record does not exist", False)


def argvs():
    n = len(sys.argv)
    if not n > 1:
        return config
    elif n > 2:
        raise_ex("1 argument expected, more than 1 passed", True)
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument("configFile")
        args = parser.parse_args()
        if not os.path.isfile(args.configFile):
            raise_ex("The passed config file does not exist", True)
        else:
            try:
                h = open(args.configFile, 'r')
                zoneFilejson = json.load(h)
                h.close()
            except FileNotFoundError:
                raise_ex("argvs method. " + args.configFile + " was not found", True)
            except PermissionError:
                raise_ex("argvs method. Invalid permissions trying to open " + args.configFile, True)
            except json.decoder.JSONDecodeError:
                raise_ex("argvs method. " + args.configFile + " is not a valid json file", True)
            outer = 0
            outerConfig = []
            for item in zoneFilejson:
                innerConfig = []
                innerConfig.extend([0, 1, 2, 3, 4, 5])
                for key in item:
                    if key == 'zone':
                        innerConfig[0] = zoneFilejson[outer][key]
                    elif key == 'record':
                        innerConfig[1] = zoneFilejson[outer][key]
                    elif key == 'global_api_key':
                        innerConfig[2] = zoneFilejson[outer][key]
                    elif key == 'cloudflare_email':
                        innerConfig[3] = zoneFilejson[outer][key]
                    elif key == 'proxied_state':
                        innerConfig[4] = zoneFilejson[outer][key]
                    elif key == 'enabled':
                        innerConfig[5] = zoneFilejson[outer][key]
                    else:
                        continue
                    # innerConfig.append(zoneFilejson[outer][key])
                outerConfig.append(innerConfig)
                outer += 1
            print("Updating DNS records from", args.configFile)
            return outerConfig


def main():
    # Get the remote IP of this machine
    remote_ip = remoteIP()
    # Decide if the new IP is different than the last
    newIPDetected = updateNeeded(remote_ip)
    # Even if it is not differnet, lets force an update on avg once ever 4hrs
    updateDNS = False
    if not newIPDetected:
        if random.randint(1, 240) == 100:
            updateDNS = True
    else:
        updateDNS = True
    if updateDNS:
        total_updates = 0
        total_errors = 0
        if len(remote_ip) > 6:
            for i in range(len(config)):
                # Set headers to be used with cloudflare
                headers = {
                    'Content-Type': 'application/json',
                    'X-Auth-Key': config[i][2],
                    'X-Auth-Email': config[i][3]
                }
                zone_id = zoneData(headers, config[i][0])  # Get Zone ID
                if i == 0:
                    print('\n Starting....\n')
                if i > 0:
                    print('-----------------------------------------\n')
                if zone_id:
                    if config[i][1] == '' or config[i][1] == '@' or config[i][1] == '.':  # If there is no sub domain
                        config[i][1] = config[i][0]
                    record_id = recordData(headers, zone_id, config[i][1])  # Get record ID
                    if record_id:
                        if not config[i][5]:
                            print(config[i][1], "Not enabled, skipping.")
                            continue
                        try:
                            results = updateRecord(headers, zone_id, config[i][1], record_id, remote_ip, config[i][4])
                        except IndexError:
                            total_errors += 1
                            raise_ex("Index Error occurred, Check configuration values", False)
                        if results == 'success':
                            print('DNS for ' + config[i][1] + ' updated to ' + remote_ip)
                            total_updates += 1
                        else:
                            exists = re.search('already exists', results, flags=re.IGNORECASE)
                            if exists is not None:
                                print('DNS for ' + config[i][1] + ' already updated to ' + remote_ip)
                                total_updates += 1
                            else:
                                print('Error updating DNS for ' + config[i][1] + ' to ' + remote_ip + ':' + results)
                    else:
                        print('Error getting record id for ' + config[i][1] + ', DNS not updated')
                        total_errors += 1
                else:
                    print('Error getting zone id for ' + config[i][0] + ', DNS not updated')
                    total_errors += 1
            print(f'\n################# RESULTS #################\n{total_updates} record(s) updated and {total_errors} error(s)\n')
        else:
            print("Could not obtain IP from https://api.ipify.org?format=json")
    else:
        print('No updated needed. Ip address', remote_ip, 'has not changed')


config = argvs()
main()
