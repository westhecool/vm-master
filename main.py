import time
import libvirt
import os
import sys
import json
import string
import random
from hashlib import sha256
import asyncio
import core
import config as vmmconfig
import threading
import subprocess
from quart import *
import atexit
import argparse

parser = argparse.ArgumentParser(
        description="A Modern looking web interface for libvirt")
parser.add_argument(
        "--auto-start-libvirt", default=False, action="store_true",
        help="Auto start libvirt this can be useful if your not using systemd. (Like in a docker container)", required=False)
args = parser.parse_args()

virtlogd_process = None
libvirtd_process = None
if args.auto_start_libvirt:
    print("Auto starting libvirt...")
    virtlogd_process = subprocess.Popen("virtlogd", stderr=sys.stderr, stdout=sys.stdout)
    libvirtd_process = subprocess.Popen("libvirtd", stderr=sys.stderr, stdout=sys.stdout)
    print("libvirt started. libvirt pid: " + str(libvirtd_process.pid) + ", virtlogd pid: " + str(virtlogd_process.pid) + ".")
    print("Waiting for a bit so libvirtd can start up...")
    time.sleep(5)

def exit_handler():
    print("Exiting...")
    if libvirtd_process is not None:
        print("Killing libvirtd...")
        try:
            libvirtd_process.kill()
        except Exception as e:
            print("Could not kill libvirtd: " + str(e), file=sys.stderr)
    if virtlogd_process is not None:
        print("Killing virtlogd...")
        try:
            virtlogd_process.kill()
        except Exception as e:
            print("Could not kill virtlogd: " + str(e), file=sys.stderr)


atexit.register(exit_handler)

threading.Thread(target=core.boot).start()

cwd = os.getcwd()
app = Quart(__name__)

client = libvirt.open("qemu:///system")


@app.route("/")
async def index():
    if core.is_authenticated(request.cookies.get("login")):
        f = open("www/index.html")
        d = f.read()
        f.close()
        f = open("www/nav.html")
        nav = f.read()
        f.close()
        f = open("www/footer.html")
        footer = f.read()
        f.close()
        content = ""
        for vm in os.listdir(vmmconfig.datadir + "/vms"):
            f = open(vmmconfig.datadir + "/vms/" + vm)
            d2 = json.loads(f.read())
            f.close()
            content += f"""
            <div class="row">
                <div class="col">
                    {vm}
                </div>
                <div class="col">
                    {d2["state"]} for {core.convert_seconds(int(time.time() - d2["time"]))}
                </div>
                <div class="col">
                    <a href="/vms/{vm}">Control</a>
                </div>
            </div>
            <hr>
            """
        return await render_template_string(d, footer=footer, nav=nav, content=content)
    else:
        return redirect("/login")


