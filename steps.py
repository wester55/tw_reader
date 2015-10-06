#!/usr/bin/python

import sys
import subprocess
import os

vagrantfile_url = "https://raw.githubusercontent.com/wester55/tw_reader/master/Vagrantfile"
run_command1 = "curl --data server=localhost:27017 'http://localhost:27080/_connect'"
run_command2 = "curl -s -X GET 'http://localhost:27080/twitter/messages/_find' | grep -Po '\"screen_name\":.*?[^\\\]\",' | awk '{print $2}' | cut -d'\"' -f2"

if len(sys.argv) != 2:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)

if sys.argv[1] == "setup":
    fldr = os.path.expanduser("~") + "/TrustyBox"
    vagrant = subprocess.Popen(["which", "vagrant"], stdout=subprocess.PIPE).communicate()[0]
    if vagrant == "":
        print "Vagrant not found"
        exit (1)
    try:
        subprocess.call(["mkdir", fldr])
    except:
        pass
    os.chdir(fldr)
    subprocess.call([vagrant, "init"])
    subprocess.call(["/usr/bin/curl", vagrantfile_url + " -o Vagrantfile"])
    subprocess.call([vagrant, "up"])
elif sys.argv[1] == "run":
    p = subprocess.Popen(run_command1, shell=True, stderr=subprocess.PIPE)
    output, err = p.communicate()
    print ""
    p = subprocess.Popen(run_command2, shell=True, stderr=subprocess.PIPE)
    output, err = p.communicate()
else:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)
