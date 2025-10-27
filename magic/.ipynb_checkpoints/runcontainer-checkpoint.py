from IPython.core.magic import (Magics, magics_class, line_cell_magic)
from connectContainer import CloudContainer
import time
#STATIC VARIABLES THAT CAN BE CHANGES DEPENDING ON WHO IS USING THIS APPLICATION:

# Path to your service account JSON file
service_account_file = r"C:\Users\kj2od\Documents\ServerlessAI\genial-caster-473015-f0-d2fdd5d3592d.json"
# Your GCP project ID
project_id = "genial-caster-473015-f0"
# Zone of execution
zone = "us-east4-c"

# Global VM instance
'''This global vm instance allows the vm to be initialized during the initilization of this magic command
so when the magic command itself is run there is limited latency'''
vm = None

@magics_class
class RunContainerMagic(Magics):

    @line_cell_magic
    def runcontainer(self, line, cell=None):
        global vm
        if vm is None:
            print("❌ VM is not initialized. Reload the extension.")
            return
        try:
            start = time.time()
            if cell is None:
                # single-line command
                vm.run_code(line)
            else:
                # multi-line cell
                vm.run_code(cell)
            end = time.time()
            print(f"⏱ Total execution time: {end - start:.2f} seconds")
        except Exception as e:
            print(f"❌ An error occurred while running code on the VM:\n{e}")
        # #Start up VM
        # vm = CloudContainer(
        #     service_account_file=service_account_file,
        #     project_id=project_id,
        #     zone=zone
        # )
        
        # ip = get_ipython()
        
        # vm.connect_vm()
        
        # if cell is None:
        #     try:
        #         # Evaluate in the user’s namespace
        #         ip = get_ipython()
        #         # result = eval(line, ip.user_ns)
        #         try:
        #             vm.run_code(line)
        #         except Exception as e:
        #             print(f"❌ An error occurred while running code on the VM:\n{e}")
        #         finally:
        #             vm.stop_vm()
        #     except Exception as e:
        #         return f"Error: {e}"
        # else:
        #     try:
                
        #         try:
        #             #parse line code to see if any packages are needed to be installed
        #             start= time.time()
        #             vm.run_code(cell)
        #             end= time.time()
        #             print(f"Total time: {end - start:.2f} seconds")
            #     except Exception as e:
            #         print(f"❌ An error occurred while running code on the VM:\n{e}")
            #     finally:
            #         vm.stop_vm()
            # except Exception as e:
            #     return f"Error: {e}"
        return f"Finished Running Command on Container"
# ---------------- EXTENSION LOAD/UNLOAD ----------------
def load_ipython_extension(ipython):
    global vm
    ipython.register_magics(RunContainerMagic)

    print("⏳ Initializing CloudContainer and starting/resuming VM...")
    vm = CloudContainer(
        service_account_file=service_account_file,
        project_id=project_id,
        zone=zone
    )
    vm.connect_vm()  # VM resumes here
    print("✅ VM is ready for running containers!")

    # Optional: pre-pull container image to speed up first run
    print("📦 Pre-pulling container image for faster runs...")
    try:
        vm.pull_container()
    except Exception as e:
        print(f"⚠️ Could not pre-pull container image: {e}")


def unload_ipython_extension(ipython):
    global vm
    if vm:
        print("🛑 Stopping VM...")
        vm.stop_vm()
        vm = None
        print("✅ VM stopped")