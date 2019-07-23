import os
import json
import datetime
import getpass
import paramiko
import sys

DEBUG = True

def log_text(text):
    if(DEBUG):
        print(str(datetime.datetime.now()) + ' : ' + str(text))

def cert_bytes(cert_file_name):
    """
    Parses a pem certificate file into raw bytes and appends null character.
    """
    with open(cert_file_name, "rb") as pem:
        chars = []
        for c in pem.read():
            chars.append(ord(c))
        # mbedtls demands null-terminated certs
        chars.append(0)
        return chars


def quote_bytes(quote_file_name):
    """
    Parses a binary quote file into raw bytes.
    """
    with open(quote_file_name, "rb") as quote:
        chars = []
        for c in quote.read():
            chars.append(ord(c))
        return chars

def reset_workspace():
    os.system("sudo pkill cchost")
    os.system("rm -rf tx0* gov* *.pem quote* nodes.json startNetwork.json joinNetwork.json ledger parsed_* sealed_*")

def reset_remote_workspace(c):
    c.exec_command("sudo pkill cchost")
    c.exec_command("cd ~/CCF/build && rm -rf tx0* gov* *.pem quote* nodes.json startNetwork.json joinNetwork.json ledger parsed_* sealed_*")

def generate_members_certs(nb_members_certs, nb_users_certs):
    for x in range(0, nb_members_certs):
        os.system("./genesisgenerator cert --name=./member" + str(x))
    for x in range(0, nb_users_certs):
        os.system("./genesisgenerator cert --name=./user" + str(x))

def generate_members_certs_on_remote(c, nb_members_certs, nb_users_certs):
    for x in range(0, nb_members_certs):
        c.exec_command("cd ~/CCF/build && ./genesisgenerator cert --name=member" + str(x))
    for x in range(0, nb_users_certs):
        c.exec_command("cd ~/CCF/build && ./genesisgenerator cert --name=user" + str(x))

def generate_nodes_json(info):
    with open('./nodes.json', 'w') as outfile:
        json.dump(
        [
            {
                "host": info["node_address_1"],
                "raftport": info["raft_port"],
                "pubhost": info["node_address_1"],
                "tlsport": info["tls_port"],
                "cert": cert_bytes("./0.pem"),
                "quote": quote_bytes("./quote0.bin"),
                "status": 0,
            },
            {
                "host": info["node_address_2"],
                "raftport": info["raft_port"],
                "pubhost": info["node_address_2"],
                "tlsport": info["tls_port"],
                "cert": cert_bytes("./1.pem"),
                "quote": quote_bytes("./quote1.bin"),
                "status": 0,
            },  
        ]
        , outfile)

def start_remote_node(info, c):
    reset_remote_workspace(c)
    c.exec_command("cd ./CCF/build && ./cchost " 
        "--enclave-file=./libloggingenc.so.signed "
        "--raft-election-timeout-ms=100000 "
        "--raft-host=" + info["node_address_2"] + " "
        "--raft-port=" + info["raft_port"] + " "
        "--tls-host=" + info["node_address_2"] + " "
        "--tls-pubhost=" + info["node_address_2"] + " "
        "--tls-port=" + info["tls_port"] + " "
        "--ledger-file=./ledger "
        "--node-cert-file=./1.pem "
        "--enclave-type=debug "
        "--log-level=info " 
        "--quote-file=./quote1.bin &")

def start_node(info):
    os.system("./cchost " 
        "--enclave-file=./libloggingenc.so.signed "
        "--raft-election-timeout-ms=100000 "
        "--raft-host=" + info["node_address_1"] + " "
        "--raft-port=" + info["raft_port"] + " "
        "--tls-host=" + info["node_address_1"] + " "
        "--tls-pubhost=" + info["node_address_1"] + " "
        "--tls-port=" + info["tls_port"] + " "
        "--ledger-file=./ledger "
        "--node-cert-file=./0.pem "
        "--enclave-type=debug "
        "--log-level=info " 
        "--quote-file=./quote0.bin & ")

def retrieve_remote_node_certs(c):
    try:
        sftp = c.open_sftp()
        sftp.get("./CCF/build/quote1.bin", "./quote1.bin")
        sftp.get("./CCF/build/1.pem","./1.pem")
        return True
    except:
        print("Error: failed to retrieve remote node certs. Check node health, then retry.")
        return False

def send_network_info_to_remote_node(c):
    try:
        sftp = c.open_sftp()
        sftp.put("./networkcert.pem", "./CCF/build/networkcert.pem")
        return True
    except:
        print("Error: failed to send network cert. Check node health, then retry.")
        return False

