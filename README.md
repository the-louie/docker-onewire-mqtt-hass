# OneWire MQTT to Home-Assistant with Docker

Publish onewire temperature sensor values with MQTT

Original author is [dcbo](https://github.com/dcbo) and his repository is here: https://github.com/dcbo/onewire-to-mqtt

Original docker adaptation by [humpedli](https://github.com/humpedli) and the repository can be found here: https://github.com/humpedli/docker-onewire-mqtt

**This is mostly minor adaptations to fit my Docker setup and enable automatic registering into Home-Assistant**

This script is intended to run as a service, it connects to [owserver](http://owfs.org/index.php?page=owserver) (from [owfs](http://owfs.org) and reads the temperature values from **DS18x20** onewire sensors.
The temperatures which have been aquired using owserver will be published using a mqtt-broker.

A running [owserver](http://owfs.org/index.php?page=owserver) and a mqtt-broker (e.g: [mosquitto](https://mosquitto.org)) are required to use this deamon.

## Run with docker-compose
Don't forget to create configuration file first (there is a sample in the repository), then attach the file as a volume like examples below.

```
version: '3'
services:
  onewire-mqtt:
    container_name: "onewire-mqtt"
    restart: always
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      - "./app:/app"
      - "/etc/localtime:/etc/localtime:ro"
      - "./log:/var/log"
    network_mode: host
```


## Configuration file
a self explaining sample configuration file is included

```
# sample configuration

# MQTT broker  related config
[mqtt]
host = 127.0.0.1
port = 1883

# polling interval for sensors
pollinterval = 30

# topic for status messages
statustopic = onewire-to-mqtt/status

# Onewire related config
[onewire]
host= localhost
port = 4304

[log]
#verbose = false
verbose = true
logfile = /var/log/onewire-to-mqtt.log

# list of sensors to be polled and names to be used in HASS
[sensors]
28.100000000000 = Hallway
10.200000000000 = Bedroom
28.300000000000 = Outside
10.400000000000 = Kitchen
```