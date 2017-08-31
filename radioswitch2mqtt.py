import RPi.GPIO as GPIO
import paho.mqtt.client as mqtt
import atexit
import time
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

logging.info('Starting MQTT to Radio driver')

data_pin = 4 # GPIO4, pin no 7
device_controllers = []


def main():
	arguments = parse_arguments()
	
	setup_GPIO()
	client = setup_mqtt(arguments.user, arguments.password)	
	
	global device_controllers
	device_controllers = setup_devices(client)
	
	logging.info('Connecting to MQTT')

	client.connect(arguments.host, arguments.port, 60)

	logging.info('Entering MQTT processing loop')
	
	# Blocking call that processes network traffic, dispatches callbacks and
	# handles reconnecting.
	client.loop_forever()

def parse_arguments():
	parser = argparse.ArgumentParser()
	parser.add_argument('--host', help='MQTT - host', required=True)
	parser.add_argument('--port', help='MQTT - port', default=1883)
	parser.add_argument('--user', help='MQTT - user')
	parser.add_argument('--password', help='MQTT - password')

	parsed = parser.parse_args()
	
	return parsed

def setup_GPIO():
	logging.info('Setting up GPIO')

	GPIO.setmode(GPIO.BCM)
	GPIO.setup(data_pin, GPIO.OUT)
	GPIO.output(data_pin, GPIO.LOW)

	def cleanup_GPIO():
		logging.info('Cleaning up GPIO')
		GPIO.cleanup()
	
	atexit.register(cleanup_GPIO)

def setup_devices(mqttClient):

	def deviceBuilder(name, status_on_topic, set_on_topic, radio_on_command, radio_off_command):
		state = { 'is_on': False }
		
		def report_status():
			mqttClient.publish(status_on_topic, int(state['is_on']), qos=2, retain=True)

		def set_status(is_on):
			logging.info('Switching '+ name + ' ' + ('ON' if is_on else 'OFF'))
			state['is_on'] = is_on
			send_radio_command(radio_on_command if is_on else radio_off_command)			
 
		def can_handle(topic):
			if(set_on_topic == topic):
				return True
			return False
		
		def handle(topic, payload):
			if(topic == set_on_topic):
				set_status(bool(int(payload)))
				report_status()
		
		def subscribe():
			mqttClient.subscribe(set_on_topic)
			#report initial state
			set_status(state['is_on'])
		
		return { 'can_handle': can_handle, 'handle': handle, 'subscribe': subscribe }

	return [
		#remote switch number 1
		deviceBuilder('LivingRoom:CornerLamp', 'livingroom/lamp/status','livingroom/lamp/set', '000001000101010100110011','000001000101010100111100' )
	
		#remove switch number 2 - not used at the moment
		#,deviceBuilder('Not set', '', '', '000001000101010111000011', '000001000101010111001100')

		#remove switch number 3 - not used at the moment
		#,deviceBuilder('Not set', '', '', '000001000101011100000011', '000001000101011100001100')
		]		
		

def setup_mqtt(user, password):
	logging.info('Setting up MQTT')
	
	client = mqtt.Client()
	client.on_connect = on_connect;
	client.on_message = on_message; 

	if(user != None and password != None):
		client.username_pw_set(user, password)

	def cleanup_mqtt():
		logging.info('Cleaning up MQTT')
		client.disconnect()

	atexit.register(cleanup_mqtt)

	return client

def on_connect( client, userdata, flags, rc):
	#0: Connection successful 
	#1: Connection refused - incorrect protocol version 
	#2: Connection refused - invalid client identifier 
	#3: Connection refused - server unavailable 
	#4: Connection refused - bad username or password 
	#5: Connection refused - not authorised 
	#6-255: Currently unused
	
	if rc == 0:
		logging.info('Sucesfully connected to MQTT')
		for device in device_controllers:
			device['subscribe']()
	else:
		logging.warning('Connecting to MQTT failed with code: ' + str(rc))

def on_message( client, userdata, msg):
	logging.debug('Received message on topic:' + msg.topic + ', payload:' + str(msg.payload))
	
	for device in device_controllers:
		if(device['can_handle'](msg.topic)):
			device['handle'](msg.topic, msg.payload)
		else:
			logging.warning('Received unexpected message on topic: ' + msg.payload)

def begin_command():
	# sends the command header
	# returns an array of functions to be called for each bit 
	# return[0]() - for logical zero and return[1]() for logical one

	short_sleep_duration = 0.00014 #0.00045  #0.0002
	long_sleep_duration =  0.00042 #0.0009 #0.0006
	very_long_sleep_duration = 0.00462  #0.0096 #0.0132

	def send_header():
		GPIO.output(data_pin, GPIO.HIGH)
		time.sleep(short_sleep_duration)

		GPIO.output(data_pin, GPIO.LOW) 
		time.sleep(very_long_sleep_duration)

	def send_one():
		GPIO.output(data_pin, GPIO.HIGH)
		time.sleep(long_sleep_duration)	

		GPIO.output(data_pin, GPIO.LOW)
		time.sleep(short_sleep_duration)

	def send_zero():
		GPIO.output(data_pin, GPIO.HIGH)
		time.sleep(short_sleep_duration)
			
		GPIO.output(data_pin, GPIO.LOW)
		time.sleep(long_sleep_duration)

	send_header()

	return [send_zero, send_one]

def send_radio_command(command):
	logging.debug('Sending radio command:' + command)

	repeat_command = 6
	for x in range(0, repeat_command):
		
		senders = begin_command()
		
		for b in command:
			senders[int(b)]()


# BEGIN EXECUTION
main()
