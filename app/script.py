#!/usr/bin/env python3
#
# This file is licensed under the terms of the GPL, Version 3
#
# Copyright 2016 Dario Carluccio <check_owserver.at.carluccio.de>
#           2018 Tamas Kinsztler <github.com/humpedli>

__author__ = "Dario Carluccio"
__copyright__ = "Copyright (C) Dario Carluccio and Tamas Kinsztler"
__license__ = "GPLv3"
__version__ = "1.1"

import os
import logging
import signal
import socket
import time
import sys
import paho.mqtt.client as mqtt
import pyownet.protocol as ow
import argparse
import configparser
import setproctitle
import json
import re
from datetime import datetime, timedelta

parser = argparse.ArgumentParser( formatter_class=argparse.RawDescriptionHelpFormatter,
description='''reads temperature sensors from onewire-server and
publishes the temperaturs to a mqtt-broker''')
parser.add_argument('config_file', metavar="<config_file>", help="file with configuration")
# parser.add_argument("-v", "--verbose", help="increase log verbosity", action="store_true")
args = parser.parse_args()

# read and parse config file
config = configparser.ConfigParser()
config.read(args.config_file)
# [mqtt]
MQTT_HOST = config.get("mqtt", "host")
MQTT_PORT = config.getint("mqtt", "port")
STATUSTOPIC = config.get("mqtt", "statustopic")
POLLINTERVAL = config.getint("mqtt", "pollinterval")
# [Onewire]
OW_HOST = config.get("onewire", "host")
OW_PORT = config.get("onewire", "port")
# [log]
LOGFILE = config.get("log", "logfile")
VERBOSE = config.get("log", "verbose")
# [sensors]
section_name = "sensors"
SENSORS = {}
for name, value in config.items(section_name):
  SENSORS[name] = value

# compose MQTT client ID from appname and PID
APPNAME = "onewire-to-mqtt"
setproctitle.setproctitle(APPNAME)
MQTT_CLIENT_ID = APPNAME + "[_%d]" % os.getpid()
MQTTC = mqtt.Client(MQTT_CLIENT_ID)

# init logging
LOGFORMAT = '%(asctime)-15s %(message)s'
if VERBOSE:
  logging.basicConfig(filename=LOGFILE, format=LOGFORMAT, level=logging.DEBUG)
else:
  logging.basicConfig(filename=LOGFILE, format=LOGFORMAT, level=logging.INFO)

logging.info("Starting " + APPNAME)
if VERBOSE:
  logging.info("INFO MODE")
else:
  logging.debug("DEBUG MODE")

### MQTT Callback handler ###

# MQTT: message is published
def on_mqtt_publish(mosq, obj, mid):
  logging.debug("MID " + str(mid) + " published.")
  logging.debug(json.dumps(obj))

# MQTT: connection to broker
# client has received a CONNACK message from broker
# return code:
#   0: Success                                                      -> Set LASTWILL
#   1: Refused - unacceptable protocol version->EXIT
#   2: Refused - identifier rejected                                -> EXIT
#   3: Refused - server unavailable                                 -> RETRY
#   4: Refused - bad user name or password (MQTT v3.1 broker only)  -> EXIT
#   5: Refused - not authorised (MQTT v3.1 broker only)             -> EXIT
def on_mqtt_connect(self, mosq, obj, return_code):
  logging.debug("on_connect return_code: " + str(return_code))
  if return_code == 0:
    logging.info("Connected to %s:%s", MQTT_HOST, MQTT_PORT)
    # set Lastwill
    self.publish(STATUSTOPIC, "1 - connected", retain=True)
    # process_connection()
  elif return_code == 1:
    logging.info("Connection refused - unacceptable protocol version")
    cleanup()
  elif return_code == 2:
    logging.info("Connection refused - identifier rejected")
    cleanup()
  elif return_code == 3:
    logging.info("Connection refused - server unavailable")
    logging.info("Retrying in 10 seconds")
    time.sleep(10)
  elif return_code == 4:
    logging.info("Connection refused - bad user name or password")
    cleanup()
  elif return_code == 5:
    logging.info("Connection refused - not authorised")
    cleanup()
  else:
    logging.warning("Something went wrong. RC:" + str(return_code))
    cleanup()

# MQTT: disconnected from broker
def on_mqtt_disconnect(mosq, obj, return_code):
  if return_code == 0:
    logging.info("Clean disconnection")
  else:
    logging.info("Unexpected disconnection. Reconnecting in 5 seconds")
    logging.debug("return_code: %s", return_code)
    time.sleep(5)

