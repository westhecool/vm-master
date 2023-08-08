import usb.core
import random
import time
import config
import os
import libvirt
import string
import json


def list_host_usb():
    d = []
    for device in usb.core.find(find_all=True):
        dev = usb.core.find(idVendor=device.idVendor,
                            idProduct=device.idProduct)
        name = usb.util.get_string(dev, dev.iProduct)
        device.name = name
        d.append(device)
    return d


def make_mac():
    mac = [0x00, 0x16, 0x3e, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, mac))


def make_domain_xml(data, name):
    def getboot():
        d = ""
        for x in data["os"]["boot"]:
            d += f"""<boot dev="{x}"/>\n"""
        return d

    def ifelse(x, y, z):
        if x:
            return y
        else:
            return z

    def getbootmenu():
        if data["os"]["bios"]["bootmenu"]:
            return f"""<bootmenu enable="yes" timeout="{data["os"]["bios"]["bootmenu"]}"/>"""
        else:
            return """<bootmenu enable="no">"""

    def getvcpus():
        return int(data["cpu"]["sockets"]) * int(data["cpu"]["dies"]) * int(data["cpu"]["cores"]) * int(data["cpu"]["threads"])

    def getnetworks():
        d = ""
        i = 0
        for x in data["devices"]["networks"]:
            d += f"""<interface type="{x["source"]["type"]}">
        <source {x["source"]["type"]}="{x["source"]["network"]}"/>
        <model type="{x["model"]}"/>
        <mac address="{x["mac"]}"/>
        <address type="pci" domain="0x0000" bus="0x00" slot="{hex(i + 7)}" function="0x0"/> <!-- start the index at 7 -->
        <bandwidth>\n"""
            if x["bandwidth"]["inbound"]["average"] or x["bandwidth"]["inbound"]["peak"] or x["bandwidth"]["inbound"]["burst"]:
                d += f"""<inbound {ifelse(x["bandwidth"]["inbound"]["average"], f"average='" + x["bandwidth"]["inbound"]["average"] + "'", "")} {ifelse(x["bandwidth"]["inbound"]["peak"], f"average='" + x["bandwidth"]["inbound"]["peak"] + "'", "")} {ifelse(x["bandwidth"]["inbound"]["burst"], "burst='" + x["bandwidth"]["inbound"]["burst"] + "'", "")}/>"""
            if x["bandwidth"]["outbound"]["average"] or x["bandwidth"]["outbound"]["peak"] or x["bandwidth"]["outbound"]["burst"]:
                d += f"""<outbound {ifelse(x["bandwidth"]["outbound"]["average"], f"average='" + x["bandwidth"]["outbound"]["average"] + "'", "")} {ifelse(x["bandwidth"]["inbound"]["peak"], f"average='" + x["bandwidth"]["inbound"]["peak"] + "'", "")} {ifelse(x["bandwidth"]["outbound"]["burst"], "burst='" + x["bandwidth"]["outbound"]["burst"] + "'", "")}/>"""
            d += """\n</bandwidth>
    </interface>\n"""
            i += 1
        return d

    def getdisks():
        d = ""
        i = 0
        for x in data["devices"]["disks"]:
            address = ""
            devtype = "sd"
            if x["bus"] == "sata" or x["bus"] == "scsi":
                address = f"""<address type="drive" controller="0" bus="0" target="0" unit="{i}"/>"""
            elif x["bus"] == "virtio":
                devtype = "vd"
                address = f"""<address type="pci" domain="0x0000" bus="0x00" slot="{hex(i + 7 + len(data["devices"]["networks"]))}" function="0x0"/>""" # start the index at 7 plus the number of networks
            elif x["bus"] == "usb":
                address = f"""<address type="usb" bus="1" port="{i}"/>"""
            d += f"""<disk type="file" device="{x["device"]}">
        <driver name="qemu" type="{x["format"]}"/>
        <source file="{x["source"]}"/>
        <target dev="{devtype}{string.ascii_lowercase[i]}" bus="{x["bus"]}"/>
        {address}
        <iotune>"""
            for y in x["iotune"]:
                if x["iotune"][y]:
                    d += f"""<{y}>{x["iotune"][y]}</{y}>\n"""
            d += """</iotune>
        </disk>\n"""
            i += 1
        return d
    d = f"""
    <domain type="kvm">
        <name>{name}</name>
        <metadata>
            <madeby>VM Master</madeby>
        </metadata>
        <on_poweroff>destroy</on_poweroff>
        <on_reboot>restart</on_reboot>
        <on_crash>restart</on_crash>
        <os>
            <type arch="{data["os"]["arch"]}" machine="{data["os"]["machine"]}">hvm</type>
            {getboot()}
            {getbootmenu()}
            <smbios mode="sysinfo"/>
            <bios useserial="yes" rebootTimeout="0"/>
        </os>
        <features>
            <acpi/>
            <apic/>
            <hyperv mode="custom">
                <relaxed state="on"/>
                <vapic state="on"/>
                <spinlocks state="on" retries="8191"/>
            </hyperv>
            <vmport state="off"/>
        </features>
        <sysinfo type="smbios">
            {data["os"]["bios"]["sysinfo"]}
        </sysinfo>
        <memory unit="M">{data["memory"]}</memory>
        <vcpu placement="static">{getvcpus()}</vcpu>
        <clock offset="localtime">
            <timer name="rtc" tickpolicy="catchup"/>
            <timer name="pit" tickpolicy="delay"/>
            <timer name="hpet" present="no"/>
            <timer name="hypervclock" present="yes"/>
        </clock>
        <devices>
            <input type="tablet" bus="usb">
                <address type="usb" bus="0" port="1"/>
            </input>
            <input type="mouse" bus="ps2"/>
            <input type="keyboard" bus="ps2"/>
            <cpu mode="custom" match="exact" check="none">
                <model fallback="forbid">{data["cpu"]["model"]}</model>
                <vendor>{data["cpu"]["vendor"]}</vendor>
                <topology sockets="{data["cpu"]["sockets"]}" dies="{data["cpu"]["dies"]}" cores="{data["cpu"]["cores"]}" threads="{data["cpu"]["threads"]}"/>
            </cpu>
            {getnetworks()}
            {getdisks()}
            <graphics type="vnc" port="{data["devices"]["graphics"]["vnc"]["port"]}" sharePolicy="allow-exclusive" {ifelse(data["devices"]["graphics"]["vnc"]["password"], f"passwd='{data['devices']['graphics']['vnc']['password']}'", "")}>
                <listen type="address" address="{data["devices"]["graphics"]["vnc"]["host"]}"/>
                <image compression="off"/>
            </graphics>
            <graphics type="spice" port="{data["devices"]["graphics"]["spice"]["port"]}" {ifelse(data["devices"]["graphics"]["spice"]["password"], f"passwd='{data['devices']['graphics']['spice']['password']}'", "")}>
                <listen type="address" address="{data["devices"]["graphics"]["spice"]["host"]}"/>
                <channel name="main" mode="insecure"/>
                <channel name="record" mode="insecure"/>
                <image compression="off"/>
            </graphics>
            <video>
                <model type="{data["devices"]["video"]["type"]}" vram="{data["devices"]["video"]["vram"]}" heads="1" primary="yes">
                    <acceleration accel3d="{data["devices"]["video"]["accel3d"]}"/>
                </model>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x01" function="0x0"/>
                <driver name="{data["devices"]["video"]["driver"]}"/>
            </video>
            <serial type="pty">
                <target type="isa-serial" port="0">
                    <model name="isa-serial"/>
                </target>
            </serial>
            <console type="pty">
                <target type="serial" port="0"/>
            </console>
            <sound model="ich9">
                <address type="pci" domain="0x0000" bus="0x00" slot="0x02" function="0x0"/>
            </sound>
            <audio type="spice" id="1"/>
            <controller type="usb" index="0" model="qemu-xhci"> <!-- usb bus 1 for internal devices -->
                <address type="pci" domain="0x0000" bus="0x00" slot="0x03" function="0x0"/>
            </controller>
            <controller type="usb" index="1" model="qemu-xhci"> <!-- usb bus 2 for disks -->
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x0"/>
            </controller>
            <controller type="usb" index="2" model="qemu-xhci"> <!-- usb bus 3 for external devices -->
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x0"/>
            </controller>
            <controller type="virtio-serial" index="0">
                <address type="pci" domain="0x0000" bus="0x00" slot="0x06" function="0x0"/>
            </controller>
            <controller type="sata" index="0">
                <address type="pci" domain="0x0000" bus="0x00" slot="0x1f" function="0x2"/>
            </controller>
            <controller type="pci" index="0" model="pcie-root"/>
        </devices>
    </domain>
    """
    return d


