# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "trusty"
  config.vm.hostname = "tweety"
  config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"

  config.vm.provision "shell", inline: <<-SHELL
    apt-get install -y mongodb
    apt-get install -y python-pip
    pip install tweepy
    mongo twitter --eval "db.createCollection( 'messages', { capped: true, size: 100000 } )"
    wget https://raw.githubusercontent.com/wester55/tw_reader/master/streaming.py
    nohup python /home/vagrant/streaming.py | mongoimport --db twitter --collection messages &
  SHELL
end