@app.route("/newvm", methods=["GET", "POST"])
async def newvm():
    if core.is_authenticated(request.cookies.get("login")):
        text = ""
        form = {"name": "", "disksize": "", "iso": ""}
        if request.method == "POST":
            form = await request.form
            print(form)
            if form["name"] and form["disksize"] and form["iso"]:
                if core.is_file_system_safe(form["name"]):
                    if os.path.isfile(vmmconfig.datadir + "/vms/" + form["name"]):
                        text = '<a style="color:red">VM already exists<a>'
                    else:
                        disk = vmmconfig.datadir + \
                            "/disks/" + form["name"] + ".qcow2"
                        try:
                            disksize = form["disksize"].replace('"', '\\"')
                            if (subprocess.run(["qemu-img", "create", "-f", "qcow2", disk, disksize]).returncode == 0):
                                f = open(vmmconfig.datadir + "/templates/1")
                                d = json.loads(f.read())
                                f.close()
                                d["name"] = form["name"]
                                d["devices"]["networks"][0]["mac"] = core.make_mac()
                                d["devices"]["disks"][0]["source"] = disk
                                d["devices"]["disks"][1]["source"] = form["iso"]
                                d["devices"]["graphics"]["vnc"]["password"] = "".join(
                                    random.choices(
                                        string.ascii_uppercase + string.digits, k=8
                                    )
                                )
                                d["devices"]["graphics"]["vnc"]["host"] = "localhost"
                                d["devices"]["graphics"]["vnc"]["port"] = str(
                                    6000 +
                                    len(os.listdir(vmmconfig.datadir + "/vms"))
                                )
                                d["time"] = time.time()
                                d["state"] = "stopped"
                                f = open(
                                    vmmconfig.datadir + "/vms/" +
                                    form["name"], "w"
                                )
                                f.write(json.dumps(d))
                                f.close()
                                return redirect("/vms/" + form["name"])
                            else:
                                text = '<a style="color:red">Failed to create disk<a>'
                        except:
                            text = '<a style="color:red">Failed to create disk<a>'
                else:
                    text = '<a style="color:red">Name includes illegal characters<a>'
            else:
                text = '<a style="color:red">All fields are required<a>'
        f = open("www/newvm.html")
        d = f.read()
        f.close()
        f = open("www/nav.html")
        nav = f.read()
        f.close()
        f = open("www/footer.html")
        footer = f.read()
        f.close()
        isos = ""
        for iso in os.listdir(vmmconfig.datadir + "/isos"):
            val = vmmconfig.datadir + "/isos/" + iso
            s = ""
            if form["iso"] == val:
                s = "selected"
            isos += f"""<option {s} value="{val}">{iso}</option>"""
        return await render_template_string(
            d,
            footer=footer,
            nav=nav,
            disksize=form["disksize"],
            name=form["name"],
            isos=isos,
            text=text,
        )
    else:
        return redirect("/login")


@app.route("/files/<path:path>")
async def files(path):
    if os.path.isfile("./www/" + path):
        return await send_file("./www/" + path)
    else:
        return "File not found", 404