def is_authenticated(login_cookie):
    if login_cookie is not None:
        if len(login_cookie.split(":")) > 1:
            if os.path.isfile(config.datadir + "/users/" + login_cookie.split(":")[0]):
                f = open(config.datadir + "/users/" +
                         login_cookie.split(":")[0])
                d = json.loads(f.read())
                f.close()
                if d["password"] == login_cookie.split(":")[1]:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False
    else:
        return False


def make_and_start_vm(client, name):
    try:
        vm = client.lookupByName(name)
        try:
            vm.destroy()
        except:
            pass
        try:
            vm.undefine()
        except:
            pass
    except:
        pass
    f = open("./data/vms/" + name)
    d = json.loads(f.read())
    f.close()
    d["state"] = "running"
    d["time"] = time.time()
    f = open("./data/vms/" + name, "w")
    f.write(json.dumps(d))
    f.close()
    client.defineXML(make_domain_xml(d, name)).create()


def convert_seconds(seconds):
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    months = days // 30

    time_units = []

    if months > 0:
        time_units.append(f"{months} months")
    if days % 30 > 0:
        time_units.append(f"{days % 30} days")
    if hours % 24 > 0:
        time_units.append(f"{hours % 24} hours")
    if minutes % 60 > 0:
        time_units.append(f"{minutes % 60} minutes")
    if seconds % 60 > 0:
        time_units.append(f"{seconds % 60} seconds")

    result = ", ".join(time_units)
    return result


