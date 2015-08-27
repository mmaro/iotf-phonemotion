import pagerduty
import slack
from bottle import request, Bottle, abort, static_file, template, HTTPError, HTTPResponse
import time
import ibmiotf.application
import cloudant
import json
import uuid
import urllib
import os
import bottle
import sys
import traceback
import logging
from logging.handlers import RotatingFileHandler

# setup logging
# Generate a default rotating file log handler and stream handler
logFileName = 'server.log'
fhFormatter = logging.Formatter('%(asctime)-25s %(name)-25s ' + ' %(levelname)-7s %(message)s')
rfh = RotatingFileHandler(logFileName, mode='a', maxBytes=52428800 , backupCount=1, encoding=None, delay=True)
rfh.setFormatter(fhFormatter)

logger = logging.getLogger(__name__)
logger.addHandler(rfh)
logger.setLevel(logging.DEBUG)

def do_monitor():
	try:
		exception = sys.exc_info()[1]
		stack = traceback.format_exc()
		
		if exception is not None:
			# pagerduty
			pagerduty.raiseEvent("BluemixZoneDemo incident: %s" % exception, "Exception stack:\n%s" % stack)		
			
			# slack
			data = {'text': "BluemixZoneDemo incident: %s\nException stack:\n%s" % (exception, stack)}
			slack.postToSlack(data)
		
	except:
		logger.error(sys.exc_info()[0])
		logger.error(traceback.format_exc())
		
	
app = Bottle()


# If running in Bluemix, the VCAP environment variables will be available, and hence we can look 
# up the bound Cloudant and IoT Foundation services that are required by this application.
if "VCAP_APPLICATION" in os.environ:
	application = json.loads(os.getenv('VCAP_APPLICATION'))
	service = json.loads(os.getenv('VCAP_SERVICES'))
	
	uri = application["application_uris"][0]
	
	# Check we have a cloudantNoSQLDB service bound
	if "cloudantNoSQLDB" not in service:
		logger.error(" CloudantNoSQLDB service has not been bound!")
		raise Exception("cloudantNoSQLDB service has not been bound!")

	# IOTF application client configuration
	applicationOptions = ibmiotf.application.ParseConfigFromBluemixVCAP()

	# Cloudant client configuration
	dbUsername = service['cloudantNoSQLDB'][0]['credentials']['username']
	dbPassword = service['cloudantNoSQLDB'][0]['credentials']['password']
else:
	# Not running in Bluemix, so you need to set up your own properties for local testing.
	# Ensure you blank these out before committing/uploading any code
	uri = "localhost"
	applicationOptions = {"org": "", "id": "", "auth-method": "", "auth-key": "", "auth-token": ""}
	dbUsername = ""
	dbPassword = ""


dbName = "iotfzonesample"
port = int(os.getenv('VCAP_APP_PORT', 80))
host = str(os.getenv('VCAP_APP_HOST', "0.0.0.0"))

# =============================================================================
# Choose application theme
# 
# 1. default
# 2. simple
# 3. bluemix
# 4. bluemixJuly2015 [in development]
# =============================================================================
theme = os.getenv('theme', "bluemix")
logger.info("Using theme '%s'" % theme)


# =============================================================================
# Configure global properties
# =============================================================================
cloudantAccount = cloudant.Account(dbUsername, async=True)
future = cloudantAccount.login(dbUsername, dbPassword)
login = future.result(10)
assert login.status_code == 200

cloudantDb = cloudantAccount.database(dbName)
# Allow up to 10 seconds
response = cloudantDb.get().result(10)
if response.status_code == 200:
	logger.debug(" * Database '%s' already exists (200)" % (dbName))
elif response.status_code == 404:
	logger.debug(" * Database '%s' does not exist (404), creating..." % (dbName))
	response = cloudantDb.put().result(10)
	if response.status_code != 201:
		logger.debug(" * Error creating database '%s' (%s)" % (dbName, response.status_code))
