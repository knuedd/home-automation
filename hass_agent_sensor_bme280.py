#!/usr/bin/python3

## install packages: 
## sudo apt install python3-influxdb python3-yaml
## pip3 install paho-mqtt

import sys
import smbus
import time
import math

from ctypes import c_short
from ctypes import c_byte
from ctypes import c_ubyte

import influxdb
import socket
import datetime

import paho.mqtt.client as mqtt
import yaml


HOSTNAME= socket.gethostname()

conf={}

mqtt_client= None
mqtt_state_topic= 'undefined'

influx= None

# smbus for BME280 sensor

DEVICE = 0x76 # Default device I2C address
bus= smbus.SMBus(1)


def getShort(data, index):
  # return two bytes from data as a signed 16-bit value
  return c_short((data[index+1] << 8) + data[index]).value

def getUShort(data, index):
  # return two bytes from data as an unsigned 16-bit value
  return (data[index+1] << 8) + data[index]

def getChar(data,index):
  # return one byte from data as a signed char
  result = data[index]
  if result > 127:
    result -= 256
  return result

def getUChar(data,index):
  # return one byte from data as an unsigned char
  result =  data[index] & 0xFF
  return result

def readBME280ID(addr=DEVICE):
  # Chip ID Register Address
  REG_ID     = 0xD0
  (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
  return (chip_id, chip_version)

def readBME280All(addr=DEVICE):

  # Register Addresses
  REG_DATA = 0xF7
  REG_CONTROL = 0xF4
  REG_CONFIG  = 0xF5

  REG_CONTROL_HUM = 0xF2
  REG_HUM_MSB = 0xFD
  REG_HUM_LSB = 0xFE

  # Oversample setting - page 27
  OVERSAMPLE_TEMP = 2
  OVERSAMPLE_PRES = 2
  MODE = 1

  # Oversample setting for humidity register - page 26
  OVERSAMPLE_HUM = 2
  bus.write_byte_data(addr, REG_CONTROL_HUM, OVERSAMPLE_HUM)

  control = OVERSAMPLE_TEMP<<5 | OVERSAMPLE_PRES<<2 | MODE
  bus.write_byte_data(addr, REG_CONTROL, control)

  # Read blocks of calibration data from EEPROM
  # See Page 22 data sheet
  cal1 = bus.read_i2c_block_data(addr, 0x88, 24)
  cal2 = bus.read_i2c_block_data(addr, 0xA1, 1)
  cal3 = bus.read_i2c_block_data(addr, 0xE1, 7)

  # Convert byte data to word values
  dig_T1 = getUShort(cal1, 0)
  dig_T2 = getShort(cal1, 2)
  dig_T3 = getShort(cal1, 4)

  dig_P1 = getUShort(cal1, 6)
  dig_P2 = getShort(cal1, 8)
  dig_P3 = getShort(cal1, 10)
  dig_P4 = getShort(cal1, 12)
  dig_P5 = getShort(cal1, 14)
  dig_P6 = getShort(cal1, 16)
  dig_P7 = getShort(cal1, 18)
  dig_P8 = getShort(cal1, 20)
  dig_P9 = getShort(cal1, 22)

  dig_H1 = getUChar(cal2, 0)
  dig_H2 = getShort(cal3, 0)
  dig_H3 = getUChar(cal3, 2)

  dig_H4 = getChar(cal3, 3)
  dig_H4 = (dig_H4 << 24) >> 20
  dig_H4 = dig_H4 | (getChar(cal3, 4) & 0x0F)

  dig_H5 = getChar(cal3, 5)
  dig_H5 = (dig_H5 << 24) >> 20
  dig_H5 = dig_H5 | (getUChar(cal3, 4) >> 4 & 0x0F)

  dig_H6 = getChar(cal3, 6)

  # Wait in ms (Datasheet Appendix B: Measurement time and current calculation)
  wait_time = 1.25 + (2.3 * OVERSAMPLE_TEMP) + ((2.3 * OVERSAMPLE_PRES) + 0.575) + ((2.3 * OVERSAMPLE_HUM)+0.575)
  time.sleep(wait_time/1000)  # Wait the required time  

  # Read temperature/pressure/humidity
  data = bus.read_i2c_block_data(addr, REG_DATA, 8)
  pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
  temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
  hum_raw = (data[6] << 8) | data[7]

  #Refine temperature
  var1 = ((((temp_raw>>3)-(dig_T1<<1)))*(dig_T2)) >> 11
  var2 = (((((temp_raw>>4) - (dig_T1)) * ((temp_raw>>4) - (dig_T1))) >> 12) * (dig_T3)) >> 14
  t_fine = var1+var2
  temperature = float(((t_fine * 5) + 128) >> 8);

  # Refine pressure and adjust for temperature
  var1 = t_fine / 2.0 - 64000.0
  var2 = var1 * var1 * dig_P6 / 32768.0
  var2 = var2 + var1 * dig_P5 * 2.0
  var2 = var2 / 4.0 + dig_P4 * 65536.0
  var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
  var1 = (1.0 + var1 / 32768.0) * dig_P1
  if var1 == 0:
    pressure=0
  else:
    pressure = 1048576.0 - pres_raw
    pressure = ((pressure - var2 / 4096.0) * 6250.0) / var1
    var1 = dig_P9 * pressure * pressure / 2147483648.0
    var2 = pressure * dig_P8 / 32768.0
    pressure = pressure + (var1 + var2 + dig_P7) / 16.0

  # Refine humidity
  humidity = t_fine - 76800.0
  humidity = (hum_raw - (dig_H4 * 64.0 + dig_H5 / 16384.0 * humidity)) * (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * humidity * (1.0 + dig_H3 / 67108864.0 * humidity)))
  humidity = humidity * (1.0 - dig_H1 * humidity / 524288.0)
  if humidity > 100:
    humidity = 100
  elif humidity < 0:
    humidity = 0

  return temperature/100.0,pressure/100.0,humidity*1.0


