import math
import argparse
import copy
import functools
import logging
import subprocess
import sys
import time 
import os
import configparser
import socket
import common 
#from paramiko import SSHClient
#from scp import SCPClient



log = logging.getLogger(__name__)


def exec_command(cmd):
    logging.info(cmd)
    result = subprocess.run(cmd.split(), stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    for l in result.stdout.decode('utf-8').splitlines():
        logging.info(l)
    for l in result.stderr.decode('utf-8').splitlines():
        logging.info(l)
    return result.stdout.decode('utf-8').splitlines()

def run_ansible_playbook(inventory, extravars=None, playbook=None, tags=None):
    extravars = ' '.join(extravars) if extravars else ''
    if tags:
        tags = '--tags "{}"'.format(tags) 
    else:
        tags = ""
    cmd = 'ansible-playbook -v -i {} -e "{}" {} {}'.format(inventory, extravars, tags, playbook)
    print(cmd)
    os.system(cmd)

def start_remote():
    run_ansible_playbook(
        inventory='hosts', 
        playbook='ansible/install.yml')

def set_uncore_freq(conf, freq_mhz):
    freq_hex=format(freq_mhz//100, 'x')
    msr_val = "0x{}{}".format(freq_hex, freq_hex) 
    
    extravars = [
       'MSR_VALUE={}'.format(msr_val)]
    run_ansible_playbook(
       inventory='hosts', 
       extravars=extravars, 
       playbook='ansible/configure.yml')

def set_core_freq(conf, freq_mhz):
    extravars = [
       'CORE_FREQ={}MHz'.format(freq_mhz)]
    run_ansible_playbook(
       inventory='hosts', 
       extravars=extravars, 
       playbook='ansible/configure_core_freq.yml')


def run_profiler(id):
    extravars = [
        'ITERATION={}'.format(id)]
    run_ansible_playbook(
        inventory='hosts', 
        extravars=extravars,
        playbook='ansible/profiler.yml', 
        tags='run_profiler')

def kill_profiler():
    run_ansible_playbook(
        inventory='hosts', 
        playbook='ansible/profiler.yml', 
        tags='kill_profiler')

def run_remote(midtier_conf, bucket_conf):

    f = open("/users/ganton12/HDSearch/microsuite/bucket_servers_IP.txt", "w")
    #start bucket servers first and prepare IP file for midtier
    sshProcess = subprocess.Popen(['ssh',
                               '-tt',
                               'node1'],
                               stdin=subprocess.PIPE, 
                               stdout = subprocess.PIPE,
                               universal_newlines=True,
                               bufsize=0)
    sshProcess.stdin.write("sudo docker ps \n")
    sshProcess.stdin.write("logout \n")
    sshProcess.stdin.close()
    for line in sshProcess.stdout:
        if "hdsearch" in line:
            container_id=line.split(" ")[0]
            break
    
    i=0
    print("IRTAAAAAAAA sto bucket server giat den leitourga")  
    while i < len(bucket_conf.port):
        extravars = [
            'CONTAINER_ID={}'.format(container_id),
            'DATASET={}'.format(bucket_conf.dataset_filepath),
            'IP={}'.format(str(bucket_conf.IP[0])),
            'PORT={}'.format(str(bucket_conf.port[i])),
            'MODE={}'.format(bucket_conf.readmode),
            'THREADS={}'.format(bucket_conf.threads),
            'ID={}'.format(str(bucket_conf.bucket_id[i])),
            'NUM_BUCKETS={}'.format(bucket_conf.num_buckets),
            'CORES={}'.format(str(bucket_conf.cores[i]))
        ]
        run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='run_bucket')
        f.write(str(bucket_conf.IP[0]) + ":" + str(bucket_conf.port[i]) + "\n")
        i=i+1
        
    f.close()
    
    #move ip files to midtier directory
    os.system('scp /users/ganton12/HDSearch/microsuite/bucket_servers_IP.txt ganton12@node1:/users/ganton12/HDSearch/microsuite/bucket_servers_IP.txt')
    move_ip_file("/users/ganton12/HDSearch/microsuite/bucket_servers_IP.txt", container_id)
    
    #start midtier server
    extravars = [
        'CONTAINER_ID={}'.format(container_id),
        'HASH_TABLES={}'.format(midtier_conf.hash_tables),
        'KEY_LENGTH={}'.format(midtier_conf.key_length),
        'PROBE_LEVEL={}'.format(midtier_conf.probe_level),
        'BUCKET_SERVERS={}'.format(midtier_conf.bucket_servers),
        'IP_FILE_PATH={}'.format(midtier_conf.ip_file_path),
        'DATASET={}'.format(midtier_conf.dataset_filepath),
        'MODE={}'.format(midtier_conf.readmode),
        'IP={}'.format(midtier_conf.IP),
        'PORT={}'.format(midtier_conf.port),
        'NETWORK_THREADS={}'.format(midtier_conf.network_threads),
        'DISPATCH_THREADS={}'.format(midtier_conf.dispatch_threads),
        'RESPONSE_THREADS={}'.format(midtier_conf.response_threads),
        'STATS={}'.format(midtier_conf.stats),
        'CORES={}'.format(str(midtier_conf.cores))
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='run_midtier')

def move_ip_file(path, container_id):
    extravars = [
        'CONTAINER_ID={}'.format(container_id),
        'IP_FILE_PATH={}'.format(path)
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='copy_ip_file')    

def cp_midtier(container_id):
    extravars = [
        'CONTAINER_ID={}'.format(container_id),
        'MIDTIER_FILE_PATH={}'.format('/users/ganton12/HDSearch/microsuite/MicroSuite/src/HDSearch/mid_tier_service/service/mid_tier_server.cc')
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='copy_midtier')

def compile_midtier(container_id):
    extravars = [
        'CONTAINER_ID={}'.format(container_id),
        'MIDTIER_FILE_PATH={}'.format('/MicroSuite/src/HDSearch/mid_tier_service/service')
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='compile_midtier')    

def cp_client(container_id):
    extravars = [
        'CONTAINER_ID={}'.format(container_id),
        'CLIENT_FILE_PATH={}'.format('/users/ganton12/HDSearch/microsuite/MicroSuite/src/HDSearch/load_generator/load_generator_open_loop.cc')
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='copy_client')

def compile_client(container_id):
    extravars = [
        'CONTAINER_ID={}'.format(container_id),
        'CLIENT_FILE_PATH={}'.format('/MicroSuite/src/HDSearch/load_generator')
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='compile_client')    

def fix_midtier(container_id):
    #copy midtier file to container
    cp_midtier(container_id)

    #compile midtier file
    compile_midtier(container_id)

def fix_client(container_id):
    #copy midtier file to container
    cp_client(container_id)

    #compile midtier file
    compile_client(container_id)
    
def get_dataset():

    sshProcess = subprocess.Popen(['ssh',
                               '-tt',
                               'node1'],
                               stdin=subprocess.PIPE, 
                               stdout = subprocess.PIPE,
                               universal_newlines=True,
                               bufsize=0)
    sshProcess.stdin.write("sudo docker ps \n")
    sshProcess.stdin.write("logout \n")
    sshProcess.stdin.close()
    for line in sshProcess.stdout:
        if "hdsearch" in line:
            container_id=line.split(" ")[0]
            break

    extravars = [
        'CONTAINER_ID={}'.format(container_id),
    ]
    run_ansible_playbook(
            inventory='hosts', 
            extravars=extravars, 
            playbook='ansible/hdsearch.yml', 
            tags='get_dataset')    

def kill_remote():
    sshProcess = subprocess.Popen(['ssh',
                               '-tt',
                               'node1'],
                               stdin=subprocess.PIPE, 
                               stdout = subprocess.PIPE,
                               universal_newlines=True,
                               bufsize=0)
    sshProcess.stdin.write("sudo docker ps \n")
    sshProcess.stdin.write("logout \n")
    sshProcess.stdin.close()
    for line in sshProcess.stdout:
        if "hdsearch" in line:
            container_id=line.split(" ")[0]
            break
    extravars = [
        'CONTAINER_ID={}'.format(container_id)
    ]
    run_ansible_playbook(
        inventory='hosts', 
        extravars=extravars,
        playbook='ansible/hdsearch.yml', tags='kill_midtier,kill_bucket')

def host_is_reachable(host):
  return True if os.system("ping -c 1 {}".format(host)) == 0 else False

def hdsearch_node():
    config = configparser.ConfigParser(allow_no_value=True)
    config.read('hosts')
    node = list(config['bucket'].items())
    if len(node) > 1:
        raise Exception('Do not support multiple memcached nodes')
    return node[0][0]

def wait_for_remote_node(node):
    while not host_is_reachable(node):
        logging.info('Waiting for remote host {}...'.format(node))
        time.sleep(30)
        pass

def configure_hdsearch_node(conf):
    node = hdsearch_node()
    print('ssh -n {} "cd ~/HDSearch; sudo python3 configure.py -v --turbo={} --kernelconfig={} -v"'.format(node, conf['turbo'], conf['kernelconfig']))
    rc = os.system('ssh -n {} "cd ~/HDSearch; sudo python3 configure.py -v --turbo={} --kernelconfig={} -v"'.format(node, conf['turbo'], conf['kernelconfig']))
    exit_status = rc >> 8 
    if exit_status == 2:
        logging.info('Rebooting remote host {}...'.format(node))
        os.system('ssh -n {} "sudo shutdown -r now"'.format(node))
        logging.info('Waiting for remote host {}...'.format(node))
        time.sleep(30)
        while not host_is_reachable(node):
            logging.info('Waiting for remote host {}...'.format(node))
            time.sleep(30)
            pass
        os.system('ssh -n {} "cd ~/HDSearch; sudo python3 configure.py -v --turbo={} --kernelconfig={} -v"'.format(node, conf['turbo'], conf['kernelconfig']))
        if conf['ht'] == False:
        	os.system('ssh -n {} "echo "forceoff" | sudo tee /sys/devices/system/cpu/smt/control"'.format(node))
        os.system('ssh -n {} "sudo cpupower frequency-set -g performance"'.format(node))
        
        #disable nmi watchdog
        os.system('ssh -n {} "echo "0" | sudo tee /proc/sys/kernel/nmi_watchdog"'.format(node))
        
        if conf['turbo'] == False:
        	os.system('ssh -n {} "~/HDSearch/turbo-boost.sh disable"'.format(node))

def run_single_experiment(root_results_dir, name_prefix, client_conf, midtier_conf, bucket_conf, idx):
    name = name_prefix + client_conf.shortname()
    results_dir_name = "{}-{}".format(name, idx)
    results_dir_path = os.path.join(root_results_dir, results_dir_name)
    hdsearch_results_dir_path = os.path.join(results_dir_path, 'hdsearch')
    print("irtaaaaa")
    sshProcess = subprocess.Popen(['ssh',
                               '-tt',
                               'node1'],
                               stdin=subprocess.PIPE, 
                               stdout = subprocess.PIPE,
                               universal_newlines=True,
                               bufsize=0)
    sshProcess.stdin.write("sudo docker ps \n")
    sshProcess.stdin.write("logout \n")
    sshProcess.stdin.close()
    for line in sshProcess.stdout:
        if "hdsearch" in line:
            container_id=line.split(" ")[0]
            break

    # cleanup any processes left by a previous run
    kill_profiler()
    kill_remote()
    time.sleep(15)
    # prepare profiler, memcached, and mcperf agents
    fix_midtier(container_id)
    fix_client(container_id)
    run_remote(midtier_conf, bucket_conf)

    #fix profiler source code
    run_profiler(idx)
    time.sleep(120)
   
    #print("sudo docker exec {} /MicroSuite/src/HDSearch/load_generator/load_generator_open_loop {} {} {} {} {} {}:{} dummy1 dummy2 dummy3 \n".format(container_id,client_conf.dataset_filepath,client_conf.result_filepath,client_conf.knn,client_conf.warmup_time,client_conf.warmup_qps,client_conf.IP,client_conf.port))
    
    # do a warmup run
   
    #os.system('ssh node1 "sudo docker exec {} mkdir /MicroSuite/src/HDSearch/load_generator/results \n"'.format(container_id))
    #os.system('ssh node1 "sudo docker exec {} /MicroSuite/src/HDSearch/load_generator/load_generator_open_loop {} {} {} {} {} {}:{} dummy1 dummy2 dummy3 \n"'.format(container_id,client_conf.dataset_filepath,client_conf.result_filepath,client_conf.knn,client_conf.warmup_time,client_conf.warmup_qps,client_conf.IP,client_conf.port))
    
    #for line in sshProcess.stdout:
    #    print(line)

    # do the measured run
    #time.sleep(30)
    #print("sudo docker exec {} taskset -c {} /MicroSuite/src/HDSearch/load_generator/load_generator_open_loop {} {} {} {} {} {}:{} dummy1 dummy2 dummy3".format(container_id,client_conf.cores,client_conf.dataset_filepath,client_conf.result_filepath,client_conf.knn,client_conf.run_time,client_conf.hdsearch_qps,client_conf.IP,client_conf.port))
    
    exec_command("python3 ./profiler.py -n node1 start")
    os.system('ssh node1 "sudo docker exec {} taskset -c {} /MicroSuite/src/HDSearch/load_generator/load_generator_open_loop {} {} {} {} {} {}:{} dummy1 dummy2 dummy3 &> ./results_out"'.format(container_id,client_conf.cores,client_conf.dataset_filepath,client_conf.result_filepath,client_conf.knn,client_conf.run_time,client_conf.hdsearch_qps,client_conf.IP,client_conf.port))
    exec_command("python3 ./profiler.py -n node1 stop")
    exec_command("python3 ./profiler.py -n node1 report -d {}".format(hdsearch_results_dir_path))
    sshProcess = subprocess.Popen(['ssh',
                               '-tt',
                               'node1'],
                               stdin=subprocess.PIPE, 
                               stdout = subprocess.PIPE,
                               universal_newlines=True,
                               bufsize=0)
    sshProcess.stdin.write("cat /users/ganton12/results_out \n")
    sshProcess.stdin.write("logout \n")
    sshProcess.stdin.close()


    client_results_path_name = os.path.join(results_dir_path, 'hdsearch_client')
    with open(client_results_path_name, 'w') as fo:
        for l in sshProcess.stdout:
            fo.write(l+'\n')

    # cleanup
    kill_remote()
    kill_profiler()
    

def run_multiple_experiments(root_results_dir, batch_name, system_conf, client_conf, midtier_conf, bucket_conf, iter):
    configure_hdsearch_node(system_conf)
    #start container
    start_remote()
    get_dataset() 
    
    time.sleep(500)

    name_prefix = "turbo={}-kernelconfig={}-hyperthreading={}-".format(system_conf['turbo'], system_conf['kernelconfig'],system_conf['ht'])
    request_qps = [1]
    root_results_dir = os.path.join(root_results_dir, batch_name)
    set_uncore_freq(system_conf, 2000)
    exit()
    for qps in request_qps:
        instance_conf = copy.copy(client_conf)
        client_conf.set('hdsearch_qps', qps)
        #same work experiment
        #time=int(int(instance_conf.mcperf_time)*min(request_qps)/qps)
        #instance_conf.set('mcperf_time',time)
        temp_iter=iter
        iters_cycle=math.ceil(float(bucket_conf.perf_counters)/4.0)
        for it in range(iters_cycle*(iter),iters_cycle*(iter+1)):
            run_single_experiment(root_results_dir, name_prefix, instance_conf, midtier_conf, bucket_conf, it)
            time.sleep(120)

def main(argv):
    system_confs = [
##        {'turbo': True,  'kernelconfig': 'vanilla'},
##        {'turbo': False,  'kernelconfig': 'vanilla'},
#         {'turbo': False, 'kernelconfig': 'baseline', 'ht': False},
#          {'turbo': False, 'kernelconfig': 'disable_c6'},
#         {'turbo': True, 'kernelconfig': 'baseline'},
#         {'turbo': False, 'kernelconfig': 'disable_cstates'},
#         {'turbo': False, 'kernelconfig': 'disable_c6', 'ht': False},
#         {'turbo': True, 'kernelconfig': 'disable_c6'},
#          {'turbo': True, 'kernelconfig': 'disable_c1e_c6', 'ht': True},
          {'turbo': False, 'kernelconfig': 'baseline', 'ht': False},
          {'turbo': False, 'kernelconfig': 'disable_c6', 'ht': False},
          {'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': False},
          {'turbo': False, 'kernelconfig': 'disable_cstates', 'ht': False},
#          {'turbo': False, 'kernelconfig': 'baseline', 'ht': False},
#          {'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': False, 'pstate': False},
#          {'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': True},
#         {'turbo': True, 'kernelconfig': 'disable_c1e_c6'},
##         {'turbo': False, 'kernelconfig': 'quick_c1'},
##         {'turbo': True, 'kernelconfig': 'quick_c1'},
##         {'turbo': False, 'kernelconfig': 'quick_c1_disable_c6'},
##         {'turbo': True, 'kernelconfig': 'quick_c1_disable_c6'},
##         {'turbo': False, 'kernelconfig': 'quick_c1_c1e'},
##         {'turbo': True, 'kernelconfig': 'quick_c1_c1e'},
##         {'turbo': True, 'kernelconfig': 'disable_cstates'},
    ]
    client_conf = common.Configuration({
        'dataset_filepath': '/home/image_feature_vectors.dat',
        'result_filepath': './results',
        'knn': '1',
        'warmup_time': '10',
        'run_time': '120',
        'warmup_qps': '500',
        'run_qps': '1',
        'IP': '0.0.0.0',
        'port': '50054',
        'hdsearch_qps': '1',
        'cores': '1'
    })

    midtier_conf = common.Configuration({
        'hash_tables': '1',
        'key_length': '13',
        'probe_level': '1',
        'bucket_servers': '4',
        'ip_file_path': 'bucket_servers_IP.txt',
        'dataset_filepath': '/home/image_feature_vectors.dat',
        'readmode': '2',
        'IP': '0.0.0.0',
        'port': '50054',
        'network_threads': '1',
        'dispatch_threads': '1',
        'response_threads': '1',
        'stats': '0',
        'cores': '2'    #'2'
    })

    bucket_conf = common.Configuration({
        'dataset_filepath': '/home/image_feature_vectors.dat',
        'IP': ['0.0.0.0'],
        'port': ['50050', '50051', '50052', '50053'],
        'readmode': '2',
        'threads': '1',
        'bucket_id': ['0', '1', '2', '3'],
        'num_buckets': '4',
        'cores': ['3', '4', '5', '6'],
        'perf_counters': '54'
    })
   
    logging.getLogger('').setLevel(logging.INFO)
    if len(argv) < 1:
        raise Exception("Experiment name is missing")
    batch_name = argv[0]
    for iter in range(0, 1):
        for system_conf in system_confs:
            run_multiple_experiments('/users/ganton12/data', batch_name, system_conf, client_conf, midtier_conf, bucket_conf, iter)

if __name__ == '__main__':
    main(sys.argv[1:])