else:
	logger.error(" * Unexpected status code (%s) when checking for existence of database '%s'" % (status, dbName))
	raise Exception("Unexpected status code (%s) when checking for existence of database '%s'" % (status, dbName))

# =============================================================================
# Define application routes
# =============================================================================
@app.route('/register', method='POST')
def register():

	try:
	
		if request.json is None:
			return bottle.HTTPResponse(status=400, body="Invalid request");
		
		data = request.json
		if "email" not in data:
			return bottle.HTTPResponse(status=400, body="Credentials not provided");
		if "pin" not in data:
			return bottle.HTTPResponse(status=400, body="4-digit code not provided");
		if ' ' in data["email"]:
			return bottle.HTTPResponse(status=400, body="Spaces are not allowed");
		try:
			int(data["pin"])
		except ValueError:
			return bottle.HTTPResponse(status=400, body="4-digit code must be numeric");
		
		doc = cloudantDb.document(urllib.quote(data["email"]))
		response = doc.get().result(10)
		if response.status_code == 200:
			logger.debug("User already registered: %s" % data["email"])
			return bottle.HTTPResponse(status=409, body="User already registered");

		else:
			logger.debug("Creating new registration for %s" % data["email"])
			# Create doc
			registrationClient = ibmiotf.application.Client(applicationOptions)
			device = registrationClient.api.registerDevice("zone-sample", uuid.uuid4().hex, {"registeredTo": data["email"]} )
			registrationClient.disconnect()
			response = doc.put(params={
				'id': data["email"],
				'pin': data["pin"],
				'device': {
					'type': device['type'], 
					'id': device['id'], 
					'authtoken': device['password'],
					'clientid': device['uuid'],
					'orgid': applicationOptions['org']
				}
			}).result(10)
			if response.status_code == 201:
				return HTTPResponse(status=201)
							
		# Shouldn't get here, if we do an error has occurred
		return bottle.HTTPResponse(status=500, body="An internal server error occurred");
	except:
		do_monitor()
		logger.error("Unexpected error: %s" % traceback.format_exc())
		sys.exit(1)
		


@app.route('/auth', method='POST')
def auth():
	try:
	
		if request.json is None:
			logger.error("Invalid request to auth")
			raise HTTPError(400)
		
		data = request.json
		errors = []
		if "email" not in data:
			errors.append("email address not provided")
		if "pin" not in data:
			errors.append("pin not provided")
		if len(errors) > 0:
			logger.error("Invalid request to auth")
			raise HTTPError(400, errors)
		
		doc = cloudantDb.document(urllib.quote(data["email"]))
		response = doc.get().result(10)
		if response.status_code != 200:
			logger.debug("User not registered: %s" % data["email"])
			return bottle.HTTPResponse(status=404, body="'"+data["email"]+"' does not exist");
			
		else:
			logger.debug("User already registered: %s" % data["email"])
			docBody = response.json()
			try:
				if int(docBody["pin"]) != int(data["pin"]):
					logger.error("PIN for %s does not match (%s != %s)" % (data["email"], docBody["pin"], data["pin"]))
					return bottle.HTTPResponse(status=403, body="Incorrect PIN code for '"+data["email"]+"'");
				else:
					return docBody['device']
			except (ValueError, KeyError):
				logger.error("PIN for %s has an unexpected value: %s"% (data["email"], data["pin"]))
				return bottle.HTTPResponse(status=403, body="Incorrect code for '"+data["email"]+"'");
	except HTTPError as e:
		logger.error("HTTPError during auth: %s" % str(e))
		raise
	except:
		do_monitor()
		logger.error("Unexpected error:", traceback.format_exc())
		sys.exit(1)

@app.route('/device/<id>')
def device(id):
	return template('device', deviceId=id, uri=uri)

@app.route('/d/<id>')
def device(id):
	return template('device', deviceId=id, uri=uri)

@app.route('/')
def applicationUi():
	return template('app-' + theme, uri=uri)
				
