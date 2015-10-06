__author__ = 'Sasha'

import sys
from subprocess import call
import os

vagrantfile_url = "https://raw.githubusercontent.com/wester55/tw_reader/master/Vagrantfile"
filter_command = "-s -X GET 'http://localhost:27080/twitter/messages/_find' | grep -Po '\"screen_name\":.*?[^\\]\",' | awk '{print $2}' | cut -d'\"\' -f2"

if len(sys.argv) != 1:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)

if sys.argv[1] == "setup":
    call(["mkdir", "~/TrustyBox"])
    os.chdir("~/TrustyBox")
    call(["Vagrant", "init"])
    call(["curl", vagrantfile_url + " -o Vagrantfile"])
    call(["Vagrant", "up"])
elif sys.argv[1] == "run":
    call(["curl", "--data server=localhost:27017 'http://localhost:27080/_connect'"])
    call(["curl", filter_command])
else:
    print "Only one argument allowed, either \"setup\" or \"run\" string must be specified"
    exit(1)