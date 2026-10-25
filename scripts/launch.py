#!/usr/bin/env python3
"""Launch a verified g6e GPU instance for image-gen, via boto3 (instance role).

Verified path — see docs/RUNBOOK.md. Uses import-key-pair (idempotent) so SSH
works immediately; falls back across AZs/regions when capacity is short.
Writes launch info to $KIROCREW_SCRATCH/launch.json. NO AWS keys needed — uses
the host instance role. Run from the host that has the role.

Usage: python scripts/launch.py            # defaults from RUNBOOK
"""
import boto3, os, json, subprocess, sys

REGION_PLAN = {  # region -> AZs to try, in order (east/eu often lack g6e capacity)
    "ap-northeast-1": ["ap-northeast-1a", "ap-northeast-1c", "ap-northeast-1d"],
    "us-west-2": ["us-west-2a", "us-west-2b", "us-west-2c", "us-west-2d"],
    "us-east-1": ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d"],
}
INSTANCE_TYPE = "g6e.xlarge"
KEY = "oss-image-lab-key"
SG = "oss-image-lab-sg"
AMI_SSM = "/aws/service/deeplearning/ami/x86_64/oss-nvidia-driver-gpu-pytorch-2.7-ubuntu-22.04/latest/ami-id"
SCRATCH = os.environ.get("KIROCREW_SCRATCH", "/tmp")
KEYFILE = os.path.join(SCRATCH, "eic_key")


def ensure_local_key():
    if not os.path.exists(KEYFILE):
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", KEYFILE, "-q"], check=True)
    return open(KEYFILE + ".pub").read().strip()


def setup_region(ec2, pub):
    try:
        ec2.import_key_pair(KeyName=KEY, PublicKeyMaterial=pub.encode())
    except Exception:
        pass  # already imported
    vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    try:
        sg = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [SG]},
             {"Name": "vpc-id", "Values": [vpc]}])["SecurityGroups"][0]["GroupId"]
    except (IndexError, Exception):
        sg = ec2.create_security_group(GroupName=SG, Description="oss image lab", VpcId=vpc)["GroupId"]
        ec2.authorize_security_group_ingress(GroupId=sg, IpPermissions=[
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}])
    return sg


def main():
    pub = ensure_local_key()
    for region, azs in REGION_PLAN.items():
        ec2 = boto3.client("ec2", region_name=region)
        ssm = boto3.client("ssm", region_name=region)
        try:
            ami = ssm.get_parameter(Name=AMI_SSM)["Parameter"]["Value"]
        except Exception as e:
            print(f"{region}: no AMI ({str(e)[:40]}), skip"); continue
        sg = setup_region(ec2, pub)
        for az in azs:
            try:
                r = ec2.run_instances(ImageId=ami, InstanceType=INSTANCE_TYPE, KeyName=KEY,
                    SecurityGroupIds=[sg], MinCount=1, MaxCount=1, Placement={"AvailabilityZone": az},
                    BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 250, "VolumeType": "gp3", "DeleteOnTermination": True}}],
                    TagSpecifications=[{"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "oss-image-lab"}, {"Key": "project", "Value": "oss-image-models-lab"}]}])
                iid = r["Instances"][0]["InstanceId"]
                ec2.get_waiter("instance_running").wait(InstanceIds=[iid])
                d = ec2.describe_instances(InstanceIds=[iid])["Reservations"][0]["Instances"][0]
                info = {"region": region, "az": az, "iid": iid, "ip": d.get("PublicIpAddress"),
                        "ami": ami, "sg": sg, "keyfile": KEYFILE}
                json.dump(info, open(os.path.join(SCRATCH, "launch.json"), "w"), indent=2)
                print(json.dumps(info))
                print(f"\nSSH: ssh -o StrictHostKeyChecking=no -i {KEYFILE} ubuntu@{info['ip']}")
                return
            except Exception as e:
                print(f"{az}: {type(e).__name__}: {str(e)[:50]}")
    sys.exit("no capacity in any region/AZ tried")


if __name__ == "__main__":
    main()