@app.route("/vms/<vm_name>")
async def vm(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open("www/vm.html")
            d = f.read()
            f.close()
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d2 = json.loads(f.read())
            f.close()
            f = open("www/nav.html")
            nav = f.read()
            f.close()
            f = open("www/footer.html")
            footer = f.read()
            f.close()
            return await render_template_string(
                d,
                vm_name=vm_name,
                vnc_password=d2["devices"]["graphics"]["vnc"]["password"].replace(
                    '"', '\\"'
                ),
                footer=footer,
                nav=nav,
            )
        else:
            return "VM not found", 404
    else:
        return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
async def login():
    text = ""
    f = open("www/login.html")
    d = f.read()
    f.close()
    f = open("www/footer.html")
    footer = f.read()
    f.close()
    form = {"username": "", "password": ""}
    if request.method == "POST":
        form = await request.form
        if form["username"] and form["password"]:
            if os.path.isfile(vmmconfig.datadir + "/users/" + form["username"]):
                f = open(vmmconfig.datadir + "/users/" + form["username"])
                d2 = json.loads(f.read())
                f.close()
                password = sha256(form["password"].encode("utf-8")).hexdigest()
                if d2["password"] == password:
                    resp = await make_response(redirect("/"))
                    resp.set_cookie(
                        "login",
                        form["username"] + ":" + password,
                        expires=time.time() + (86400 * 30),
                    )  # 30 days
                    return resp
                else:
                    text = '<a style="color:red">Incorrect password<a>'
            else:
                text = '<a style="color:red">Username not found<a>'
        else:
            text = '<a style="color:red">Username and password are required<a>'
    return await render_template_string(
        d,
        text=text,
        username=form["username"],
        password=form["password"],
        footer=footer,
    )


@app.route("/logout")
async def logout():
    resp = await make_response(redirect("/login"))
    resp.set_cookie("login", "", expires=0)
    return resp


@app.route("/api/vms")
def api_vms():
    if core.is_authenticated(request.cookies.get("login")):
        return jsonify(os.listdir(vmmconfig.datadir + "/vms"))
    else:
        return "Unauthorized", 403


@app.route("/api/networks")
def api_networks():
    if core.is_authenticated(request.cookies.get("login")):
        return jsonify(os.listdir(vmmconfig.datadir + "/networks"))
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>", methods=["DELETE"])
def api_vm_delete(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            os.remove(vmmconfig.datadir + "/vms/" + vm_name)
            return "ok"
        else:
            return "VM not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>")
def api_vm(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            vm = None
            d = {}
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d2 = json.loads(f.read())
            f.close()
            for disk in d2["devices"]["disks"]:
                try:
                    d3 = json.loads(
                        subprocess.run(
                            ["qemu-img", "info", "-U",
                                "--output=json", disk["source"]],
                            capture_output=True,
                        ).stdout.decode()
                    )
                    disk["size"] = d3["virtual-size"]
                    disk["used"] = d3["actual-size"]
                except Exception as e:
                    print(e)
            d["disks"] = d2["devices"]["disks"]
            d["networks"] = d2["devices"]["networks"]
            d["running"] = core.vm_is_running(client, vm_name)
            d["time_raw"] = int(time.time() - d2["time"])
            d["time"] = core.convert_seconds(d["time_raw"])
            if d["running"]:
                vm = client.lookupByName(vm_name)
                d["blockStats"] = []
                i = 0
                for disk in d2["devices"]["disks"]:
                    d["blockStats"].append(vm.blockStats(
                        "sd" + string.ascii_lowercase[i]))
                    i += 1
                # d["CPUStats"] = vm.getCPUStats(total=False)
                d["CPUStats_total"] = vm.getCPUStats(total=True)
                d["memory"] = vm.memoryStats()
                d["vcpus"] = len(vm.vcpus()[0])
                d["interfaceStats"] = {}

                d["networks_live"] = vm.interfaceAddresses(0)
                for name in d["networks_live"]:
                    d["interfaceStats"][name] = vm.interfaceStats(name)

            return jsonify(d)
        else:
            return "VM not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/<action>")
def vm_action(vm_name, action):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            try:
                if action == "reset":
                    vm = client.lookupByName(vm_name)
                    try:
                        vm.destroy()
                    except:
                        pass
                    try:
                        vm.undefine()
                    except:
                        pass
                    core.mark_vm_as_stopped(vm_name)
                    core.make_and_start_vm(client, vm_name)
                elif action == "destroy":
                    vm = client.lookupByName(vm_name)
                    try:
                        vm.destroy()
                    except:
                        pass
                    try:
                        vm.undefine()
                    except:
                        pass
                    core.mark_vm_as_stopped(vm_name)
                elif action == "start":
                    core.make_and_start_vm(client, vm_name)
                elif action == "stop":
                    vm = client.lookupByName(vm_name)
                    vm.shutdown()
                    while vm.isActive() == 1:
                        time.sleep(1)
                    try:
                        vm.undefine()
                    except:
                        pass
                    core.mark_vm_as_stopped(vm_name)
                elif action == "reboot":
                    vm = client.lookupByName(vm_name)
                    vm.shutdown()
                    while vm.isActive() == 1:
                        time.sleep(1)
                    try:
                        vm.undefine()
                    except:
                        pass
                    core.mark_vm_as_stopped(vm_name)
                    core.make_and_start_vm(client, vm_name)
                else:
                    return "Not found", 404
                return "ok"
            except Exception as e:
                print(e)
                return str(e), 500
        else:
            return "VM not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/config", methods=["GET"])
