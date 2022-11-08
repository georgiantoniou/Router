import ast
import copy
import csv
import os
import re
import statistics
import sys

Pipeline_Width = 4
MS_Switches_Cost = 2

def parse_topdown_results(system_conf,results_topdown1,results_topdown2,results_topdown3,qps):
    raw = []
    row = []
    
    instance_name = system_conf_fullname(system_conf) + shortname(qps)
    row.append(instance_name)
    for key,val in results_topdown1.items():
        row.append(key + " " + str(val))
    for key,val in results_topdown2.items():
        row.append(key + " " + str(val))
    #for key,val in results_topdown3.items():
    #    row.append(key + " " + str(val))
    raw.append(row)
    return raw

def get_topdown_level1(stats):
    
    results_topdown1 = {}

    #metrics

    results_topdown1['Retired_Slots'] = stats['UOPS_RETIRED_RETIRE_SLOTS']
    results_topdown1['Recovery_Cycles'] = stats['INT_MISC_RECOVERY_CYCLES_ANY']
    results_topdown1['CLKS'] = stats['CPU_CLK_UNHALTED_THREAD'] 
    results_topdown1['CORE_CLKS'] = results_topdown1['CLKS']
    results_topdown1['SLOTS'] = Pipeline_Width*results_topdown1['CORE_CLKS']
    results_topdown1['IPC'] =  stats['INST_RETIRED_ANY'] / results_topdown1['CLKS']
    results_topdown1['CPI'] = 1 / results_topdown1['IPC'] 

    #categories

    results_topdown1['Frontend_Bound'] = stats['IDQ_UOPS_NOT_DELIVERED_CORE'] / results_topdown1['SLOTS']
    results_topdown1['Bad_Speculation'] = ( stats['UOPS_ISSUED_ANY'] - results_topdown1['Retired_Slots'] + Pipeline_Width * results_topdown1['Recovery_Cycles']) / results_topdown1['SLOTS']
    results_topdown1['Backend_Bound'] = 1 - results_topdown1['Frontend_Bound'] - ( stats['UOPS_ISSUED_ANY'] + Pipeline_Width * results_topdown1['Recovery_Cycles'] ) / results_topdown1['SLOTS']
    results_topdown1['Retiring'] =  results_topdown1['Retired_Slots'] / results_topdown1['SLOTS']
    
    return results_topdown1

def get_topdown_level2(stats,results_topdown1):
    
    results_topdown2={}

    #metrics
    #print(results_topdown1)
    results_topdown2['Frontend_Latency_Cycles'] = min((stats['CPU_CLK_UNHALTED_THREAD']),(stats['IDQ_UOPS_NOT_DELIVERED_CYCLES_0_UOPS_DELIV_CORE']))
    results_topdown2['Few_Uops_Executed_Threshold'] = stats['EXE_ACTIVITY_1_PORTS_UTIL'] + results_topdown1['Retiring'] * stats['EXE_ACTIVITY_2_PORTS_UTIL']
    results_topdown2['Backend_Bound_Cycles'] = stats['CYCLE_ACTIVITY_STALLS_TOTAL'] + results_topdown2['Few_Uops_Executed_Threshold'] + stats['EXE_ACTIVITY_BOUND_ON_STORES']
    results_topdown2['Mispred_Clears_Fraction'] = stats['BR_MISP_RETIRED_ALL_BRANCHES'] / ( stats['BR_MISP_RETIRED_ALL_BRANCHES'] + stats['MACHINE_CLEARS_COUNT'])    
    results_topdown2['Memory_Bound_Fraction'] = (stats['CYCLE_ACTIVITY_STALLS_MEM_ANY'] + stats['EXE_ACTIVITY_BOUND_ON_STORES']) / results_topdown2['Backend_Bound_Cycles']

    #Categories

    results_topdown2['Fetch_Latency'] = Pipeline_Width * results_topdown2['Frontend_Latency_Cycles'] / results_topdown1['SLOTS']
    results_topdown2['Fetch_Bandwidth'] = results_topdown1['Frontend_Bound'] - results_topdown2['Fetch_Latency']

    results_topdown2['Branch_Mispredicts'] = results_topdown2['Mispred_Clears_Fraction'] * results_topdown1['Bad_Speculation']
    results_topdown2['Machine_Clears'] = results_topdown1['Bad_Speculation'] - results_topdown2['Branch_Mispredicts']

    results_topdown2['Memory_Bound'] = results_topdown2['Memory_Bound_Fraction'] * results_topdown1['Backend_Bound']
    results_topdown2['Core_Bound'] = results_topdown1['Backend_Bound'] - results_topdown2['Memory_Bound']

    results_topdown2['Heavy_Operations'] = ( results_topdown1['Retired_Slots'] + stats['UOPS_RETIRED_MACRO_FUSED'] - stats['INST_RETIRED_ANY']) / results_topdown1['SLOTS']
   
    results_topdown2['Light_Operations'] = results_topdown1['Retiring'] - results_topdown2['Heavy_Operations']


    return results_topdown2