@app.route('/websocket')
def handle_websocket():
	logger.info("Handling websocket")
	client = None
	
	def myEventCallback(event):
		try:
			if wsock:
				wsock.send(json.dumps(event.data))
		except WebSocketError as e:
			logger.error("WebSocket error in callback: %s" % str(e))
			# ignore this and let any Exception in receive() terminate the loop

	wsock = request.environ.get('wsgi.websocket')
	if not wsock:
		abort(400, 'Expected WebSocket request.')

	try:
		message = wsock.receive()
		if message is None:
			abort(400, 'No data or non UTF-8 data received over WebSocket')
		
		data = json.loads(message)
		pin = int(data["pin"])
	
		doc = cloudantDb.document(urllib.quote(data["email"]))
		response = doc.get().result(10)
		if response.status_code != 200:
			logger.error("User not registered: %s" % data["email"])
			wsock.close()
		else:
			document = response.json()
			print document
			
			if str(pin) != str(document["pin"]):
				logger.error("PIN for %s does not match (%s != %s)" % (data["email"], pin, document["pin"]))
				wsock.close()
			else:
				deviceId = str(document['device']["id"])
				deviceType = str(document['device']["type"])
				options = {"org": applicationOptions['org'], "id": str(uuid.uuid4()), "auth-method": applicationOptions['auth-method'], "auth-key": applicationOptions['auth-key'], "auth-token": applicationOptions['auth-token']}
				try :
					clientsLogFileName = "device." + data["email"] + ".log"
					fhFormatter = logging.Formatter('%(asctime)-25s %(name)-25s ' + ' %(levelname)-7s %(message)s')
					clientsLogHandler = RotatingFileHandler(clientsLogFileName, mode='a', maxBytes=10240 , backupCount=0, encoding=None, delay=True)
					clientsLogHandler.setFormatter(fhFormatter)
					client = ibmiotf.application.Client(options, logHandlers=[clientsLogHandler])
					
					client.connect()
					client.deviceEventCallback = myEventCallback
					client.subscribeToDeviceEvents(deviceType, deviceId, "+")
				except ibmiotf.ConnectionException as e: 
					# We've been unable to do the initial connect. In this case, we'll terminate the socket to trigger the client to try again.
					do_monitor()
					logger.error("Connect attempt failed: %s" % str(e))
					wsock.close()
					sys.exit(1)
	except WebSocketError as e:
		logger.error("WebSocket error during subscriber setup: %s" % str(e))
	except HTTPError as e:
		logger.error("HTTPError handling websocket: %s" % str(e))
		raise
	except:
		do_monitor()
		logger.error("Unexpected error:", sys.exc_info()[1])
		sys.exit(1)
	#Send the message back
	while True:
		try:
			message = wsock.receive()
			time.sleep(1)
			#wsock.send("Your message was: %r" % message)
		except WebSocketError as e:
			# This can occur if the browser has navigated away from the page, so the best action to take is to stop.
			logger.error("WebSocket error during loop: %s" % str(e))
			break
	# Always ensure we disconnect. Since we are using QoS0 and cleanSession=true, we don't need to worry about cleaning up old subscriptions as we go: the IoT Foundation
	# will handle this automatically.
	if client is not None:
		client.disconnect()
	

@app.route('/static/<path:path>')
def service_static(path):
	return static_file(path, root='static')

@app.route('/test/monitoring')
def test_monitoring():

	monitoringTestEnabled = os.getenv('enablemonitoringtest', None)
	
	if monitoringTestEnabled is not None and monitoringTestEnabled == "true":
	
		try:
			self.logger.info("Testing monitoring")
			raise Exception("Test Exception")
		except:
			do_monitor()
			raise
		
	return "Monitoring testing disabled."

# =============================================================================
# Start
# =============================================================================
from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketError
from geventwebsocket.handler import WebSocketHandler

import pagerduty
import slack

server = WSGIServer((host, port), app, handler_class=WebSocketHandler)
logger.info("Starting web socket server")

# tell slack we are starting
data = {'text': "BluemixZoneDemo starting"}
slack.postToSlack(data)

server.serve_forever()