# MQTT: debug log
def on_mqtt_log(mosq, obj, level, string):
  if VERBOSE:
    logging.debug(string)

### END of MQTT Callback handler ###


# clean disconnect on SIGTERM or SIGINT.
def cleanup(signum, frame):
  logging.info("Disconnecting from broker")
  # Publish a retained message to state that this client is offline
  MQTTC.publish(STATUSTOPIC, "0 - DISCONNECT", retain=True)
  MQTTC.disconnect()
  MQTTC.loop_stop()
  logging.info("Exiting on signal %d", signum)
  sys.exit(signum)


# init connection to MQTT broker
def mqtt_connect():
  logging.debug("Connecting to %s:%s", MQTT_HOST, MQTT_PORT)
  # Set the last will before connecting
  MQTTC.will_set(STATUSTOPIC, "0 - LASTWILL", qos=0, retain=True)
  result = MQTTC.connect(MQTT_HOST, MQTT_PORT, 60)
  if result != 0:
    logging.info("Connection failed with error code %s. Retrying", result)
    time.sleep(10)
    mqtt_connect()
  # Define callbacks
  MQTTC.on_connect = on_mqtt_connect
  MQTTC.on_disconnect = on_mqtt_disconnect
  MQTTC.on_publish = on_mqtt_publish
  MQTTC.on_log = on_mqtt_log
  MQTTC.loop_start()

# register all sensors for autodiscovery in hass
def register_sensors():
  for owid, nice_name in SENSORS.items():
    try:
      object_id = re.sub("[^A-Za-z0-9_-]","-", owid) # No silly chars allowed as object_id
      hass_reg = {
        'name': nice_name,
        'device_class': 'temperature',
        'temperature_unit': '°C',
        'state_topic': 'homeassistant/sensor/{}/state'.format(object_id)
      }
      logging.debug('Publishing {} to homeassistant/sensor/{}/config'.format(nice_name, object_id))
      topic = "homeassistant/sensor/{}/config".format(object_id)
      MQTTC.publish(topic, json.dumps(hass_reg))
    except Exception as e:
      logging.info('EXCEPTION: hass-config {}'.format(e))


# Main Loop
def main_loop():
  logging.debug(("onewire server : %s") % (OW_HOST))
  logging.debug(("  port         : %s") % (str(OW_PORT)))
  logging.debug(("MQTT broker    : %s") % (MQTT_HOST))
  logging.debug(("  port         : %s") % (str(MQTT_PORT)))
  logging.debug(("pollinterval   : %s") % (str(POLLINTERVAL)))
  logging.debug(("statustopic    : %s") % (str(STATUSTOPIC)))
  logging.debug(("sensors        : %s") % (len(SENSORS)))
  for owid, nice_name in SENSORS.items():
    logging.debug(("  %s : %s") % (owid, nice_name))

  # Connect to the broker and enter the main loop
  mqtt_connect()

  # Connect to ow server
  owproxy = ow.proxy(OW_HOST, OW_PORT)

  # register sensors in HASS
  register_sensors()

  n = 0
  while True:
    if n > 100:
      # re-register sensors every 100 loops if the HASS-sever has been restarted.
      register_sensors()
      n = 0

    n += 1

    # simultaneous temperature conversion
    owproxy.write("/simultaneous/temperature",b"1")

    # iterate over all sensors
    for owid, nice_name in SENSORS.items():
      logging.debug(("Querying %s : %s") % (owid, nice_name))
      try:
        owtemp = owproxy.read(("/%s/temperature") % (owid))
        object_id = re.sub("[^A-Za-z0-9_-]","-", owid)
        logging.debug("publishing homeassistant/sensor/{}/state -> '{:.1f}'".format(object_id, float(owtemp.strip())))
        topic = "homeassistant/sensor/{}/state".format(object_id)
        MQTTC.publish(topic, "{:.1f}".format(float(owtemp.strip())))
      except ow.Error:
        logging.info("Threw an unknown sensor exception for device %s - %s. Continuing", owid, nice_name)
        continue

      time.sleep(float(POLLINTERVAL) / len(SENSORS))

# Use the signal module to handle signals
signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

# start main loop
try:
  main_loop()
except KeyboardInterrupt:
  logging.info("Interrupted by keypress")
  sys.exit(0)