def do_measurement():

  temperature,pressure,humidity= readBME280All()
  return temperature,pressure,humidity


def parse_config():

  global conf

  with open("mqtt-agent.yaml", 'r') as stream:
    try:
      conf = yaml.load(stream, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
      print(exc)
      print("Unable to parse configuration file mqtt-agent.yaml")
      sys.exit(1)

  if not 'name' in conf:

    # use hostname instead
    conf['name']= HOSTNAME

  if not 'location' in conf:

    # use hostname instead
    conf['location']= HOSTNAME


  if 'mqttServer' in conf:
    print( "Home Assistant MQTT enabled" )

  if 'influxServer' in conf:
    print( "InfluxDB  enabled" )

  print( "conf: ", conf )


def mqtt_announce():

  global mqtt_client, mqtt_state_topic

  print( "mqtt_announce" )

  mqtt_state_topic= 'homeassistant/sensor/bme280_' + HOSTNAME + '/state'

  # temperature
  topic= "homeassistant/sensor/" + conf['name'] + "/temperature/config"
  unique_id= "temperature_" + conf['name']
  payload= '{ "device_class":  "temperature", "name": "Temperature ' + conf['name'] + '", "unique_id": "' + unique_id + '", "state_topic": "' + mqtt_state_topic + '", "unit_of_measurement": "°C", "value_template": "{{ value_json.temperature }}", "expire_after": 370 }'
  print( "send " + topic + " : " + payload )
  mqtt_client.publish( topic, payload )

  # pressure
  topic= "homeassistant/sensor/" + conf['name'] + "/pressure/config"
  unique_id= "pressure_" + conf['name']
  payload= '{ "device_class": "pressure", "name": "Pressure ' + conf['name'] + '", "unique_id": "' + unique_id + '", "state_topic": "' + mqtt_state_topic + '", "unit_of_measurement": "hPa", "value_template": "{{ value_json.pressure }}", "expire_after": 370 }'
  print( "send " + topic + " : " + payload )
  mqtt_client.publish( topic, payload )

  # humidity
  topic= "homeassistant/sensor/" + conf['name'] + "/humidity/config"
  unique_id= "humidity_" + conf['name']
  payload= '{ "device_class": "humidity", "name": "Humidity ' + conf['name'] + '", "unique_id": "' + unique_id + '", "state_topic": "' + mqtt_state_topic + '", "unit_of_measurement": "%", "value_template": "{{ value_json.humidity }}", "expire_after": 370 }'
  print( "send " + topic + " : " + payload )
  mqtt_client.publish( topic, payload )


## callbacks for mqtt

# The callback for when the client receives a CONNACK response from the server.
def mqtt_callback_connect( client, userdata, flags, rc ):
    
  global mqtt_client, mqtt_state_topic
  
  print("Connected with result code "+str(rc))
  sys.stdout.flush()
  
  (result, mid) = client.subscribe( "homeassistant/status" )
  print("Got subscription result for "+"homeassistant/status"+":"+str(result))

  mqtt_announce()


# The callback for when a PUBLISH message is received from the server.
def mqtt_callback_message(client, userdata, msg):

  # ignore retained messages
  if 1 == msg.retain: 
      return

  print("Received command: "+msg.topic+" "+str(msg.payload) )
  sys.stdout.flush()

  if "homeassistant/status" == msg.topic:
    print( "home assistant status message:", msg.topic )
    # report ourselves as available to home assistant
    
    if b'online' == msg.payload:

      # re-report ourselves available to home assistant and report current state
      mqtt_announce()


def mqtt_callback_disconnect(client, userdata, rc):

  print( "Disconnect from MQTT" )

  if rc != 0:
      print( "Unexpected disconnection." )


def init_mqtt():

  global conf, mqtt_client

  mqtt_client = mqtt.Client()
  mqtt_client.on_connect = mqtt_callback_connect
  mqtt_client.on_message = mqtt_callback_message
  mqtt_client.on_disconnect = mqtt_callback_disconnect

  print("Starting mqtt-agent.py")
  if conf['mqttUser'] and conf['mqttPass']:
      mqtt_client.username_pw_set( username=conf['mqttUser'], password=conf['mqttPass'] )

  mqtt_client.connect( conf['mqttServer'], conf['mqttPort'], 60 )
  print("Listen to MQTT messages...")
  sys.stdout.flush()

  print( 'initialized mqtt' )

  mqtt_client.loop_start()


def finalize_mqtt():

  global mqtt_client

  print( "stopping MQTT" )


  mqtt_client.disconnect()

  mqtt_client.loop_stop()

  print( "MQTT stopped" )


def send_mqtt( temperature, pressure, humidity ):

  global conf, mqtt_client, mqtt_state_topic

  payload= '{ "temperature": %f, "pressure": %f, "humidity": %f }' % (temperature,pressure,humidity)
  #print( "mqtt publish ", mqtt_state_topic, " : ", payload )
  mqtt_client.publish( mqtt_state_topic, payload )


def init_influx():

  global influx

  # init Influx connection
  influx = influxdb.InfluxDBClient( host= conf['influxServer'], port= conf['influxPort'], username= conf['influxUser'], password= conf['influxPass'],  database=conf['influxDB'] )

  #influx.create_database('temperature')
  list= influx.get_list_database()
  print( "list of influx databases")
  print( list )


def send_influx( temperature, pressure, humidity ):

  global influx

  # send to influx db
  jsonpoint = [
    {
      "measurement": "BME280 Sensor",
      "tags": {
        "source": conf['name'],
        "hostname": HOSTNAME,
        "location": conf['location'],
      },
      "time": "%s" %(datetime.datetime.utcnow()),
      "fields": {
        "temperature": temperature,
        "pressure":    pressure,
        "humidity":    humidity
      }
    },
  ]

  #print( "   json ", jsonpoint )
  influx.write_points( jsonpoint )


def main():

  global conf, mqtt_client, mqtt_state_topic

  parse_config()

  if 'mqttServer' in conf:
    init_mqtt()

  if 'influxServer' in conf:
    init_influx()

  (chip_id, chip_version) = readBME280ID()
  print( "Chip ID     :", chip_id )
  print( "Version     :", chip_version )

  try:
  
    while(True):

      temperature, pressure, humidity = do_measurement()
      print( "Temperature : ", temperature, "C ", "Pressure : ", pressure, "hPa ", "Humidity : ", humidity, "%" )

      if 'mqttServer' in conf:
        send_mqtt( temperature, pressure, humidity )

      if 'influxServer' in conf:
        send_influx( temperature, pressure, humidity )

      time.sleep(120)

  except KeyboardInterrupt:
    print( "Keyboard interrupt" )
  except:
    print( "unexpected error" )

  if 'mqttServer' in conf:
    finalize_mqtt()


if __name__=="__main__":
    main()

