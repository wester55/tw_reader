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
    call(["mkdir", "~/TrustyBox"])
    os.chdir("~/TrustyBox")
    call(["Vagrant", "init"])
    call(["curl", vagrantfile_url + " -o Vagrantfile"])
    call(["Vagrant", "up"])
elif sys.argv[1] == "run":
    p = subprocess.Popen(run_command1, shell=True, stderr=subprocess.PIPE)
    output, err = p.communicate()
    p = subprocess.Popen(run_command2, shell=True, stderr=subprocess.PIPE)
    output, err = p.communicate()
    print output
else:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)
