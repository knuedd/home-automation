# Home Automation scripts for Home Assistant

This is my public version of the home automation scripts to work together with https://www.home-assistant.io/.

## hass_agent_sensor_bme280.py

Python3 agent that regularly collects temperature, pressure, and humidity measuremnts fomr a BME280 (https://www.reichelt.de/entwicklerboards-temperatur-und-drucksensor-bmp280-debo-bmp280-p266034.html?&nbc=1) sensor and sends it out. It will send it to:
* the Home Assistant instance via MQTT device discovery and updates
* optionally to an InfluxDB via the python3 package `influxdb`

## hass_agent_sensor_dummy.py

Does the same thing but with dummy sensors so that you don't need the sensor to play with this.

