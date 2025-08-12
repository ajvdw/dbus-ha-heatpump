#!/usr/bin/env python

# import normal packages
import sys
import os
import sys
import json
import requests # for http GET
import configparser # for config/ini file

def main():
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))

    token = config['DEFAULT']['Token']
    host = config['DEFAULT']['Host']
    URL = 'http://' + host + '/api/states/sensor.heatpump_json'


    headers = { 'Authorization': 'Bearer '+token,
                'Content-Type': 'application/json' }

    resp_data = requests.get(url = URL, headers=headers, timeout=5)

    # check for response
    if not resp_data:
        raise ConnectionError("No response from endpoint - %s" % (URL))

    datajson = resp_data.json()             
    
        # check for Json
    if not datajson:
        raise ValueError("Converting response to JSON failed")

    heatpump_data = datajson["attributes"]

    for key, value in heatpump_data.items():
        print(key, ":", value)
            
if __name__ == "__main__":
    main()