def get_topdown_level3(stats,results_topdown1,results_topdown2):  
    
    results_topdown3={}
    #metrics
    
    results_topdown3['LOAD_L1_MISS_NET'] = stats['MEM_LOAD_RETIRED_L1_MISS']
    results_topdown3['FBHit_per_L1Miss'] = stats['MEM_LOAD_RETIRED_FB_HIT'] / results_topdown3['LOAD_L1_MISS_NET']
    results_topdown3['LOAD_L2_HIT'] = stats['MEM_LOAD_RETIRED_L2_HIT'] * ( 1 + results_topdown3['FBHit_per_L1Miss']  )
    results_topdown3['L2_Bound_Ratio'] = ( stats['CYCLE_ACTIVITY_STALLS_L1D_MISS'] - stats['CYCLE_ACTIVITY_STALLS_L2_MISS'] ) / results_topdown1['CLKS']
    
    #Categories
    
    results_topdown3['L2_Bound'] = (results_topdown3['LOAD_L2_HIT'] / ( results_topdown3['LOAD_L2_HIT'] + stats['L1D_PEND_MISS_FB_FULL_c1'])) * results_topdown3['L2_Bound_Ratio']
    
    #metrics

    results_topdown3['MEM_Bound_Ratio'] = stats['CYCLE_ACTIVITY_STALLS_L3_MISS'] / results_topdown1['CLKS'] + results_topdown3['L2_Bound_Ratio'] - results_topdown3['L2_Bound']    
    results_topdown3['Few_Uops_Executed_Threshold'] = stats['EXE_ACTIVITY_1_PORTS_UTIL'] + results_topdown1['Retiring'] * stats['EXE_ACTIVITY_2_PORTS_UTIL'] 
    results_topdown3['Core_Bound_Cycles'] = stats['EXE_ACTIVITY_EXE_BOUND_0_PORTS'] + results_topdown3['Few_Uops_Executed_Threshold']
    
    #Light_Ops_Sum: FP_Arith + Memory_Operations + Fused_Instructions + Non_Fused_Branches + Nop_Instructions
    results_topdown3['Retire_Fraction'] = results_topdown1['Retired_Slots'] / stats['UOPS_ISSUED_ANY']

    #Categories

    results_topdown3['ICache_Misses'] = ( stats['ICACHE_16B_IFDATA_STALL'] + 2 * stats['icache_16b_ifdata_stall_c1_e1'] ) / results_topdown1['SLOTS']
    results_topdown3['ITLB_Misses'] = stats['ICACHE_64B_IFTAG_STALL'] / results_topdown1['CLKS']
    #results_topdown3['Branch_Resteers'] = stats['INT_MISC_CLEAR_RESTEER_CYCLES'] / results_topdown1['CLKS'] + 
    #Branch_Resteers : INT_MISC.CLEAR_RESTEER_CYCLES / CLKS + Unknown_Branches
    results_topdown3['DSB_Switches'] = stats['DSB2MITE_SWITCHES_PENALTY_CYCLES'] / results_topdown1['CLKS']
    results_topdown3['LCP'] = stats['ILD_STALL_LCP'] /  results_topdown1['CLKS']
    results_topdown3['MS_Switches'] = MS_Switches_Cost * stats['IDQ_MS_SWITCHES'] / results_topdown1['CLKS']
    results_topdown3['MITE'] = ( stats['IDQ_ALL_MITE_CYCLES_ANY_UOPS'] - stats['IDQ_ALL_MITE_CYCLES_4_UOPS'] ) / results_topdown1['CORE_CLKS'] / 2
    results_topdown3['DSB'] = ( stats['IDQ_ALL_DSB_CYCLES_ANY_UOPS'] - stats['IDQ_ALL_DSB_CYCLES_4_UOPS'] ) / results_topdown1['CORE_CLKS'] / 2
    
    results_topdown3['L1_Bound'] = max( (stats['CYCLE_ACTIVITY_STALLS_MEM_ANY'] - stats['CYCLE_ACTIVITY_STALLS_L1D_MISS']) / results_topdown1['CLKS'] , 0)
    results_topdown3['L3_Bound'] = (stats['CYCLE_ACTIVITY_STALLS_L2_MISS'] - stats['CYCLE_ACTIVITY_STALLS_L3_MISS'] ) / results_topdown1['CLKS']
    results_topdown3['DRAM_Bound'] = results_topdown3['MEM_Bound_Ratio']
    results_topdown3['Store_Bound'] = stats['EXE_ACTIVITY_BOUND_ON_STORES'] / results_topdown1['CLKS']
    results_topdown3['Divider'] = stats['ARITH_DIVIDER_ACTIVE'] / results_topdown1['CLKS']
    if stats['ARITH_DIVIDER_ACTIVE'] < (stats['CYCLE_ACTIVITY_STALLS_TOTAL'] - stats['CYCLE_ACTIVITY_STALLS_MEM_ANY']):
        results_topdown3['Ports_Utilization'] = results_topdown3['Core_Bound_Cycles'] / results_topdown1['CLKS']
    else:
        results_topdown3['Ports_Utilization'] = results_topdown3['Few_Uops_Executed_Threshold'] / results_topdown1['CLKS']

    
    #FP_Arith: X87_Use + FP_Scalar + FP_Vector
    results_topdown3['Memory_Operations'] = results_topdown2['Light_Operations'] * stats['MEM_INST_RETIRED_ANY'] / stats['INST_RETIRED_ANY']
    results_topdown3['Fused_Instructions'] = results_topdown2['Light_Operations'] * (stats['UOPS_RETIRED_MACRO_FUSED'] / results_topdown1['Retired_Slots'])
    results_topdown3['Non_Fused_Branches'] = results_topdown2['Light_Operations'] * (stats['BR_INST_RETIRED_ALL_BRANCHES'] - stats['UOPS_RETIRED_MACRO_FUSED']) / results_topdown1['Retired_Slots']
    results_topdown3['Nop_Instructions'] = results_topdown2['Light_Operations'] * stats['INST_RETIRED_NOP'] / results_topdown1['Retired_Slots']
    #results_topdown3['Other_Light_Ops'] = 
    #Other_Light_Ops: max( 0 , Light_Operations - #Light_Ops_Sum )
    results_topdown3['Microcode_Sequencer'] = results_topdown3['Retire_Fraction'] * stats['IDQ_MS_UOPS'] / results_topdown1['SLOTS']
    results_topdown3['Few_Uops_Instructions'] = results_topdown2['Heavy_Operations'] - results_topdown3['Microcode_Sequencer']

    #print(results_topdown3['MS_Switches'])
    return results_topdown3
    
