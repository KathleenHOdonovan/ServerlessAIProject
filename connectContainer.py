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

class CloudContainer:
    def __init__(self, service_account_file, project_id, zone="us-central1-a", machine_type="e2-medium", image="debian-11"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_file
        self.project_id = project_id
        self.zone = zone
        self.vm_name = "container-vm"
        self.credentials = service_account.Credentials.from_service_account_file(service_account_file)
        self.compute = discovery.build("compute", "v1", credentials=self.credentials)
        self.gcloud_path = shutil.which("gcloud")
        if not self.gcloud_path:
            raise RuntimeError(
                "❌ Google Cloud SDK (`gcloud`) not found.\n"
                "Please install it from https://cloud.google.com/sdk/docs/install\n"
                "and make sure it is added to your system PATH."
            )
        else:
            print("goooogle")
            print(self.gcloud_path)

    def connect_vm(self):
        print(f"🚀 Connecting to VM {self.vm_name} in {self.zone}...")
        
        subprocess.run([
            self.gcloud_path, "compute", "instances", "start", self.vm_name,
            "--zone", self.zone,
            "--project", self.project_id
        ], check=True)
        print(f"✅ VM {self.vm_name} started!")
        
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
    #image variable can be added to method signature to be used to replace the hardcoded image
    def pull_container(self):
        print("pulling container...")
        # subprocess_command = (
        #     f"{self.gcloud_path} compute ssh {self.vm_name} "
        #     f"--zone {self.zone} --project {self.project_id} "
        #     f"--command 'docker pull nvcr.io/nvidia/pytorch:23.08-py3'"
        # )
        # subprocess.run(subprocess_command, shell=True, check=True)
        
        output = subprocess.run(
                [
                    self.gcloud_path,
                    "compute", "ssh", self.vm_name,
                    "--project", self.project_id,
                    "--zone", self.zone,
                    "--command", "docker pull nvcr.io/nvidia/pytorch:23.08-py3"
                ],
                capture_output=True,  # capture both stdout and stderr
                text=True,
                check=True
            )
        print("------output-----")
        print(output)
        print("✅ Container image is ready!")

    def run_code(self, code: str, packages=None):
        """Run arbitrary Python code on the VM and print output live."""
        print("🧠 Executing code remotely...")
        
        # Encode the full Python code to base64 to safely preserve newlines and quotes
        encoded_code = base64.b64encode(code.encode()).decode("utf-8")
    
        # Remote command: decode + execute the code inside Python
        remote_cmd = (
            f'python3 -c "import base64; exec(base64.b64decode(\'{encoded_code}\').decode())"'
        )
        
        
        print("packages")
        print(packages)
        container_image = "nvcr.io/nvidia/pytorch:23.08-py3" #THIS IS HARDCODED BUT CAN BE AND SHOULD BE CHANGED LATER
        
        #Handle Installing User Defined Packages on the VM
        if packages and isinstance(packages, str):
            packages = [pkg.strip() for pkg in packages.split(" ")]
            
            install_cmd = (
                # "sudo apt-get update -y && "
                # "sudo apt-get install -y python3-pip && "
                "pip3 install -q " + " ".join(packages)
            )
            # container_cmd = f'docker run --rm --gpus all {container_image} bash -c "pip install -q {pkgs_str} && {remote_cmd}"'
            remote_cmd = f"{install_cmd} && {remote_cmd}"
            
         #Run command on container   
        container_cmd = f'DOCKER_TMPDIR=/mnt/stateful_partition/docker-tmp docker run --rm {container_image} {remote_cmd}'
        #--runtime=nvidia --gpus all
        self.wait_for_ssh(self.get_vm_external_ip())
        print(f"🚀 Running command on container {self.vm_name} ...")

        try:
            result = subprocess.run(
                [
                    self.gcloud_path,
                    "compute", "ssh", self.vm_name,
                    "--project", self.project_id,
                    "--zone", self.zone,
                    "--command", container_cmd
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
       
        
    
    def stop_vm(self):
        print(f"🛑 Stopping VM {self.vm_name}...")
        subprocess.run([
            self.gcloud_path, "compute", "instances", "stop", self.vm_name,
            "--zone", self.zone,
            "--project", self.project_id
        ], check=True)
        print(f"✅ VM {self.vm_name} stopped!")