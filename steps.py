#!/usr/bin/python

import sys
import subprocess
import os

vagrantfile_url = "https://raw.githubusercontent.com/wester55/tw_reader/master/Vagrantfile"
setup_command1 = "/usr/bin/curl " + vagrantfile_url + " -o Vagrantfile"
setup_command2 = "global-status | grep TrustyBox | wc -l"
run_command1 = "curl --data server=localhost:27017 'http://localhost:27080/_connect'"
run_command2 = "curl -s -X GET 'http://localhost:27080/twitter/messages/_find' | grep -Po '\"screen_name\":.*?[^\\\]\",' | awk '{print $2}' | cut -d'\"' -f2"

if len(sys.argv) != 2:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)

vagrant = subprocess.Popen(["which", "vagrant"], stdout=subprocess.PIPE).communicate()[0]
vagrant = vagrant.rstrip()
if vagrant == "":
    print "Vagrant not found"
    exit (1)
exist = subprocess.Popen([vagrant, setup_command2], stdout=subprocess.PIPE).communicate()[0]
if sys.argv[1] == "setup":
    if exist != 0:
	    print "Looks like our project already running, may be you want './steps.py run'?"
	    exit (1)
    fldr = os.path.expanduser("~") + "/TrustyBox"
    subprocess.call(["mkdir", fldr])
    os.chdir(fldr)
    subprocess.call([vagrant, "init"])
    p = subprocess.Popen(setup_command1, shell=True)
    p.communicate()
    subprocess.call([vagrant, "up"])
elif sys.argv[1] == "run":
    if exist != 1:
	    print "Looks like our project not running, you need './steps.py setup' first."
	    exit (1)
    p = subprocess.Popen(run_command1, shell=True)
    p.communicate()
    print ""
    p = subprocess.Popen(run_command2, shell=True)
    p.communicate()
else:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)