def get_topdown_analysis(stats,system_conf,qps_list):
    results_topdown1={}
    results_topdown2={}
    results_topdown3={}
    raw = []
    for qps in qps_list:
        instance_name = system_conf_fullname(system_conf) + shortname(qps)
        print(instance_name)
        

        all_stat = {}
        for stat in stats[instance_name]:
            for key,val in stat.items():
                all_stat[key] = []
        for stat in stats[instance_name]:
            for key,val in stat.items():
                for element in val:
                    all_stat[key].append(element[1])

        for key,val in all_stat.items():
            all_stat[key] = [i for i in all_stat[key] if int(i) != 0] 
            all_stat[key] = statistics.mean(all_stat[key])       
        print(all_stat['cycles_u'])
        print(all_stat['instructions_u'])
        print(all_stat['cycles_k'])
        print(all_stat['instructions_k'])
        results_topdown1 = get_topdown_level1(all_stat)
        results_topdown2 = get_topdown_level2(all_stat,results_topdown1)
        #results_topdown3 = get_topdown_level3(all_stat,results_topdown1,results_topdown2)

        raw = parse_topdown_results(system_conf,results_topdown1,results_topdown2,results_topdown3,qps)        
    
    return raw

def write_csv(filename, rows):
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(row)  

def write_csv_all(stats, system_confs, qps_list):
    for system_conf in system_confs:
        
        raw = get_topdown_analysis(stats, system_conf, qps_list)
        write_csv(system_conf_fullname(system_conf) + 'topdownanalysis' + '.csv', raw)

