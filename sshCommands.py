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

        print(f"✅ VM {self.vm_name} created successfully!")

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
        vm_ip = self.get_vm_external_ip()
        print(f"🌐 VM external IP: {vm_ip}")

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

        self.wait_for_ssh(vm_ip)

        ssh_cmd = [
            "gcloud",
            "compute",
            "ssh",
            f"serverless-user@{self.vm_name}",
            "--project",
            self.project_id,
            "--zone",
            self.zone,
            "--command",
            remote_cmd,
        ]

        try:
            result = subprocess.run(
                ssh_cmd, check=True, text=True, capture_output=True
            )
            print("----- STDOUT -----")
            print(result.stdout)
            print("----- STDERR -----")
            print(result.stderr)
        except subprocess.CalledProcessError as e:
            print("❌ Error executing remote code:")
            print(e.stdout)
            print(e.stderr)

    def delete_vm(self):
        print(f"🧹 Deleting VM {self.vm_name}...")
        instance_client = compute_v1.InstancesClient()
        op = instance_client.delete(
            project=self.project_id, zone=self.zone, instance=self.vm_name
        )
        op.result()
        print("✅ VM deleted.")