def is_file_system_safe(string):
    illegal_chars = {'/', '\\', '?', '%', '*', ':', '|', '"', '<', '>', '.'}
    for char in string:
        if char in illegal_chars:
            return False
    return True


def vm_is_running(client, name):
    try:
        vm = client.lookupByName(name)
        return vm.isActive() == 1
    except:
        return False


def mark_vm_as_stopped(name):
    f = open("./data/vms/" + name)
    d = json.loads(f.read())
    f.close()
    d["state"] = "stopped"
    d["time"] = time.time()
    f = open("./data/vms/" + name, "w")
    f.write(json.dumps(d))
    f.close()


def make_network_xml(d, name):
    return f"""
    <network>
    <name>{name}</name>
    <bridge name="{d["iface"]}"/>
    <forward mode="nat"/>
    <forwarder addr="{d["nameservers"][0]}"/>
    <forwarder addr="{d["nameservers"][1]}"/>
    <ip address="{d["ip"]}" netmask="255.255.255.0">
        <dhcp>
            <range start="{d["dhcp"]["start"]}" end="{d["dhcp"]["end"]}"/>
        </dhcp>
    </ip>
    </network>
    """


def boot():
    client = libvirt.open("qemu:///system")
    # net
    for net in os.listdir(config.datadir + "/networks"):
        try:
            net_xml = client.networkLookupByName(net)
            try:
                net_xml.destroy()
            except:
                pass
            try:
                net_xml.undefine()
            except:
                pass
        except:
            pass
        f = open(config.datadir + "/networks/" + net)
        d = json.loads(f.read())
        f.close()
        client.networkCreateXML(make_network_xml(d, net))
    for vm in os.listdir(config.datadir + "/vms"): # auto start VMs that where not stopped by user
        f = open(config.datadir + "/vms/" + vm)
        d = json.loads(f.read())
        f.close()
        if d["state"] == "running" and not vm_is_running(client, vm):
            try:
                vm_xml = client.lookupByName(vm)
                try:
                    vm_xml.destroy()
                except:
                    pass
                try:
                    vm_xml.undefine()
                except:
                    pass
            except:
                pass
            client.createXML(make_domain_xml(d, vm))
            d["state"] = "running"
            d["time"] = time.time()
            f = open(config.datadir + "/vms/" + vm, "w")
            f.write(json.dumps(d))


def check_if_vm_stopped():
    client = libvirt.open("qemu:///system")
    while True:
        for vm in os.listdir(config.datadir + "/vms"):
            f = open(config.datadir + "/vms/" + vm)
            d = json.loads(f.read())
            f.close()
            if d["state"] == "running":
                if not vm_is_running(client, vm):
                    mark_vm_as_stopped(vm)
        time.sleep(1) # add a delay to avoid high resource usage