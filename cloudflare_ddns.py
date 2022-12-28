'''
cloudflareDDNS

This script was created so I could update a dns record on cloudflare when my IP address changed
It uses 3 different APIs to get your remote IP then updates the specified zone's dns on cloudflare

Requires Python 3.7 or later.
Edit zones.json to add your own zones to be updated. 
Make sure ip.json has write permissions
Set cloudflare.py to run on a cron job

Brent Russsell
www.brentrussell.com
'''

from urllib3.exceptions import HTTPError as BaseHTTPError
import sys
import re
import json
import requests
import datetime
import random


if float(str(sys.version_info[0]) + '.' + str(sys.version_info[1])) < 3.6:
    raise_ex("Please upgrade to Python 3.7 or later", True)


def raise_ex(msg, terminate):
    print(msg)
    terminate and resetIpJson() and sys.exit(1)


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
        'https://api.bigdatacloud.net/data/client-ip': 'ipString'
    }
    return random.choice(list(ipProviders.items()))


def remoteIP():
    try:
        provider, key = getIpProvider()
        ip = getURL(provider, 'get')
        if not ip.content:
            print(provider + "Did not respond with content")
            provider, key = getIpProvider()
            print('Trying again with ' + provider)
            ip = getURL(provider, 'get')
        if ip.content:
            data = json.loads(ip.content)
            if not data[key]:
                raise_ex("No IP returned from " + provider, True)
            elif not re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", data[key]):
                raise_ex("A valid IP was not returned from " + provider, True)
            else:
                return data[key]
        else:
            raise_ex("No content returned from " + provider, True)
    except KeyError:
        raise_ex(
            "Unable to find required key in json response from " + provider, False)
    except json.decoder.JSONDecodeError:
        raise_ex("Not a valid json response from " + provider, False)


def zoneData(headers, zone):
    try:
        data = getURL(
            'https://api.cloudflare.com/client/v4/zones?name=' + zone, 'get', headers)
        zone_data = json.loads(data.content)
        if len(zone_data['result']) > 0:
            if not zone_data['result'][0]['id']:
                raise_ex(
                    "Zone not found, no ID returned from Cloudflare api", False)
            else:
                return zone_data['result'][0]['id']
        else:
            raise_ex(
                "Not a valid json response from Cloudflare, result key not found or no content returned while attempting to obtain zone id", False)
    except json.decoder.JSONDecodeError:
        raise_ex("Not a valid json response from Cloudflare", False)
    except KeyError:
        raise_ex(
            "Unable to find result key in json response from Cloudflare", False)


def recordData(headers, zone_id, record):
    try:
        data = getURL('https://api.cloudflare.com/client/v4/zones/' +
                      zone_id + '/dns_records?name=' + record, 'get', headers)
        record_data = json.loads(data.content)
        if len(record_data['result']) > 0:
            if not record_data['result'][0]['id']:
                raise_ex(
                    "Record not found, no ID returned from Cloudflare api", False)
            else:
                return record_data['result'][0]['id']
        else:
            raise_ex(
                "Not a valid json response from Cloudflare, result key not found or no content returned while attempting to obtain record id", False)
    except json.decoder.JSONDecodeError:
        raise_ex("Not a valid json response from Cloudflare", False)
    except KeyError:
        raise_ex(
            "Unable to find result key in json response from Cloudflare", False)


def updateRecord(headers, zone_id, record_id, record, remote_ip, proxied_state):
    try:
        payload = dict(type="A", name=record, content=remote_ip,
                       ttl=1, proxied=proxied_state)
        data = getURL('https://api.cloudflare.com/client/v4/zones/' + zone_id +
                      '/dns_records/' + record_id, 'put', headers, json.dumps(payload))
        update = json.loads(data.content)
        if update['success']:
            return 'success'
        else:
            return update['errors'][0]['message']
    except KeyError:
        raise_ex(
            "Unable to find required key in json response from Cloudflare api", False)
    except json.decoder.JSONDecodeError:
        raise_ex("Not a valid json response from Cloudflare api", False)
    except TypeError:
        raise_ex(
            "TypeError. This usually happens when the DNS record does not exist while attempting to update", False)


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
        raise_ex("ip.json was not found", True)
    except PermissionError:
        raise_ex("Dont have permissions to open ip.json", True)
    except KeyError:
        raise_ex("Unable to find required keys in ip.json", True)
    except json.decoder.JSONDecodeError:
        raise_ex("ip.json does not contain proper json", True)
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
            json_object = json.dumps(
                newjson, sort_keys=True, default=str, indent=4)
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
        json_object = json.dumps(
            newjson, sort_keys=True, default=str, indent=4)
        with open("ip.json", "w") as ipFile:
            ipFile.write(json_object)
        ipFile.close()
    except PermissionError:
        raise_ex("Dont have permissions to write to ip.json", True)


remote_ip = remoteIP()
if updateNeeded(remote_ip):
    try:
        zoneFile = open('zones.json', 'r')
        zoneFilejson = json.load(zoneFile)
        # Get the zone list, Iterate through the zones updating them, close the file
        for key in zoneFilejson['zones']:
            # Set headers to be used with cloudflare API
            print("zone = ", key['zone'])
            headers = {
                'Content-Type': 'application/json',
                'X-Auth-Key': key['global_api_key'],
                'X-Auth-Email': key['cloudflare_email']
            }
            zone_id = zoneData(headers, key['zone'])  # Get Zone ID
            record_id = recordData(
                headers, zone_id, key['record'])  # Get record ID
            if updateRecord(headers, zone_id, record_id, key['record'], remote_ip, key['proxied_state']):
                print("DNS for ", key['zone'], " updated to ", remote_ip)
            else:
                print('DNS Update Failed')
        zoneFile.close()
    except FileNotFoundError:
        raise_ex("zones.json was not found", True)
    except PermissionError:
        raise_ex("Dont have permissions to open zones.json", True)
    except KeyError:
        raise_ex("Unable to find required keys in zones.json", True)
    except json.decoder.JSONDecodeError:
        raise_ex("zones.json does not contain proper json", True)
else:
    print('no update needed')
