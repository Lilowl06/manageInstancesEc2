import boto3
import os
import sys
import time

ec2 = boto3.resource('ec2', region_name="eu-central-1")
user = str(sys.argv[1])
userGroup = str(sys.argv[2])
SecurityGroupIds='sg-045de45c2834b1b04' # A changer en fonction de l'utilisateur du script

######## Function definition ########
def nameAvailable(userName) :
    unavailableUserNames = [f.split('.')[0] for f in os.listdir("/tmp/") if (os.path.isfile(f"/tmp/{f}") and (".pem" in f))]
    return not (userName in unavailableUserNames)

def create_user(userName):
    iam = boto3.client("iam")
    iam.create_user(UserName=userName)

def add_user_to_group(userName, group_name):
    iam = boto3.client('iam') # IAM low level client object
    iam.add_user_to_group(
        UserName=userName,
        GroupName=group_name
    )

def create_key_pair(userName):
    key_pair = ec2.create_key_pair(KeyName=userName)
    private_key = key_pair.key_material
    # change permission to file with 400 permissions
    with os.fdopen(os.open(f"/tmp/{userName}.pem", os.O_WRONLY | os.O_CREAT, 0o400), "w+") as handle:
        handle.write(private_key)

def create_instance(keyName):
    res=ec2.create_instances(
        ImageId="ami-0a49b025fffbbdac6",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        SecurityGroupIds=[SecurityGroupIds],
        KeyName=keyName,
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': f'dev-{user}'
                    }
                ]
            }
        ]
    )
    return res

######## Apply function ########
if not nameAvailable(user) : 
    print("User name is taken") 
    exit()

create_user(user)
print(f"***** User {user} has been created *****")

add_user_to_group(user, userGroup)
print(f"***** User {user} has been put into group {userGroup} *****")

create_key_pair(user)
print("***** Key pair create *****")

instances=create_instance(user)
print("***** Instance EC2 create *****")

# inventory.txt creation file
instanceId=str(instances[0].id)
print("***** Wait instance is running *****")
instances[0].wait_until_running()
instances[0].reload()
print("***** Instance EC2 running *****")
instanceIp=str(instances[0].public_ip_address)
instancePublicDns=str(instances[0].public_dns_name)

line = f"{instanceId} ansible_host={instanceIp} ansible_port=22 ansible_ssh_private_key_file=/tmp/{user}.pem\n"
with open('inventory.txt', 'a') as f:
    f.write(line)
with open('tmp.txt', 'w') as f:
    f.write("[dev]\n"+line)
print("***** Instance EC2 added to Inventory.txt *****")

with open('ConnectionId.txt', 'a') as f:
    f.write(f"***** {user} *****\n Connection à l'instance {user} :\n La clé privé se situe dans /tmp/{user}.pem\n La commande de connection à l'instance est ssh est : -i /tmp/{user}.pem ubuntu@{instancePublicDns}\n")

# Sleep for 
time.sleep(30)

# Automatic add fingerprint in known_hosts
os.system(f"ssh-keyscan -H {instanceIp} >> ~/.ssh/known_hosts")
print("***** hohst add to known_hosts *****")

# Run ansible playbook
os.system(f'ansible-playbook -i tmp.txt ./playbook.yml --user ubuntu')