def connect_remote_node(info):
    try:
        c = paramiko.SSHClient()
        c.load_system_host_keys()
        c.set_missing_host_key_policy(paramiko.WarningPolicy)
        c.connect(info["node_address_2"], port=22, username=info["node_user_2"], password=info["node_pwd_2"])
        return c
    except:
        print("Error: unable to connect to remote node. Check node health and credentials, then retry.")
        return False

def get_light_node_info():
    node_address_2 = str(raw_input("Remote node IP address: "))
    node_user_2 = str(raw_input("Remote node IP username: "))
    node_pwd_2 = getpass.getpass()

    return {
        "node_address_2": node_address_2,
        "node_user_2": node_user_2,
        "node_pwd_2": node_pwd_2,
    }

def get_node_info():
    node_address_1 = str(raw_input("Local node IP address: "))
    node_address_2 = str(raw_input("Remote node IP address: "))
    node_user_2 = str(raw_input("Remote node IP username: "))
    node_pwd_2 = getpass.getpass()
    raft_port = str(raw_input("Raft port: "))
    tls_port = str(raw_input("TLS port: "))

    return {
        "node_address_1": node_address_1,
        "node_address_2": node_address_2,
        "node_user_2": node_user_2,
        "node_pwd_2": node_pwd_2,
        "raft_port": raft_port,
        "tls_port": tls_port,
    }

def reset_workspaces():
    info = get_light_node_info()
    log_text("Cleaning older files and resetting server on local node ...")
    reset_workspace() 
    log_text("Done.")

    log_text("Connecting to remote node ...")
    c = connect_remote_node(info)
    log_text("Done.")

    log_text("Cleaning older files and resetting server on remote node ...")
    reset_remote_workspace(c)
    log_text("Done.")

    c.close()

def run(args=None):
    info = get_node_info()
    log_text("Cleaning older files and resetting server")
    reset_workspace()

    log_text("Starting local node ...")
    start_node(info)

    log_text("Connecting to remote node ...")
    c = connect_remote_node(info)

    if(c):
        log_text("Starting remote node ...")
        start_remote_node(info, c)

        log_text("Waiting for nodes to start ...")
        os.system("sleep 8")

        log_text("Retrieving remote node certs ...")
        res = retrieve_remote_node_certs(c)

        if(res):
            log_text("Generating nodes.json file ...")
            generate_nodes_json(info)
            log_text("Done.")

            log_text("Generating members and users certs on local node ...")
            generate_members_certs(1,1)
            log_text("Done.")

            log_text("Generating members and users certs on remote node ...")
            generate_members_certs_on_remote(c,1,1)
            log_text("Done.")

            log_text("Generating genesis transaction ...")
            os.system("./genesisgenerator tx --gov-script=../src/runtime_config/gov.lua")

            log_text("Starting blockchain ...")
            os.system("./client --host=" + info["node_address_1"] + " --port=" + info["tls_port"] + " --ca=./0.pem startnetwork --req=@startNetwork.json")

            log_text("Sending network cert to remote node ...")
            send_network_info_to_remote_node(c)
            log_text("Done.")

            log_text("Connecting remote node to blockchain ...")
            c.exec_command("cd ~/CCF/build && ./genesisgenerator joinrpc --network-cert=./networkcert.pem --host=" + info["node_address_1"] + " --port=" + info["tls_port"])
            #print("cd ~/CCF/build && ./genesisgenerator joinrpc --network-cert=./1.pem --host=" + info["node_address_1"] + " --port=" + info["tls_port"])
            c.exec_command("cd ~/CCF/build && ./client --host=" + info["node_address_2"] + " --port=" + info["tls_port"] + " --ca=./1.pem joinnetwork --req=joinNetwork.json")
            #print("./client --host=" + info["node_address_2"] + " --port=" + info["tls_port"] + " --ca=./1.pem joinnetwork --req=joinNetwork.json")
            log_text("Done.")
            
            log_text("Network online, setup complete.")
        c.close()
    else:
        os.system("sudo pkill cchost")
        os.system("cd ~/CCF/build  && rm -rf tx0* gov* *.pem quote* nodes.json startNetwork.json joinNetwork.json 0 parsed_* sealed_*")

if __name__ == "__main__":
    if sys.argv[1] == "run":
        run()
    elif sys.argv[1] == "clean":
        reset_workspaces()
    else:
        print("How to use the script : ")
        print("-> python network.py run : launch the sample network")
        print("-> python network.py clean : clean all files generated from previous tests, on VMs used")