def shortname(qps=None):
    return 'qps={}'.format(qps)

def system_conf_fullname(system_conf):
    l = [
        'turbo={}'.format(system_conf['turbo']),
        'kernelconfig={}'.format(system_conf['kernelconfig']),
        'hyperthreading={}'.format(system_conf['ht']),
    ]
    if 'freq' in system_conf:
        l.append('freq={}'.format(system_conf['freq']))
    return '-'.join(l) + '-'

      
def derive_datatype(datastr):
    try:
        return type(ast.literal_eval(datastr))
    except:
        return type("")

def read_timeseries_perf(filepath):
    header = None
    timeseries = None
    
    with open(filepath, 'r') as f:
        
        header = f.readline().strip().replace('.','_')
        header = header.replace(' ','_')
        header = header.replace(':','_')
        timeseries = []
        data = f.readline().strip().split(',')
        
        datatype = derive_datatype(data[1])
        f.seek(0)
        for l in f.readlines()[1:]:
            data = l.strip().split(',')
            timestamp = int(data[0])
            value = datatype(data[1])
            timeseries.append((timestamp, value))
    return (header, timeseries)        

def add_metric_to_dict(stats_dict, metric_name, metric_value):
    head = metric_name.split('.')[0]
    tail = metric_name.split('.')[1:]
    if tail:
        stats_dict = stats_dict.setdefault(head, {})
        add_metric_to_dict(stats_dict, '.'.join(tail), metric_value)
    else:
        stats_dict[head] = metric_value

def parse_perf_stats(stats_dir):
    stats = {}
    prog = re.compile('(.*)\.(.*)\.(.*)')
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if not m or not "CPU" in f:
            if not "package-0" in f and not "package-1" in f and not "dram" in f:
                stats_file = os.path.join(stats_dir, f)
                (metric_name, timeseries) = read_timeseries_perf(stats_file)
                add_metric_to_dict(stats, metric_name, timeseries)
    return stats


def parse_single_instance_stats(stats_dir):
    stats = {}
    server_stats_dir = os.path.join(stats_dir, 'memcached')
    server_perf_stats = parse_perf_stats(server_stats_dir)
    stats = {**server_perf_stats}
    return stats


def parse_multiple_instances_stats(stats_dir, pattern='.*'):
    stats = {}
    for f in os.listdir(stats_dir):
        instance_dir = os.path.join(stats_dir, f)
        instance_name = f[:f.rfind('-')]
        stats.setdefault(instance_name, []).append(parse_single_instance_stats(instance_dir))
    return stats


def main(argv):
    stats_root_dir = argv[1]
    stats = parse_multiple_instances_stats(stats_root_dir)
    all_system_confs = [
       #{'turbo': False, 'kernelconfig': 'baseline', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_c6', 'ht': False},
       #{'turbo': False, 'kernelconfig': 'disable_c1e_c6', 'ht': False},
       {'turbo': False, 'kernelconfig': 'disable_cstates', 'ht': False},
    ]

    system_confs = all_system_confs
   
    qps_list = [1500]

    write_csv_all(stats, system_confs, qps_list)
    

if __name__ == '__main__':
    main(sys.argv)
