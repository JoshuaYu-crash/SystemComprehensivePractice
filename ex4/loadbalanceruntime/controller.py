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

def writeHashRange(p4info_helper, ingress_sw, egress_sw,
                        match_fields, action_params):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_group",
        match_fields={
            "hdr.ipv4.dstAddr": match_fields
        },
        action_name="MyIngress.set_ecmp_select",
        action_params=action_params
    )
    ingress_sw.WriteTableEntry(table_entry)

def writeNextHop(p4info_helper, ingress_sw, egress_sw,
                        match_fields, action_params):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.ecmp_nhop",
        match_fields={
            "meta.ecmp_select": match_fields
        },
        action_name="MyIngress.set_nhop",
        action_params=action_params
    )
    ingress_sw.WriteTableEntry(table_entry)

def writeDMAC(p4info_helper, ingress_sw, egress_sw,
                        match_fields, action_params):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyEgress.send_frame",
        match_fields={
            "standard_metadata.egress_port": match_fields
        },
        action_name="MyEgress.rewrite_mac",
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
        writeHashRange(p4info_helper, s1, s1, 
        ["10.0.0.1", 32], {"ecmp_base": 0, "ecmp_count": 2})
        writeNextHop(p4info_helper, s1, s1,
        0, {"nhop_dmac": "00:00:00:00:01:02", "nhop_ipv4": "10.0.2.2", "port": 2})
        writeNextHop(p4info_helper, s1, s1,
        1, {"nhop_dmac": "00:00:00:00:01:03", "nhop_ipv4": "10.0.3.3", "port": 3})
        writeDMAC(p4info_helper, s1, s1,
        2, {"smac": "00:00:00:01:02:00"})
        writeDMAC(p4info_helper, s1, s1,
        3, {"smac": "00:00:00:01:03:00"})
        
        # s2 流规则下发
        writeHashRange(p4info_helper, s2, s2, 
        ["10.0.2.2", 32], {"ecmp_base": 0, "ecmp_count": 1})
        writeNextHop(p4info_helper, s2, s2,
        0, {"nhop_dmac": "08:00:00:00:02:02", "nhop_ipv4": "10.0.2.2", "port": 1})
        writeDMAC(p4info_helper, s2, s2,
        1, {"smac": "00:00:00:02:01:00"})
        
        # s3 流规则下发
        writeHashRange(p4info_helper, s3, s3, 
        ["10.0.3.3", 32], {"ecmp_base": 0, "ecmp_count": 1})
        writeNextHop(p4info_helper, s3, s3,
        0, {"nhop_dmac": "08:00:00:00:03:03", "nhop_ipv4": "10.0.3.3", "port": 1})
        writeDMAC(p4info_helper, s3, s3,
        1, {"smac": "00:00:00:03:01:00"})
        


    except KeyboardInterrupt:
        print(" Shutting down.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/load_balance.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/load_balance.json')
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