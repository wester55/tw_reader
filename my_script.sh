#!/bin/sh -e

(nohup python /home/vagrant/sleepy.mongoose/httpd.py &); nohup python /home/vagrant/streaming.py | mongoimport --db twitter --collection messages &
exit 0