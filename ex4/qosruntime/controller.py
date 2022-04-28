#!/usr/bin/env python3
import argparse
import os
import sys
from time import sleep

import grpc

# Import P4Runtime lib from parent utils dir
# Probably there's a better way of doing this.
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '../../utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections

def writeForwardRules(p4info_helper, ingress_sw, egress_sw,
                        match_fields, action_params):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ipv4_lpm",
        match_fields={
            "hdr.ipv4.dstAddr": match_fields
        },
        action_name="MyIngress.ipv4_forward",
        action_params=action_params
    )
    ingress_sw.WriteTableEntry(table_entry)

def main(p4info_file_path, bmv2_file_path):
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    try:
        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='logs/s1-p4runtime-requests.txt')
        s2 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s2',
            address='127.0.0.1:50052',
            device_id=1,
            proto_dump_file='logs/s2-p4runtime-requests.txt')
        s3 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s3',
            address='127.0.0.1:50053',
            device_id=2,
            proto_dump_file='logs/s3-p4runtime-requests.txt')

        s1.MasterArbitrationUpdate()
        s2.MasterArbitrationUpdate()
        s3.MasterArbitrationUpdate()

        s1.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s1")
        s2.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s2")
        s3.SetForwardingPipelineConfig(p4info=p4info_helper.p4info,
                                       bmv2_json_file_path=bmv2_file_path)
        print("Installed P4 Program using SetForwardingPipelineConfig on s3")
        # s1 流规则下发
        writeForwardRules(p4info_helper, s1, s1, 
        ["10.0.1.1", 32], {"dstAddr": "08:00:00:00:01:01", "port": 2})
        writeForwardRules(p4info_helper, s1, s1, 
        ["10.0.1.11", 32], {"dstAddr": "08:00:00:00:01:11", "port": 1})
        writeForwardRules(p4info_helper, s1, s1, 
        ["10.0.2.0", 24], {"dstAddr": "08:00:00:00:02:00", "port": 3})
        writeForwardRules(p4info_helper, s1, s1, 
        ["10.0.3.0", 24], {"dstAddr": "08:00:00:00:03:00", "port": 4})
        
        # s2 流规则下发
        writeForwardRules(p4info_helper, s2, s2, 
        ["10.0.2.2", 32], {"dstAddr": "08:00:00:00:02:02", "port": 2})
        writeForwardRules(p4info_helper, s2, s2, 
        ["10.0.2.22", 32], {"dstAddr": "08:00:00:00:02:22", "port": 1})
        writeForwardRules(p4info_helper, s2, s2, 
        ["10.0.1.0", 24], {"dstAddr": "08:00:00:00:01:00", "port": 3})
        writeForwardRules(p4info_helper, s2, s2, 
        ["10.0.3.0", 24], {"dstAddr": "08:00:00:00:03:00", "port": 4})
        
        # s3 流规则下发
        writeForwardRules(p4info_helper, s3, s3, 
        ["10.0.3.3", 32], {"dstAddr": "08:00:00:00:01:01", "port": 1})
        writeForwardRules(p4info_helper, s3, s3, 
        ["10.0.1.0", 32], {"dstAddr": "08:00:00:00:01:11", "port": 2})
        writeForwardRules(p4info_helper, s3, s3, 
        ["10.0.2.0", 24], {"dstAddr": "08:00:00:00:02:00", "port": 3})



    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/qos.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/qos.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info file not found: %s\nHave you run 'make'?" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON file not found: %s\nHave you run 'make'?" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)