#THIS SCRIPT SPINS UP A NEW VM AND BUCKET RUNS THE SCRIPT THE USER UPLOADS, THEN RETURNS THE RESULTS
import uuid
import time
from google.cloud import storage
from googleapiclient import discovery
from google.oauth2 import service_account
from google.cloud import compute_v1
import os


class CloudVM:
    def __init__(self, service_account_file, project_id, zone="us-central1-a", machine_type="e2-medium", image="debian-11", file="myscript.py"):
        print("intitializing input")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\kj2od\Documents\ServerlessAI\genial-caster-473015-f0-d2fdd5d3592d.json"
        self.key_file = service_account_file
        self.project_id = project_id
        self.zone = zone
        self.machine_type = f"zones/{zone}/machineTypes/{machine_type}"
        self.source_image = f"projects/debian-cloud/global/images/family/{image}"
        self.credentials = service_account.Credentials.from_service_account_file(service_account_file)
        self.compute = discovery.build("compute", "v1", credentials=self.credentials)
        self.bucket_name = None
        self.vm_name = f"vm-{uuid.uuid4().hex[:8]}"
        print("creating vm")
        #CREATE BUCKET
        print("create bucket")
        client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
        self.bucket_name = f"temp-bucket-{uuid.uuid4().hex[:8]}"
        bucket = client.bucket(self.bucket_name)
        bucket.storage_class = "STANDARD"
        bucket.location = "US"
        bucket = client.create_bucket(bucket)
        print(f"Created temporary bucket: {self.bucket_name}")
        #list all buckets 
        buckets = client.list_buckets()
        print("Buckets in project:")
        for bucket in buckets:
            print(f"- {bucket.name}")

        #UPLOAD FILE
        print("upload file")
        # client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
        # bucket = client.bucket(self.bucket_name)
        blob = bucket.blob(file)
        blob.upload_from_filename(file)
        print(f"Uploaded myscript.py to gs://{self.bucket_name}/myscript.py")
        #list all blobs
        blobs = bucket.list_blobs()
        print(f"Files in bucket '{self.bucket_name}':")
        for blob in blobs:
            print(f"- {blob.name}")
            # echo "Updating packages and installing Python..."
            # apt-get update && apt-get install -y python3 python3-pip
            # echo "Installing Google Cloud SDK..."
            # curl https://sdk.cloud.google.com | bash
        startup_script = startup_script = f"""#!/bin/bash
                                            echo "Starting VM startup script..."
                                            
                                            
                                            
                                            echo "Downloading script from GCS..."
                                            gsutil cp gs://{self.bucket_name}/myscript.py /home/myscript.py
                                            
                                            echo "Running Python script..."
                                            python3 /home/myscript.py > /home/results.txt
                                            
                                            echo "Uploading results to GCS..."
                                            gsutil cp /home/results.txt gs://{self.bucket_name}/results.txt
                                            
                                            echo "Script finished. Shutting down VM..."
                                            sleep 30
                                            shutdown -h now
                                            """
        

        
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
                    name="global/networks/default",  # Or your custom network
                    access_configs=[compute_v1.AccessConfig(name="External NAT", type="ONE_TO_ONE_NAT")],
                )
            ],
            service_accounts=[
                compute_v1.ServiceAccount(
                    email="serverless-gpu-access@genial-caster-473015-f0.iam.gserviceaccount.com",
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            ],
            # Add other configurations like metadata, service accounts, etc., as needed
           metadata=compute_v1.Metadata(
                items=[
                    {"key": "startup-script", "value": startup_script}
                ]
            )
        )
        print(f"VM {self.vm_name} is being created...")
        instance_client = compute_v1.InstancesClient()
        request = compute_v1.InsertInstanceRequest(
            project=self.project_id,
            zone=self.zone,
            instance_resource=instance_config,
        )
        print(f"Creating instance {self.vm_name} in {self.zone}...")
        operation = instance_client.insert(request=request)
        operation.result()  # Wait for the operation to complete
        print(f"DONE")
        blobs = bucket.list_blobs()
        print(f"Files in bucket '{self.bucket_name}':")
        
        blob = bucket.blob("results.txt")
        while not blob.exists():
                print("still waiting")
                time.sleep(5)
        results = blob.download_as_text()
        print("RESULTS:")
        print(results)
        #DELETE TEMP VM AND BUCKET
        time.sleep(5)
        
        # self.delete_vm()
        self.compute.instances().delete(project=self.project_id, zone=self.zone, instance=self.vm_name).execute()
        print(f"VM {self.vm_name} deletion requested.")
        # self.delete_bucket()
        for blob in bucket.list_blobs():
            blob.delete()
        bucket.delete()
        print(f"Deleted bucket: {self.bucket_name}")
        print("All done. VM and bucket cleaned up.")
        # for blob in blobs:
        #     blob_download = bucket.blob(blob.name)
        #     print(f"- {blob.name}")
        #     results = blob_download.download_as_text()
        #     print("downloaded?")
        #     print(results)

    # # -------------------------
    # # Temporary bucket helpers
    # # -------------------------
    # def create_temp_bucket(self):
    #     print("create bucket")
    #     client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
    #     self.bucket_name = f"temp-bucket-{uuid.uuid4().hex[:8]}"
    #     bucket = client.bucket(self.bucket_name)
    #     bucket.storage_class = "STANDARD"
    #     bucket.location = "US"
    #     bucket = client.create_bucket(bucket)
    #     print(f"Created temporary bucket: {self.bucket_name}")
    #     return self.bucket_name

    # def delete_bucket(self):
    #     if not self.bucket_name:
    #         return
    #     client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
    #     bucket = client.bucket(self.bucket_name)
    #     # Delete all objects
    #     for blob in bucket.list_blobs():
    #         blob.delete()
    #     bucket.delete()
    #     print(f"Deleted bucket: {self.bucket_name}")

    # def upload_file(self, local_file, remote_file):
    #     print("upload file")
    #     client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
    #     bucket = client.bucket(self.bucket_name)
    #     blob = bucket.blob(remote_file)
    #     blob.upload_from_filename(local_file)
    #     print(f"Uploaded {local_file} to gs://{self.bucket_name}/{remote_file}")

    # def download_file(self, remote_file, local_file):
    #     print("download")
    #     client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
    #     bucket = client.bucket(self.bucket_name)
    #     blob = bucket.blob(remote_file)
    #     blob.download_to_filename(local_file)
    #     print(f"Downloaded gs://{self.bucket_name}/{remote_file} to {local_file}")

    # # -------------------------
    # # VM helpers
    # # -------------------------
    # # def create_vm(self, startup_script=None):
    # #     print("trying to create vm")
    # #     if startup_script is None:
    # #         # Default: download 'myscript.py', run, upload 'results.txt', shutdown
    # #         startup_script = f"""#!/bin/bash
    # #             apt-get update && apt-get install -y python3 python3-pip
    # #             curl https://sdk.cloud.google.com | bash
    # #             gcloud auth activate-service-account --key-file=/tmp/key.json
    # #             gsutil cp gs://{self.bucket_name}/myscript.py /home/myscript.py
    # #             python3 /home/myscript.py > /home/results.txt
    # #             gsutil cp /home/results.txt gs://{self.bucket_name}/results.txt
    # #             shutdown -h now
    # #             """
    # #     config = {
    # #         "name": self.vm_name,
    # #         "machineType": self.machine_type,
    # #         "disks": [{
    # #             "boot": True,
    # #             "autoDelete": True,
    # #             "initializeParams": {"sourceImage": self.source_image}
    # #         }],
    # #         "networkInterfaces": [{
    # #             "network": "global/networks/default",
    # #             "accessConfigs": [{"type": "ONE_TO_ONE_NAT", "name": "External NAT"}]
    # #         }],
    # #         "metadata": {"items": [{"key": "startup-script", "value": startup_script}]}
    # #     }
    # #     operation = self.compute.instances().insert(project=self.project_id, zone=self.zone, body=config).execute()
    # #     print(f"VM {self.vm_name} is being created...")
    # #     return operation

    # def delete_vm(self):
    #     op = self.compute.instances().delete(project=self.project_id, zone=self.zone, instance=self.vm_name).execute()
    #     print(f"VM {self.vm_name} deletion requested.")
    #     return op

    # # -------------------------
    # # High-level workflow
    # # -------------------------
    # def run_script(self, local_script, output_file="results.txt"):
    #     try:
    #         # 1. Create bucket
    #         self.create_temp_bucket()
    #         #list all buckets 
    #         buckets = client.list_buckets()
    #         print("Buckets in project:")
    #         for bucket in buckets:
    #             print(f"- {bucket.name}")
                
    #         # 2. Upload script
    #         self.upload_file(local_script, "myscript.py")
    #         #see all files in bucket
    #         bucket = client.bucket(self.bucket_name)
    #         blobs = bucket.list_blobs()
    #         print(f"Files in bucket '{bucket_name}':")
    #         for blob in blobs:
    #             print(f"- {blob.name}")
                
    #         # 3. Create VM with startup script
    #         # self.create_vm()
    #         print("VM is running your script... wait a few minutes for it to complete.")
    #         # Wait for results (simple polling)
    #         client = storage.Client.from_service_account_json(self.key_file, project=self.project_id)
    #         bucket = client.bucket(self.bucket_name)
    #         blob = bucket.blob("results.txt")
    #         while not blob.exists():
    #             print("still waiting")
    #             time.sleep(5)
    #         # 4. Download results
    #         self.download_file("results.txt", output_file)
    #     finally:
    #         # Cleanup
    #         self.delete_vm()
    #         self.delete_bucket()
    #         print("All done. VM and bucket cleaned up.")
