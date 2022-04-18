from urllib3.exceptions import HTTPError as BaseHTTPError
import sys
import re
import json
import requests

'''
cloudflareDDNS
This was created so I could update dns records on cloudflare when my IP address changed
It uses ipify.org api to get your remote IP then updates the specified zone's dns on cloudflare
Requires Python 3.7 or later

Brent Russsell
www.brentrussell.com
'''

config = [ 
            # ['ZONE', 'RECORD', 'GLOBAL API_KEY at https://dash.cloudflare.com/profile', 'EMAIL@DOMAIN.COM' ]
            # ['apple.com', 'maps.apple.com', 'f2f7sl269-FAKE-GLOBAL-KEY-hs34gxo5l2', 'stevejobs@apple.com' ]
            ['domain1.com', 'domain1.com', 'ExAmPlEaPiKeY', 'contactemail@gmail.com', True ], 
            ['domain2.com', 'subdomain.domain2.com', 'ExAmPlEaPiKeY', 'contactemail@gmail.com', False ], 
            ['domain3.com', 'domain3.com', 'ExAmPlEaPiKeY', 'contactemail@gmail.com', True ],
            ['domain4.com', 'example.domain4.com', 'AnOtHeRExAmPlEaPiKeY', 'contactAnotherEmail@gmail.com', True ]
        ] 

if float(str(sys.version_info[0]) + '.' + str(sys.version_info[1])) < 3.6:
    raise_ex("Please upgrade to Python 3.7 or later", True)


def raise_ex(msg, terminate):
    print(msg)
    terminate and sys.exit(1)


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


def remoteIP():
    # https://www.ipify.org/ api to get public ip
    ip_api = 'https://api.ipify.org?format=json'
    ip = getURL(ip_api, 'get')
    if ip.content:
        data = json.loads(ip.content)
        if not data['ip']:
            raise_ex('No IP returned from ' + ip_api, True)
        elif not re.search(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", data['ip']):
            raise_ex('A valid IP was not returned from ' + ip_api, True)
        else:
            return data['ip']
    else:
        raise_ex("No content returned from " + ip_api, True)


def zoneData(headers, zone):
    data = getURL('https://api.cloudflare.com/client/v4/zones?name=' + zone, 'get', headers)
    zone_data = json.loads(data.content)
    if len (zone_data['result']) > 0:
        if not zone_data['result'][0]['id']:
            raise_ex('Zone ' + zone + ' not found', True)
        else:
            return zone_data['result'][0]['id']
    else:
        return False


def recordData(headers, zone_id, record):
    data = getURL('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records?name=' + record, 'get', headers)
    record_data = json.loads(data.content)
    if len (record_data['result']) > 0:
        if not record_data['result'][0]['id']:
            raise_ex('Record ' + record + ' not found', True)
        else:
            return record_data['result'][0]['id']
    else:
        return False


def listToDict(lst):
    op = {lst[i]: lst[i + 1] for i in range(0, len(lst), 2)}
    return op


def updateRecord(headers, zone_id, record, record_id, remote_ip, proxied_state):
    payload = dict(type="A", name=record, content=remote_ip, ttl=1, proxied=proxied_state)
    data = getURL('https://api.cloudflare.com/client/v4/zones/' + zone_id + '/dns_records/' + record_id, 'put', headers, json.dumps(payload))
    update = json.loads(data.content)
    if update['success']:
        return 'success'
    else:
        return update['errors'][0]['message']


# Get the remote IP of thsis machine
remote_ip = remoteIP()
total_updates = 0
total_errors = 0
if len(remote_ip) > 6:
    for i in range(len(config)) : 
        # Set headers to be used with cloudflare
        headers = {
            'Content-Type': 'application/json',
            'X-Auth-Key': config[i][2],
            'X-Auth-Email': config[i][3]
        }
        zone_id = zoneData(headers, config[i][0])  # Get Zone ID
        if i > 0:
            print('\n-----------------------------------------')
        if zone_id:
            record_id = recordData(headers, zone_id, config[i][1])  # Get record ID
            if record_id:
                print('Record: ' + config[i][1])
                results = updateRecord(headers, zone_id, config[i][1], record_id, remote_ip, config[i][4])
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
    print(f'\n----------------RESULTS----------------\n{total_updates} record(s) updated and {total_errors} error(s)')
else:
    print("Could not obtain IP from https://api.ipify.org?format=json")
