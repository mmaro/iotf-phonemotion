#!/bin/bash

# Helper script to update zonedemo instance that is inactive as defined by the absence
# of iotf.mybluemix.net route.

active=$(cf apps | grep iotf.mybluemix.net | awk '{print $1}')
inactive=$(cf apps | grep -v iotf.mybluemix.net | grep zonedemo | awk '{print $1}')
echo "${active} is active and ${inactive} is inactive"

cf push $inactive -f manifest.yml || { echo 'push failed' ; exit 1; }
