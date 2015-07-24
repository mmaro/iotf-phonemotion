#!/bin/bash

# Helper script to migrate iotf.mybluemix.net route from zonedemo instance that has it
# to zonedemo instance that does not have it.

active=$(cf apps | grep iotf.mybluemix.net | awk '{print $1}')
inactive=$(cf apps | grep -v iotf.mybluemix.net | grep zonedemo | awk '{print $1}')
echo "${active} is active and ${inactive} is inactive"

cf map-route $inactive mybluemix.net -n iotf || { echo 'map route failed' ; exit 1; }

echo "Sleeping while the route catches up"
sleep 10
cf unmap-route $active mybluemix.net -n iotf
