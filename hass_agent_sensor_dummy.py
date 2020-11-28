#!/usr/bin/python3

## install packages: 
## sudo apt install python3-influxdb python3-yaml
## pip3 install paho-mqtt

import sys
import time
import math

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


def do_measurement():

  ## do fake measurment values

  seconds= time.time() # time in seconds

  # print( "t= ", seconds, 1.0*(seconds % 3600)/3600, 1.0*(seconds % 1800)/1800, 1.0*(seconds % 2400)/2400 )

  temperature= 15.0 + 20.0* math.sin( 2.0*math.pi*(seconds % 3600)/3600 ) # one sine per hour
  pressure= 900.0 + 100.0 * math.sin( 2.0*math.pi*(seconds % 1800)/1800 ) # one sine per half hour
  humidity= 0.8 + .2 * math.sin ( 2.0*math.pi*(seconds % 2400)/2400 ) # 1.5 sine per hour

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

  mqtt_state_topic= 'homeassistant/sensor/dummy_bme280_' + HOSTNAME + '/state'

  # temperature
  topic= "homeassistant/sensor/" + conf['name'] + "/temperature/config"
  unique_id= "temperature_" + conf['name']
  payload= '{ "device_class":  "temperature", "name": "Temperature ' + conf['name'] + '", "unique_id": "' + unique_id + '", "state_topic": "' + mqtt_state_topic + '", "unit_of_measurement": "°C", "value_template": "{{ value_json.temperature }}" }'
  #print( "send " + topic + " : " + payload )
  mqtt_client.publish( topic, payload )

  # pressure
  topic= "homeassistant/sensor/" + conf['name'] + "/pressure/config"
  unique_id= "pressure_" + conf['name']
  payload= '{ "device_class": "pressure", "name": "Pressure ' + conf['name'] + '", "unique_id": "' + unique_id + '", "state_topic": "' + mqtt_state_topic + '", "unit_of_measurement": "hPa", "value_template": "{{ value_json.pressure }}" }'
  #print( "send " + topic + " : " + payload )
  mqtt_client.publish( topic, payload )

  # humidity
  topic= "homeassistant/sensor/" + conf['name'] + "/humidity/config"
  unique_id= "humidity_" + conf['name']
  payload= '{ "device_class": "humidity", "name": "Humidity ' + conf['name'] + '", "unique_id": "' + unique_id + '", "state_topic": "' + mqtt_state_topic + '", "unit_of_measurement": "%", "value_template": "{{ value_json.humidity }}" }'
  #print( "send " + topic + " : " + payload )
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

  mqtt_client.disconnect()

  mqtt_client.loop_stop()

  print( "mqtt stopped" )


def send_mqtt( temperature, pressure, humidity ):

  global conf, mqtt_client

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
      "measurement": "Dummy BME280 Sensor",
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

  if 'influxServer' in conf:
    init_mqtt()

  if 'influxServer' in conf:
    init_influx()


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

    finalize_mqtt()


if __name__=="__main__":
    main()

