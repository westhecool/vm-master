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


def make_domain_xml(data):
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
        <address type="pci" domain="0x0000" bus="{hex(i)}" slot="0x00" function="0x0"/>
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
            d += f"""<disk type="file" device="{x["device"]}">
        <driver name="qemu" type="{x["format"]}"/>
        <source file="{x["source"]}"/>
        <target dev="sd{string.ascii_lowercase[i]}" bus="{x["bus"]}"/>
        <address type="drive" controller="0" bus="0" target="0" unit="{i}"/>
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
        <name>{data["name"]}</name>
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
            <controller type="usb" index="0" model="qemu-xhci">
                <address type="pci" domain="0x0000" bus="0x00" slot="0x03" function="0x0"/>
            </controller>
            <controller type="pci" index="0" model="pcie-root"/>
            <controller type="pci" index="1" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="1" port="0x10"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x0" multifunction="on"/>
            </controller>
            <controller type="pci" index="2" model="pcie-root-port">
                <model name="pcie-root-port"/>
            <target chassis="2" port="0x11"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x1"/>
            </controller>
            <controller type="pci" index="3" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="3" port="0x12"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x2"/>
            </controller>
                <controller type="pci" index="4" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="4" port="0x13"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x3"/>
            </controller>
            <controller type="pci" index="5" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="5" port="0x14"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x4"/>
            </controller>
            <controller type="pci" index="6" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="6" port="0x15"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x5"/>
            </controller>
            <controller type="pci" index="7" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="7" port="0x16"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x6"/>
            </controller>
            <controller type="pci" index="8" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="8" port="0x17"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x04" function="0x7"/>
            </controller>
            <controller type="pci" index="9" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="9" port="0x18"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x0" multifunction="on"/>
            </controller>
            <controller type="pci" index="10" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="10" port="0x19"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x1"/>
            </controller>
            <controller type="pci" index="11" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="11" port="0x1a"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x2"/>
            </controller>
            <controller type="pci" index="12" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="12" port="0x1b"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x3"/>
            </controller>
            <controller type="pci" index="13" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="13" port="0x1c"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x4"/>
            </controller>
            <controller type="pci" index="14" model="pcie-root-port">
                <model name="pcie-root-port"/>
                <target chassis="14" port="0x1d"/>
                <address type="pci" domain="0x0000" bus="0x00" slot="0x05" function="0x5"/>
            </controller>
            <controller type="sata" index="0">
                <address type="pci" domain="0x0000" bus="0x00" slot="0x1f" function="0x2"/>
            </controller>
            <controller type="virtio-serial" index="0">
                <address type="pci" domain="0x0000" bus="0x00" slot="0x06" function="0x0"/>
            </controller>
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
    client.defineXML(make_domain_xml(d)).create()


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


def make_network_xml(d):
    return f"""
    <network>
    <name>{d["name"]}</name>
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
        client.networkCreateXML(make_network_xml(d))
    for vm in os.listdir(config.datadir + "/vms"):
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
            client.createXML(make_domain_xml(d))
            d["state"] = "running"
            d["time"] = time.time()
            f = open(config.datadir + "/vms/" + vm, "w")
            f.write(json.dumps(d))
