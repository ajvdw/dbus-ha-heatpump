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

STOP_CHARGING_COUNTER_AFTER = 300  # seconds

class DbusHAHeatpumpService:
    def __init__(self, servicename, paths, productname='Heatpump', connection='HA Heatpump HTTP JSON Service'):
        config = self._getConfig()
        deviceinstance = int(config['DEFAULT']['DeviceInstance'])
        customname = config['DEFAULT']['CustomName']

        productid = 0xFFFF #45069

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
        self._dbusservice.add_path('/Role', 'heat pump')
        self._dbusservice.add_path('/Position', 1) 
        self._dbusservice.add_path('/Serial', self._getSerial())
        self._dbusservice.add_path('/UpdateIndex', 0)

        
        # add path values to dbus
        for path, settings in self._paths.items():
          self._dbusservice.add_path(
            path, settings['initial'], gettextcallback=settings['textformat'], writeable=True, onchangecallback=self._handlechangedvalue)
    
        # last update
        self._lastUpdate = 0
        self._charging_time = {"start": None, "calculate": False, "stopped_since": 0}
        self._energy_start = 0
    
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
        logging.info("Last '/Ac/Power': %s" % (self._dbusservice['/Ac/Power']))
        logging.info("--- End: sign of life ---")
        return True
 
    def _update(self):   
        try:
            now = int( time.time() )
            #get data from Heatpump

            hp_data = self._getData()
            config = self._getConfig()


#/ProductId
#/State. (0,1)
#/Ac/Power
#/Ac/Energy/Forward
#/Temperature
#/TargetTemperature

            #send data to DBus for 3phase system
            self._dbusservice['/Ac/Power'] = ev_data['power']
            self._dbusservice['/Current'] = ev_data['l1_i']
            self._dbusservice['/Ac/L1/Power'] = ev_data['l1_v']*ev_data['l1_i']
            self._dbusservice['/Ac/L2/Power'] = ev_data['l2_v']*ev_data['l2_i']
            self._dbusservice['/Ac/L3/Power'] = ev_data['l3_v']*ev_data['l3_i']
            self._dbusservice['/Mode'] = 0  # Manual, no control
            self._dbusservice['/MaxCurrent'] = 16
            #self._dbusservice['/Status'] = 1  # 0=Disconnected, 1=Connected, 2=Charging, 3=Charged, #24=Stop Charging


            # set charging time start
            if self._charging_time["start"] is None and ev_data['power'] > 0:
                self._charging_time["start"] = now
                self._energy_start = (ev_data['energy'])
                self._dbusservice['/Status'] = 2 #Charging

            # calculate charging time if charging started
            if self._charging_time["start"] is not None:
                self._dbusservice['/ChargingTime'] = now - self._charging_time["start"]

                if ev_data['power'] == 0 and self._charging_time["stopped_since"] is None:
                    self._charging_time["stopped_since"] = now
                    self._dbusservice['/Status'] = 1 #Connected
                elif ev_data['power'] > 0 and self._charging_time["stopped_since"] is not None:
                    self._charging_time["stopped_since"] = None

                if self._charging_time["stopped_since"] is not None and STOP_CHARGING_COUNTER_AFTER < now - self._charging_time["stopped_since"]:
                    self._charging_time["start"] = None
                    self._charging_time["stopped_since"] = None
                    self._dbusservice['/ChargingTime']= None
            
            if self._energy_start > 0:
                self._dbusservice['/Ac/Energy/Forward'] = (ev_data['energy']) - self._energy_start
            else:
                self._dbusservice['/Ac/Energy/Forward'] = 0
                
            #logging
            logging.debug("Grid Consumption (/Ac/Power): %s" % (self._dbusservice['/Ac/Power']))
            logging.debug("Grid Forward (/Ac/Energy/Forward): %s" % (self._dbusservice['/Ac/Energy/Forward']))
            logging.debug("---");
            
            # increment UpdateIndex - to show that new data is available an wrap
            self._dbusservice['/UpdateIndex'] = (self._dbusservice['/UpdateIndex'] + 1 ) % 256

            #update lastupdate vars
            self._lastUpdate = time.time()
        except (ValueError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, ConnectionError) as e:
            logging.critical('Error getting data from ESPHome - check network or ESPhome device status. Setting power values to 0. Details: %s', e, exc_info=e)       
            self._dbusservice['/Ac/L1/Power'] = 0                                       
            self._dbusservice['/Ac/L2/Power'] = 0                                       
            self._dbusservice['/Ac/L3/Power'] = 0
            self._dbusservice['/Ac/Power'] = 0
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
        _n = lambda p, v: (str("%i" % v ) )
        
        #start our main-service
        
        evac_output = DbusHAEVChargerService(
            servicename='com.victronenergy.evcharger.ha',
            paths={
                '/Ac/Energy/Forward': {'initial': 0, 'textformat': _kwh}, # energy bought from the grid
                '/Ac/Power': {'initial': 0, 'textformat': _w},            
                '/Ac/Current': {'initial': 0, 'textformat': _a},
                '/Ac/L1/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L2/Power': {'initial': 0, 'textformat': _w},
                '/Ac/L3/Power': {'initial': 0, 'textformat': _w},
                "/Current": {'initial': None, "textformat": _a},
                "/MaxCurrent": {'initial': None, "textformat": _a},
                "/SetCurrent": {'initial': None, "textformat": _a},
                "/AutoStart": {'initial': 0, "textformat": _n},
                "/ChargingTime": {'initial': None, "textformat": _n},                
                '/Mode': {'initial': 1, "textformat": _n},
                "/Status": {'initial': 0, "textformat": _n},
                "/StartStop": {'initial': 1, "textformat": _n},
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
