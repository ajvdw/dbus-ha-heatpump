# dbus-ha-heatpump
Integrate your heatpump from HomeAssistant into [Victron Energy Venus OS](https://github.com/victronenergy/venus)

## Purpose
With the scripts in this repo it should be possible to add the heatpump to VenusOS. 

## Origin
This repo is based on similar projects for shelly and home wizard integration

## Install & Configuration
### Get the code
Just grap a copy of the main branche and copy them to `/data/dbus-ha-heatpump`.
After that call the install.sh script.

The following script should do everything for you:
```
wget https://github.com/ajvdw/dbus-ha-heatpump/archive/refs/heads/main.zip
unzip main.zip "dbus-ha-heatpump-main/*" -d /data
mv /data/dbus-ha-heatpump-main /data/dbus-ha-heatpump
chmod a+x /data/dbus-ha-heatpump/install.sh
/data/dbus-ha-heatpump/install.sh
rm main.zip
```
⚠️ Check configuration after that - because service is already installed an running and with wrong connection data (host, username, pwd) you will spam the log-file


### Add a template sensor
Copy the following to configuration.yaml in HomeAssistant
```
template:
  - sensor:
       - name: "heatpump_json"
        unique_id: "heatpump_json"
        unit_of_measurement: "kWh"
        state_class: measurement
        state: "{{ states('sensor.heatpumpdaily')|float }}"
        attributes:
          state: "{{ states('switch.manualboiler') }}"
          power: "{{ (((states('sensor.eastron_sdm_total_power')) | float) * 1000)|round(1) }}"
          energy: "{{ ((states('sensor.eastron_sdm_import_active_energy')) | float) |round(1) }"
          current_temp: "{{ states('sensor.ebusd_ctlv2_hwcstoragetemp_tempv')|round(1)}}"
          target_temp: "{{ states('number.ebusd_ctlv2_hwctempdesired_tempv') }}"
          unique_id: "000003"          

```

### Change config.ini
Within the project there is a file `/data/dbus-ha-heatpump/config.ini` - just change the values - most important is the host

| Section  | Config vlaue | Explanation |
| ------------- | ------------- | ------------- |
| DEFAULT  | SignOfLifeLog  | Time in minutes how often a status is added to the log-file `current.log` with log-level INFO |
| DEFAULT  | CustomName  | Name of your device - usefull if you want to run multiple versions of the script |
| DEFAULT  | DeviceInstance  | DeviceInstanceNumber e.g. 40 |
| DEFAULT  | Position	0: AC Out, 1: AC In (default: 0) |
| DEFAULT  | LogLevel  | Define the level of logging - lookup: https://docs.python.org/3/library/logging.html#levels |
| DEFAULT  | Host | IP or hostname of the homeassistant api |
| DEFAULT  | Token | Long lived token from homeassistant/profile/security |

python /data/dbus-ha-heatpump/dbus-ha-heatpump.py


### Debugging
You can check the status of the service with svstat:

svstat /service/dbus-ha-heatpump

### Also useful:

tail -f /data/dbus-ha-heatpump/current.log 

### Stop the script
svc -d /service/dbus-ha-heatpump

### Start the script
svc -u /service/dbus-ha-heatpump

### Restart the script
If you want to restart the script, for example after changing it, just run the following command:

sh /data/dbus-ha-heatpump/restart.sh

## Used documentation
- https://github.com/victronenergy/venus/wiki/dbus#grid   DBus paths for Victron namespace GRID
- https://github.com/victronenergy/venus/wiki/dbus#heatpump  DBus paths for Victron namespace heatpump
- https://github.com/victronenergy/venus/wiki/dbus-api   DBus API from Victron
- https://www.victronenergy.com/live/ccgx:root_access   How to get root access on GX device/Venus OS
