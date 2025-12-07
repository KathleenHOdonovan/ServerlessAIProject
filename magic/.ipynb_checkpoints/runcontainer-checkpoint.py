from IPython.core.magic import (Magics, magics_class, line_cell_magic)
# from IPython.core.hooks import shutdown_hook as default_shutdown_hook
from connectContainer import CloudContainer
import time
import atexit

# STATIC VARIABLES THAT CAN BE CHANGED DEPENDING ON WHO IS USING THIS APPLICATION
service_account_file = r"C:\Users\kj2od\Documents\ServerlessAI\genial-caster-473015-f0-d2fdd5d3592d.json"
project_id = "genial-caster-473015-f0"
zone = "us-east4-c"

# Global VM instance
'''This global vm instance allows the vm to be initialized during the initilization of this magic command
so when the magic command itself is run there is limited latency'''
vm = None

@magics_class
class RunContainerMagic(Magics):

    @line_cell_magic
    def runcontainer(self, line, cell=None):
        start = time.time()
        global vm
        if vm is None:
            print("❌ VM is not initialized. Reload the extension.")
            return
        try:
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
        return f"Finished Running Command on Container"

# ---------------- EXTENSION LOAD/UNLOAD ----------------
def load_ipython_extension(ipython):
    global vm
    ipython.register_magics(RunContainerMagic)
    # 2️⃣ Register Jupyter kernel shutdown hook (works for restarts)
    # ---- PATCH IPython SHUTDOWN HOOK ----
    def custom_shutdown_hook():
        print("💀 IPython shutdown hook triggered — cleaning VM & container...")
        _cleanup()
        default_shutdown_hook()  # call the real hook afterward

    ipython.set_hook('shutdown_hook', custom_shutdown_hook)
    # --------------------------------------

    print("⏳ Initializing CloudContainer and starting/resuming VM...")
    vm = CloudContainer(
        service_account_file=service_account_file,
        project_id=project_id,
        zone=zone
    )
    vm.connect_vm()  # VM resumes here
    print("✅ VM is ready for running containers!")

    # Optional: pre-pull container image to speed up first run
    print("📦 starting container...")
    try:
        vm.start_container()  # starts container and keeps it alive
    except Exception as e:
        print(f"⚠️ Could not start container image: {e}")

    # Register automatic cleanup when notebook/kernel shuts down
    atexit.register(_cleanup)
    
    
def unload_ipython_extension(ipython):
    _cleanup()

def _cleanup():
    """Stop container and VM cleanly."""
    global vm
    if vm:
        print("🧹 Cleaning up resources...")
        try:
            vm.stop_container()
        except Exception as e:
            print(f"⚠️ Error stopping container: {e}")
        try:
            vm.stop_vm()
        except Exception as e:
            print(f"⚠️ Error stopping VM: {e}")
        vm = None
        print("✅ Cleanup complete!")
