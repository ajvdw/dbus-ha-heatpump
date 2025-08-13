#!/usr/bin/env python

# import normal packages
import platform 
import logging
import logging.handlers
import os
import sys
if sys.version_info.major == 2:
    import gobject
else:
    from gi.repository import GLib as gobject
import time
import requests # for http GET
import configparser # for config/ini file

# our own packages from victron
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python'))
from vedbus import VeDbusService

class DbusHAHeatpumpService:
    def __init__(self, servicename, paths, productname='Heatpump', connection='HA Heatpump HTTP JSON Service'):
        config = self._getConfig()
        deviceinstance = int(config['DEFAULT']['DeviceInstance'])
        customname = config['DEFAULT']['CustomName']
        position = int(config['DEFAULT']['Position'])

        productid = 45058 #0xFFFF 

        self._dbusservice = VeDbusService("{}.http_{:02d}".format(servicename, deviceinstance))
        self._paths = paths

        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unknown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', productid)
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/CustomName', customname)
        self._dbusservice.add_path('/Latency', None)
        self._dbusservice.add_path('/FirmwareVersion', 0.2)
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)
        self._dbusservice.add_path('/Role', 'heatpump')
        self._dbusservice.add_path('/Position', position ) 
        self._dbusservice.add_path('/Serial', self._getSerial())
        self._dbusservice.add_path('/UpdateIndex', 0)


        # add path values to dbus
        for path, settings in self._paths.items():
          self._dbusservice.add_path(
            path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)

        # add _update function 'timer'
        gobject.timeout_add(5000 , self._update) # pause 500ms before the next request

        # add _signOfLife 'timer' to get feedback in log every 5minutes
        gobject.timeout_add(self._getSignOfLifeInterval()*60*1000, self._signOfLife)

    def _getSerial(self):
        ev_data = self._getData()  

        if not ev_data['unique_id']:
            raise ValueError("Response does not contain 'unique_id' attribute")

        serial = ev_data['unique_id']
        return serial

    def _getConfig(self):
        config = configparser.ConfigParser()
        config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
        return config;


    def _getSignOfLifeInterval(self):
        config = self._getConfig()
        value = config['DEFAULT']['SignOfLifeLog']

        if not value: 
            value = 0

        return int(value)


    def _getData(self):
        config = self._getConfig()
        host = config['DEFAULT']['Host']
        token = config['DEFAULT']['Token']
        headers = { 'Authorization': 'Bearer '+token,
                    'Content-Type': 'application/json' }
        URL = "http://%s/api/states/sensor.heatpump_json" % (host)

        resp_data = requests.get(url = URL, headers=headers, timeout=5)

        # check for response
        if not resp_data:
            raise ConnectionError("No response from endpoint - %s" % (URL))

        datajson = resp_data.json()                     

        # check for Json
        if not datajson:
            raise ValueError("Converting response to JSON failed")

        heatpump_data = datajson["attributes"]

        return heatpump_data


    def _signOfLife(self):
        logging.info("--- Start: sign of life ---")
        logging.info("Last _update() call: %s" % (self._lastUpdate))
        logging.info("--- End: sign of life ---")
        return True

    def _update(self):   
        try:
            now = int( time.time() )
            #get data from Heatpump

            hp_data = self._getData()
            config = self._getConfig()

            #send data to DBus for 3phase system
            self._dbusservice['/Ac/Power'] = hp_data['power']
            self._dbusservice['/Ac/Energy/Forward'] = hp_data['energy']
            self._dbusservice['/Temperature'] = hp_data['current_temp']
            self._dbusservice['/TargetTemperature'] = hp_data['target_temp']
            
            if( hp_data['state'] == 'on' ): 
                self._dbusservice['/State'] = 3
            else:
                self._dbusservice['/State'] = 0

            # increment UpdateIndex - to show that new data is available an wrap
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1 ) % 256
            #update lastupdate vars
            self._lastUpdate = time.time()

            #logging
            logging.debug("Heatpump Power (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            logging.debug("Heatpump Energy (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            logging.debug("---");
        except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError) as e:
            logging.critical('Error getting data from ESPHome - check network or ESPhome device status. Setting power values to 0. Details: %s', e, exc_info=e)       
            self._dbusservice['/Ac/Power'] = 0
            self._dbusservice['/Ac/Energy/Forward'] = 0
            self._dbusservice['/Temperature'] = 0
            self._dbusservice['/TargetTemperature'] = 0
            self._dbusservice['/State'] = 0  # 0=Off;1=Error;2=Startup;3=Heating;4=Cooling
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1 ) % 256        
        except Exception as e:
            logging.critical('Error at %s', '_update', exc_info=e)

        # return true, otherwise add_timeout will be removed from GObject - see docs http://library.isr.ist.utl.pt/docs/pygtk2reference/gobject-functions.html#function-gobject--timeout-add
        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
        return True # accept the change

def getLogLevel():
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    logLevelString = config['DEFAULT']['LogLevel']

    if logLevelString:
        level = logging.getLevelName(logLevelString)
    else:
        level = logging.INFO

    return level


def main():
    #configure logging
    logging.basicConfig(format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=getLogLevel(),
        handlers=[
            logging.FileHandler("%s/current.log" % (os.path.dirname(os.path.realpath(__file__)))),
            logging.StreamHandler()
        ])

    try:
        logging.info("Start");

        from dbus.mainloop.glib import DBusGMainLoop
        # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
        DBusGMainLoop(set_as_default=True)

        #formatting 
        _kwh = lambda p, v: (str(round(v, 2)) + ' kWh')
        _a = lambda p, v: (str(round(v, 1)) + ' A')
        _w = lambda p, v: (str(round(v, 1)) + ' W')
        _v = lambda p, v: (str(round(v, 1)) + ' V')  
        _t = lambda p, v: (str(round(v, 1)) + '°C')
        _n = lambda p, v: (str("%i" % v ) )

        #start our main-service

        evac_output = DbusHAHeatpumpService(
            servicename='com.victronenergy.heatpump.ha',
            paths={
                '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh}, # energy bought from the grid
                '/Ac/Power': {'initial': 0, 'textformat': _w}, 
                '/State': {'initial': 0, "textformat": _n},           
                "/Temperature": {'initial': 0, "textformat": _t},
                "/TargetTemperature": {'initial': 0, "textformat": _t},
                })
        logging.info('Connected to dbus, and switching over to gobject.MainLoop() (= event based)')
        mainloop = gobject.MainLoop()
        mainloop.run()            
    except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logging.critical('Error in main type %s', str(e))
    except Exception as e:
        logging.critical('Error at %s', 'main', exc_info=e)

if __name__ == "__main__":
    main()