# dbus-ha-evcharger
Integrate your EVCharger from HomeAssistant into [Victron Energy Venus OS](https://github.com/victronenergy/venus)

## Purpose
With the scripts in this repo it should be possible to add the EVCharger to VenusOS. 

## Origin
This repo is based on similar projects for shelly and home wizard integration

## Install & Configuration
### Get the code
Just grap a copy of the main branche and copy them to `/data/dbus-ha-evcharger`.
After that call the install.sh script.

The following script should do everything for you:
```
wget https://github.com/ajvdw/dbus-ha-evcharger/archive/refs/heads/main.zip
unzip main.zip "dbus-ha-evcharger-main/*" -d /data
mv /data/dbus-ha-evcharger-main /data/dbus-ha-evcharger
chmod a+x /data/dbus-ha-evcharger/install.sh
/data/dbus-ha-evcharger/install.sh
rm main.zip
```
⚠️ Check configuration after that - because service is already installed an running and with wrong connection data (host, username, pwd) you will spam the log-file


### Add a template sensor
Copy the following to configuration.yaml in HomeAssistant
```
template:
  - sensor:
      - name: "evcharger_json"
        unique_id: "evcharger_01_json"
        unit_of_measurement: "kWh"
        state_class: measurement
        state: "{{ states('sensor.evcharger_daily')|float }}"
        attributes:
          power: "{{ states('sensor.evcharger_power') }}"
          energy: "{{ states('sensor.evcharger_total_energy')}}"
          l1_v: "{{ states('sensor.evcharger_phase_a_voltage') }}"
          l2_v: "{{ states('sensor.evcharger_phase_b_voltage') }}"
          l3_v: "{{ states('sensor.evcharger_phase_c_voltage') }}"
          l1_i: "{{ states('sensor.evcharger_phase_a_current') }}"
          l2_i: "{{ states('sensor.evcharger_phase_b_current') }}"
          l3_i: "{{ states('sensor.evcharger_phase_c_current') }}" 
          unique_id: "000002"
```

### Change config.ini
Within the project there is a file `/data/dbus-ha-evcharger/config.ini` - just change the values - most important is the host

| Section  | Config vlaue | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | SignOfLifeLog  | Time in minutes how often a status is added to the log-file `current.log` with log-level INFO |
| DEFAULT  | CustomName  | Name of your device - usefull if you want to run multiple versions of the script |
| DEFAULT  | DeviceInstance  | DeviceInstanceNumber e.g. 40 |
| DEFAULT  | LogLevel  | Define the level of logging - lookup: https://docs.python.org/3/library/logging.html#levels |
| DEFAULT  | Host | IP or hostname of the homeassistant api |
| DEFAULT  | Token | Long lived token from homeassistant/profile/security |

python /data/dbus-ha-evcharger/dbus-ha-evcharger.py


### Debugging
You can check the status of the service with svstat:

svstat /service/dbus-ha-evcharger

### Also useful:

tail -f /data/dbus-ha-evcharger/current.log 

### Stop the script
svc -d /service/dbus-ha-evcharger

### Start the script
svc -u /service/dbus-ha-evcharger

### Restart the script
If you want to restart the script, for example after changing it, just run the following command:

sh /data/dbus-ha-evcharger/restart.sh

## Used documentation
- https://github.com/victronenergy/venus/wiki/dbus#grid   DBus paths for Victron namespace GRID
- https://github.com/victronenergy/venus/wiki/dbus#evcharger  DBus paths for Victron namespace EVCHARGER
- https://github.com/victronenergy/venus/wiki/dbus-api   DBus API from Victron
- https://www.victronenergy.com/live/ccgx:root_access   How to get root access on GX device/Venus OS