async def vm_config(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            return jsonify(d)
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/config", methods=["POST"])
async def vm_config_set(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            form = await request.form
            if form["config"]:
                json.loads(form["config"])  # Attempt to catch invalid requests
                f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
                f.write(form["config"])
                f.close()
                return "ok"
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/add_network", methods=["GET"])
def vm_network_add(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            net = {
                "model": "e1000e",
                "mac": core.make_mac(),
                "source": {
                    "type": "network",
                    "network": os.listdir(vmmconfig.datadir + "/networks")[0],
                },
                "bandwidth": {
                    "inbound": {"average": "", "burst": "", "peak": ""},
                    "outbound": {"average": "", "burst": "", "peak": ""},
                },
            }
            d["devices"]["networks"].append(net)
            f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
            f.write(json.dumps(d))
            f.close()
            return net
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/add_disk", methods=["GET"])
def vm_disk_add(vm_name):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            disk = {
                "device": "",
                "format": "",
                "source": "",
                "bus": "",
                "iotune": {
                    "total_bytes_sec": "",
                    "read_bytes_sec": "",
                    "write_bytes_sec": "",
                    "total_iops_sec": "",
                    "read_iops_sec": "",
                    "write_iops_sec": "",
                },
            }
            d["devices"]["disks"].append(disk)
            f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
            f.write(json.dumps(d))
            f.close()
            return jsonify({"id": len(d["devices"]["disks"] - 1)})
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/network/<network>", methods=["GET"])
async def vm_network(vm_name, network):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            net = None
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            for n in d["devices"]["networks"]:
                if n["mac"] == network:
                    net = jsonify(n)
            if net is not None:
                return net
            else:
                return "Cannot find network", 404
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/network/<network>", methods=["DELETE"])
async def vm_network_delete(vm_name, network):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            net = None
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            for n in d["devices"]["networks"]:
                if n["mac"] == network:
                    net = n
            if net is not None:
                d["devices"]["networks"].remove(net)
                f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
                f.write(json.dumps(d))
                f.close()
                return "ok"
            else:
                return "Cannot find network", 404
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/network/<network>", methods=["POST"])
async def vm_network_set(vm_name, network):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            net = None
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            i = 0
            for n in d["devices"]["networks"]:
                if n["mac"] == network:
                    net = i
                i += 1
            if net is not None:
                d["devices"]["networks"][net] = json.loads(
                    (await request.form)["config"]
                )
                f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
                f.write(json.dumps(d))
                f.close()
                return "ok"
            else:
                return "Cannot find network", 404
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/disks/<disk>", methods=["GET"])
def vm_disk(vm_name, disk):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            return jsonify(d["devices"]["disks"][int(disk)])
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/disks/<disk>", methods=["DELETE"])
def vm_disk_delete(vm_name, disk):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            del d["devices"]["disks"][int(disk)]
            f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
            f.write(json.dumps(d))
            f.close()
            if request.args.get("delete") == "true":
                os.remove(vmmconfig.datadir + "/disks/" + vm_name + ".qcow2")
            return "ok"
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


@app.route("/api/vms/<vm_name>/disks/<disk>", methods=["POST"])
async def vm_disk_set(vm_name, disk):
    if core.is_authenticated(request.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            d["devices"]["disks"][int(disk)] = json.loads(
                (await request.form)["config"]
            )
            f = open(vmmconfig.datadir + "/vms/" + vm_name, "w")
            f.write(json.dumps(d))
            f.close()
            return "ok"
        else:
            return "Not found", 404
    else:
        return "Unauthorized", 403


async def vnc_sending(reader, writer):
    while True:
        d = await reader.read(1024)
        await websocket.send(d)


async def vnc_receiving(reader, writer):
    while True:
        data = await websocket.receive()
        writer.write(data)


@app.websocket("/api/vms/<vm_name>/vncws")
async def vnc_ws(vm_name):
    if core.is_authenticated(websocket.cookies.get("login")):
        if os.path.isfile(vmmconfig.datadir + "/vms/" + vm_name):
            f = open(vmmconfig.datadir + "/vms/" + vm_name)
            d = json.loads(f.read())
            f.close()
            reader, writer = await asyncio.open_connection(
                d["devices"]["graphics"]["vnc"]["host"],
                int(d["devices"]["graphics"]["vnc"]["port"]),
            )
            producer = asyncio.create_task(vnc_sending(reader, writer))
            consumer = asyncio.create_task(vnc_receiving(reader, writer))
            await asyncio.gather(producer, consumer)
        else:
            return "VM not found", 404
    else:
        return "Unauthorized", 403


app.run(host="0.0.0.0", port=8880)
