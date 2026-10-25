#!/usr/bin/env python3
"""Terminate the GPU instance and clean up key pair + security group.

Reads $KIROCREW_SCRATCH/launch.json (written by launch.py), or pass --iid/--region.
Verified path — see docs/RUNBOOK.md. ALWAYS run this when done to stop billing.

Usage: python scripts/teardown.py
       python scripts/teardown.py --iid i-xxxx --region ap-northeast-1
"""
import boto3, os, json, argparse

KEY = "oss-image-lab-key"
SG = "oss-image-lab-sg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iid")
    ap.add_argument("--region")
    a = ap.parse_args()
    scratch = os.environ.get("KIROCREW_SCRATCH", "/tmp")
    if a.iid and a.region:
        iid, region = a.iid, a.region
    else:
        info = json.load(open(os.path.join(scratch, "launch.json")))
        iid, region = info["iid"], info["region"]

    ec2 = boto3.client("ec2", region_name=region)
    try:
        st = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]["State"]["Name"]
        print("state before:", st)
    except Exception as e:
        print("describe:", str(e)[:80])
    ec2.terminate_instances(InstanceIds=[iid])
    print("terminating", iid)
    ec2.get_waiter("instance_terminated").wait(InstanceIds=[iid])
    print("TERMINATED")
    try:
        ec2.delete_key_pair(KeyName=KEY); print("key deleted")
    except Exception as e:
        print("key:", str(e)[:60])
    try:
        sg = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [SG]}])["SecurityGroups"][0]["GroupId"]
        ec2.delete_security_group(GroupId=sg); print("sg deleted", sg)
    except Exception as e:
        print("sg:", str(e)[:80])
    # sanity: no lingering project instances
    r = ec2.describe_instances(Filters=[{"Name": "tag:project", "Values": ["oss-image-models-lab"]},
        {"Name": "instance-state-name", "Values": ["running", "pending", "stopping", "stopped"]}])
    left = [i["InstanceId"] for res in r["Reservations"] for i in res["Instances"]]
    print("remaining project instances:", left or "NONE")


if __name__ == "__main__":
    main()
