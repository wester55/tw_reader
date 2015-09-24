# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "trusty"
  config.vm.hostname = "tweety"
  config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"
  config.vm.network "forwarded_port", guest: 27080, host: 27080

  config.vm.provision "shell", inline: <<-SHELL
    apt-get install -y mongodb
    apt-get install -y python-pip
    pip install tweepy
    pip install pymongo==2.7.2
    apt-get -y install git
    git clone https://github.com/mongodb-labs/sleepy.mongoose.git
    mongo twitter --eval "db.createCollection( 'messages', { capped: true, size: 100000 } )"
    wget https://raw.githubusercontent.com/wester55/tw_reader/master/streaming.py
    wget https://raw.githubusercontent.com/wester55/tw_reader/master/my_script.sh; chmod a+x /home/vagrant/my_script.sh
  SHELL
end