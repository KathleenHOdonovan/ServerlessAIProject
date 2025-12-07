import os
import uuid
import shutil
import subprocess
import time
import socket
import base64
import tempfile
import paramiko
from google.oauth2 import service_account
from googleapiclient import discovery
from google.cloud import compute_v1

class CloudVM:
    def __init__(
        self,
        service_account_file,
        project_id,
        zone="us-central1-a",
        machine_type="e2-medium",
        image="debian-11",
        gpu_type=None,
        gpu_count=0,
    ):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_file
        self.project_id = project_id
        self.zone = zone
        self.machine_type = f"zones/{zone}/machineTypes/{machine_type}"
        self.source_image = f"projects/debian-cloud/global/images/family/{image}"
        self.credentials = service_account.Credentials.from_service_account_file(
            service_account_file
        )
        self.compute = discovery.build("compute", "v1", credentials=self.credentials)
        self.vm_name = f"vm-{uuid.uuid4().hex[:8]}"
        self.gpu_type = gpu_type
        self.gpu_count = gpu_count
        self.gcloud_path = shutil.which("gcloud")
        
        #Persistant SSH
        self.ssh_client = None 
        self.ssh_private_key_path = None 
        self.ssh_username = "serverless-user"

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
                    access_configs=[
                        compute_v1.AccessConfig(
                            name="External NAT",
                            type="ONE_TO_ONE_NAT",
                        )
                    ],
                )
            ],
            service_accounts=[
                compute_v1.ServiceAccount(
                    email="serverless-gpu-access@genial-caster-473015-f0.iam.gserviceaccount.com",
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            ],
        )

        if self.gpu_type and self.gpu_count > 0:
            instance_config.guest_accelerators = [
                compute_v1.AcceleratorConfig(
                    accelerator_type=(
                        f"projects/{self.project_id}/zones/{self.zone}/acceleratorTypes/{self.gpu_type}"
                    ),
                    accelerator_count=self.gpu_count,
                )
            ]
            instance_config.scheduling = compute_v1.Scheduling(
                on_host_maintenance="TERMINATE"
            )

        op = instance_client.insert(
            project=self.project_id,
            zone=self.zone,
            instance_resource=instance_config,
        )
        op.result()
        print("wait for ssh")
        self.wait_for_ssh(self.get_vm_external_ip())
        print("Setup ssh")
        self.setup_ssh()

        print(f"✅ VM {self.vm_name} created successfully!")
        
    def setup_ssh(self):
        """Generate an SSH key and add it to the VM metadata, then connect via Paramiko."""
        vm_ip = self.get_vm_external_ip()
        print("🔑 Setting up SSH access...")
    
        # Generate OpenSSH key pair
        private_key_path = os.path.join(tempfile.gettempdir(), f"temp_ssh_key_{uuid.uuid4().hex}")
        public_key_path = private_key_path + ".pub"
    
        # Generate key pair
        os.system(f'ssh-keygen -t rsa -b 2048 -f "{private_key_path}" -N "" -q')
    
        # Check that the public key exists
        if not os.path.exists(public_key_path):
            raise RuntimeError(f"Failed to generate public key: {public_key_path} not found")
        print("reading public key")
    
        # Read the public key in OpenSSH format
        with open(public_key_path, "r") as f:
            public_key_str = f"{self.ssh_username}:{f.read().strip()}"
        print("done with key gen")
    
        # Add public key to VM metadata 
        instance_client = compute_v1.InstancesClient()
        instance = instance_client.get(project=self.project_id, zone=self.zone, instance=self.vm_name)
        items = instance.metadata.items or []
        items.append(compute_v1.Items(key="ssh-keys", value=public_key_str))
        metadata = compute_v1.Metadata(items=items, fingerprint=instance.metadata.fingerprint)
        instance_client.set_metadata(project=self.project_id, zone=self.zone, instance=self.vm_name, metadata_resource=metadata)
    
        # Assign the private key path so Paramiko can use it
        self.ssh_private_key_path = private_key_path
    
        # Connect via Paramiko
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
        retry_count = 0
        while retry_count < 10:
            try:
                print(self.ssh_private_key_path)
                self.ssh_client.connect(vm_ip, username=self.ssh_username, key_filename=self.ssh_private_key_path)
                print("✅ Persistent SSH connected!")
                return  # success
            except Exception as e:
                print(f"⚠ SSH not ready yet: {e}. Retrying...")
                time.sleep(5)
                retry_count += 1
    
        raise RuntimeError("Failed to establish SSH connection to VM.")


    def wait_for_ssh_key(vm_ip, username, key_path, timeout=120):
        print("got into wait for ssh key")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        start = time.time()
        while time.time() - start < timeout:
            try:
                client.connect(vm_ip, username=username, key_filename=key_path, timeout=5)
                client.close()
                return True
            except Exception:
                time.sleep(5)
        return False
    def wait_for_ssh(self, vm_ip):
        port = 22
        timeout = 300
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
        instance = instance_client.get(
            project=self.project_id, zone=self.zone, instance=self.vm_name
        )
        for nic in instance.network_interfaces:
            for access_config in nic.access_configs:
                if access_config.type_ == "ONE_TO_ONE_NAT":
                    return access_config.nat_i_p
        raise RuntimeError("No external IP found for the VM.")

    def run_code(self, code, packages=None):
        """Send code to the persistent SSH session and capture stdout/stderr."""
        if not self.ssh_client: 
            self.setup_ssh()

        encoded_code = base64.b64encode(code.encode()).decode()
        remote_cmd = (
            f'python3 -c "import base64; '
            f'exec(base64.b64decode(\'{encoded_code}\').decode())"'
        )

        # Package installation
        if packages and isinstance(packages, str):
            packages = [p.strip() for p in packages.split(" ")]
            install_cmd = (
                "sudo apt-get update -y && "
                "sudo apt-get install -y python3-pip && "
                "pip3 install -q " + " ".join(packages)
            )
            remote_cmd = f"{install_cmd} && {remote_cmd}"

        # self.wait_for_ssh(vm_ip)

        # print("before command")

        # ssh_cmd = [
        #     self.gcloud_path,
        #     "compute",
        #     "ssh",
        #     self.vm_name,
        #     # f"serverless-user@{self.vm_name}",
        #     "--project",
        #     self.project_id,
        #     "--zone",
        #     self.zone,
        #     "--command",
        #     remote_cmd,
        #     "--quiet",
        #     "--strict-host-key-checking=no",
        # ]
        stdin, stdout, stderr = self.ssh_client.exec_command(remote_cmd) 
        out = stdout.read().decode() 
        err = stderr.read().decode() 
        print(out)
        print(err)

        # try:
        #     result = subprocess.run(
        #         ssh_cmd, check=True, text=True, capture_output=True
        #     )
        #     print("----- STDOUT -----")
        #     print(result.stdout)
        #     print("----- STDERR -----")
        #     print(result.stderr)
        # except subprocess.CalledProcessError as e:
        #     print("❌ Error executing remote code:")
        #     print(e.stdout)
        #     print(e.stderr)
    
    def close_master_ssh(self):
        """Close the master SSH session."""
        if not self.master_started:
            return

        print("🛑 Closing master SSH session...")
        subprocess.run([
            self.gcloud_path,
            "compute",
            "ssh",
            self.vm_name,
            "--project", self.project_id,
            "--zone", self.zone,
            "--ssh-flag=-O", "exit",
            "--ssh-flag=-o", "StrictHostKeyChecking=no",
            "--ssh-flag=-o", "UserKnownHostsFile=/dev/null",
            "--quiet"
        ], check=True)
        self.master_started = False
        print("✅ Master SSH session closed.")
            
    def resume_vm(self):
        print(f"🚀 Resuming VM {self.vm_name} in {self.zone}...")
        
        subprocess.run([
            self.gcloud_path, "compute", "instances", "start", self.vm_name,
            "--zone", self.zone,
            "--project", self.project_id
        ], check=True)
        print(f"✅ VM {self.vm_name} started!")
    def stop_vm(self):
        print(f"🛑 Pausing VM {self.vm_name}...")
        subprocess.run([
            self.gcloud_path, "compute", "instances", "stop", self.vm_name,
            "--zone", self.zone,
            "--project", self.project_id
        ], check=True)
        print(f"✅ VM {self.vm_name} paused!")
    def delete_vm(self):
        print(f"🧹 Deleting VM {self.vm_name}...")
        instance_client = compute_v1.InstancesClient()
        op = instance_client.delete(
            project=self.project_id, zone=self.zone, instance=self.vm_name
        )
        op.result()
        print("✅ VM deleted.")
