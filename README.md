# Home Automation scripts for Home Assistant

This is my public version of the home automation scripts to work together with https://www.home-assistant.io/.

## hass_agent_sensor_bme280.py

Python3 agent that regularly collects temperature, pressure, and humidity measuremnts from a BME280 (https://www.reichelt.de/entwicklerboards-temperatur-feuchtigkeits-und-drucksensor--debo-bme280-p253982.html?&nbc=1) sensor and sends it out. It will send it to:
* the Home Assistant instance via MQTT device discovery and updates
* optionally to an InfluxDB via the python3 package `influxdb`

## hass_agent_sensor_dummy.py

Does the same thing but with dummy sensors so that you don't need the sensor to play with this.

## Example dashboard

![Example dashboard screenshot](https://raw.githubusercontent.com/knuedd/home-automation/main/images/example_dashboard_screenshot.png)

This is how the result may look like. The three gauge charts in the top present one BME280 sensor connected to a remote raspi and transmitted via the MQTT agent from this repo. The three sets of line charts below are from the one sensor shown above and three more BME280 sensors connected to three more raspis.

To the left there is a weather forecast and in the top left there is a remote garage door control and status panel. The home assistant MQTT agent for this one will follow here.


## PS

BMP280 (https://www.reichelt.de/entwicklerboards-temperatur-und-drucksensor-bmp280-debo-bmp280-p266034.html?&nbc=1) should also work. It is much cheaper but has no humidity sensor.
