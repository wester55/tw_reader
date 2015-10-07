# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "trusty"
  config.vm.hostname = "tweety"
  config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"
  config.vm.network "forwarded_port", guest: 27080, host: 27080

  config.vm.provision "shell", inline: <<-SHELL
    apt-get update
    apt-get install -y mongodb
    apt-get install -y python-pip
    pip install pymongo==2.7.2
    apt-get -y install git
    git clone https://github.com/mongodb-labs/sleepy.mongoose.git
    mongo twitter --eval "db.createCollection( 'messages', { capped: true, size: 100000 } )"
    wget https://raw.githubusercontent.com/wester55/tw_reader/master/streaming2.py
    sudo nohup python /home/vagrant/sleepy.mongoose/httpd.py > nohup1.out 2>&1 & sleep 1
    sudo nohup python /home/vagrant/streaming.py SEARCHSTRING | mongoimport --db twitter --collection messages > nohup2.out 2>&1 & sleep 1
  SHELL

end
