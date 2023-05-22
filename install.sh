#!/bin/bash
apt update
apt install gcc pkg-config qemu-system-x86-64 qemu-system-i386 dnsmasq-base qemu qemu-utils libvirt-daemon-system libvirt-clients qemu-kvm libvirt-dev python3 python3-pip python3-venv python3-pip python3-dev -y
python3 -m venv venv
./venv/bin/pip install libvirt-python quart pyusb
echo -e '\nuser = "root"\ngroup = "root"' >> /etc/libvirt/qemu.conf
service libvirtd restart
mkdir ./data/disks ./data/isos ./data/vms