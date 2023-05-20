import sys
import config
from hashlib import sha256
import json
args = sys.argv
user = "root"
if len(args) > 2:
    user = args[2]
if len(args) > 1:
    f = open(config.datadir + "/users/" + user)
    d = json.loads(f.read())
    f.close()
    d["password"] = sha256(args[1].encode('utf-8')).hexdigest()
    f = open(config.datadir + "/users/" + user, "w")
    f.write(json.dumps(d))
    f.close()
else:
    print("Usage: python3 setpassword.py password [user=root]")