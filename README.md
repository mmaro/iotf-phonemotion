#Internet of Things PhoneMotion Demo Application
Demonstration application showing how to send events to the cloud from a device and process them in an application.  The application demonstrates one approach to delegating access to sensor data to users of a backend application authenticated with a single API key.

See the demo application running live in the IBM Bluemix Internet of Things solutions page https://bluemix.net/solutions/iot


---


##Introduction
The application has two main pieces of function.


### The WSGI Application
The main application is a Python WSGI server which primarily exists to provide delegated authentication to real time device events.  The application requires a user to register a unique username and PIN.  Once authorized using the correct combination of username and PIN the application renders a number of realtime visualizations representing the movement of the device associated with that user.


### The Simulated Device
The second part of the application is a page designed to be run on a users phone that uses JavaScript to simulate device code running on the phone.  The device code presents the same username & PIN to the backend application for authentication, on a successful authentication the backend application will provide the device with the necessary credentials required to connect securely to the Internet of Things service.


---


##Bluemix Deployment

Deploy the mobile phone demonstration into your own set of Bluemix services: a Python runtime, the Internet of Things service for device MQTT messaging and the Cloudant service for application data.

It is better if you have a Bluemix account before you get started. https://bluemix.net/registration

[![Deploy to Bluemix]
(https://bluemix.net/deploy/button.png)]
(https://bluemix.net/deploy?repository=)

See everything deployed in your [Bluemix dashboard](bluemix.net/?direct=classic/#/resources).

Or if you want to deploy from your local command-line...

###Bluemix Command-line Prerequisites
+ GitHub client [git](https://github.com/)
+ Cloud Foundry CLI [cf](https://github.com/cloudfoundry/cli/releases)
+ Bluemix account [register](https://bluemix.net/registration)

###Get the sample source code
```
$ git clone https://github.com/ibm-messaging/iotf-phonemotion.git
```

###Create a new application
```bash
$ cf push <app_name> --no-start
```

###Create the required services
```bash
$ cf create-service iotf-service iotf-service-free phonemotion-iotf
$ cf create-service cloudantNoSQLDB Shared phonemotion-cloudant
```

### Bind the services to your application
```bash
$ cf bind-service <app_name> phonemotion-iotf
$ cf bind-service <app_name> phonemotion-cloudant
```

###Start the application
```
cf start <app_name>
```
###Launch your application

Open http://&lt;app_name&gt;.mybluemix.net/ in a browser


---


##Configuration
The demo supports multiple themes.  The Demo running in Bluemix uses a highly customised theme specifically designed for the Bluemix Internet of Things solution page, but there are a number of simpler themes included in the sample code that provide a cleaner starting point for building your own application based on this sample.

One way to do this is to use the cf **set-env** command:
```
cf set-env <app_name> theme simple
```

To change the theme simply set a value for the "theme" environment variable to one of these options:
 - **default** - The original theme, provides the traditional interface associated with a modern web application, with discrete registration and login options for the application user.
 - **simple** - A simplified theme, which combines registration and login into a single "Go" action.  This will login a user if the username matches an existing user (and the PIN is correct), or register a new user if the username is new to the system.  This is the model that the demo running in the Bluemix IOT zone utilises.
 - **bluemix** - A highly customised theme designed to seemlessly integrate into the Bluemix IOT Zone.
