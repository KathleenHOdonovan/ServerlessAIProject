from IPython.core.magic import (Magics, magics_class, line_cell_magic)
from sshCommands import CloudVM

#STATIC VARIABLES THAT CAN BE CHANGES DEPENDING ON WHO IS USING THIS APPLICATION:

# Path to your service account JSON file
service_account_file = "/Users/genial-caster-473015-f0-55ca72882d9e.json"
# Your GCP project ID
project_id = "genial-caster-473015-f0"
# Zone of execution
zone = "us-east4-b"

@magics_class
class RunVMMagic(Magics):

    @line_cell_magic
    def runvm(self, line, cell=None):
        #Start up VM
        vm = CloudVM(
            service_account_file=service_account_file,
            project_id=project_id,
            zone=zone
        )
        
        ip = get_ipython()
        
        vm.create_vm()
        
        if cell is None:
            try:
                # Evaluate in the user’s namespace
                ip = get_ipython()
                # result = eval(line, ip.user_ns)
                try:
                    vm.run_code(line)
                except Exception as e:
                    print(f"❌ An error occurred while running code on the VM:\n{e}")
                finally:
                    vm.delete_vm()
            except Exception as e:
                return f"Error: {e}"
        else:
            try:
                
                try:
                    #parse line code to see if any packages are needed to be installed
                    vm.run_code(cell, line)
                except Exception as e:
                    print(f"❌ An error occurred while running code on the VM:\n{e}")
                finally:
                    vm.delete_vm()
            except Exception as e:
                return f"Error: {e}"
        return f"Finished Running Command on GPU VM"
def load_ipython_extension(ipython):
    ipython.register_magics(RunVMMagic)