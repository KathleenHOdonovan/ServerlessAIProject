import os
import uuid
import shutil
import subprocess
import time
import socket
import base64
from google.oauth2 import service_account
from googleapiclient import discovery
from google.cloud import compute_v1

class CloudVM:
    def __init__(self, service_account_file, project_id, zone="us-central1-a", machine_type="e2-medium", image="debian-11"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_file
        self.project_id = project_id
        self.zone = zone
        self.machine_type = f"zones/{zone}/machineTypes/{machine_type}"
        self.source_image = f"projects/debian-cloud/global/images/family/{image}"
        self.credentials = service_account.Credentials.from_service_account_file(service_account_file)
        self.compute = discovery.build("compute", "v1", credentials=self.credentials)
        self.vm_name = f"vm-{uuid.uuid4().hex[:8]}"

    def create_vm(self):
        print(f"🚀 Creating VM {self.vm_name} in {self.zone}...")
        instance_client = compute_v1.InstancesClient()

        instance_config = compute_v1.Instance(
            name=self.vm_name,
            machine_type=self.machine_type,
            disks=[
                compute_v1.AttachedDisk(
                    initialize_params=compute_v1.AttachedDiskInitializeParams(
                        source_image=self.source_image,
                        disk_size_gb=20,
                    ),
                    auto_delete=True,
                    boot=True,
                )
            ],
            network_interfaces=[
                compute_v1.NetworkInterface(
                    name="global/networks/default",
                    access_configs=[compute_v1.AccessConfig(name="External NAT", type="ONE_TO_ONE_NAT")],
                )
            ],
            service_accounts=[
                compute_v1.ServiceAccount(
                    email="serverless-gpu-access@genial-caster-473015-f0.iam.gserviceaccount.com",
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            ],
        )

        request = compute_v1.InsertInstanceRequest(
            project=self.project_id,
            zone=self.zone,
            instance_resource=instance_config,
        )

        op = instance_client.insert(request=request)
        op.result()
        print(f"✅ VM {self.vm_name} created successfully!")
    def wait_for_ssh(self, vm_ip):
        port=22
        timeout=300
        start = time.time()
        while True:
            try:
                with socket.create_connection((vm_ip, port), timeout=5):
                    print("✅ VM SSH is ready!")
                    return
            except (OSError, ConnectionRefusedError):
                if time.time() - start > timeout:
                    raise TimeoutError("VM SSH never became available.")
                print("⏳ Waiting for VM SSH...")
                time.sleep(5)
    def get_vm_external_ip(self):
        instance_client = compute_v1.InstancesClient()
        instance = instance_client.get(project=self.project_id, zone=self.zone, instance=self.vm_name)
        
        # Most VMs have at least one network interface
        nic = instance.network_interfaces[0]
        
        # External IP is in access_configs
        if nic.access_configs:
            external_ip = nic.access_configs[0].nat_i_p
            return external_ip
        else:
            return None
    def run_code(self, code: str, packages=None):
        """Run arbitrary Python code on the VM and print output live."""
        print("🧠 Executing code remotely...")
        gcloud_path = shutil.which("gcloud")
        if not gcloud_path:
            raise RuntimeError(
                "❌ Google Cloud SDK (`gcloud`) not found.\n"
                "Please install it from https://cloud.google.com/sdk/docs/install\n"
                "and make sure it is added to your system PATH."
            )
        # Encode the full Python code to base64 to safely preserve newlines and quotes
        encoded_code = base64.b64encode(code.encode()).decode("utf-8")
    
        # Remote command: decode + execute the code inside Python
        remote_cmd = (
            f'python3 -c "import base64; exec(base64.b64decode(\'{encoded_code}\').decode())"'
        )
        
        print("packages")
        print(packages)
        #Handle Installing User Defined Packages on the VM
        if packages and isinstance(packages, str):
            packages = [pkg.strip() for pkg in packages.split(" ")]
            
            install_cmd = (
                "sudo apt-get update -y && "
                "sudo apt-get install -y python3-pip && "
                "pip3 install -q " + " ".join(packages)
            )
            remote_cmd = f"{install_cmd} && {remote_cmd}"

        self.wait_for_ssh(self.get_vm_external_ip())
        print(f"🚀 Running command on VM {self.vm_name} ...")

        try:
            result = subprocess.run(
                [
                    gcloud_path,
                    "compute", "ssh", self.vm_name,
                    "--project", self.project_id,
                    "--zone", self.zone,
                    "--command", remote_cmd
                ],
                capture_output=True,  # capture both stdout and stderr
                text=True,
                check=True
            )
    
            print("✅ Command executed successfully!")
            print("----- STDOUT -----")
            print(result.stdout)
            print("------------------")
    
        except subprocess.CalledProcessError as e:
            print("❌ An error occurred while running code on the VM:")
            print("----- STDOUT -----")
            print(e.stdout)
            print("----- STDERR -----")
            print(e.stderr)
            print("------------------")
       
        
    
    def delete_vm(self):
        print(f"🧹 Deleting VM {self.vm_name}...")
        instance_client = compute_v1.InstancesClient()
        delete_op = instance_client.delete(project=self.project_id, zone=self.zone, instance=self.vm_name)
        delete_op.result()
        print("✅ VM deleted.")
