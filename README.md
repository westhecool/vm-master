# VM Master
A Modern looking web interface for libvirt.
<br>
Really isn't completely finished yet but this is the first release.
## Installing
The installer is only for Debain right now.
<br>
Install git:
```sh
sudo apt update && sudo apt install git -y
```
Then install VM Master:
```sh
git clone https://github.com/westhecool/vm-master
cd vm-master
sudo bash install.sh
```
This will install all the necessary dependencies.
## running
You can start VM Master by running:
```sh
sudo ./venv/bin/python3 main.py
```
This will start VM Master on `0.0.0.0:8880`
## Usage
The default password is `password` and the user is `root`. I highly recommend you change it.
<br>
To set the root password run `python3 setpassword.py (new password)`
<br>
Place ISO files in `./data/isos`