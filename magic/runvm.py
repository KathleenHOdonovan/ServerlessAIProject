from IPython.core.magic import (Magics, magics_class, line_cell_magic)
from sshCommands import CloudVM

#STATIC VARIABLES THAT CAN BE CHANGES DEPENDING ON WHO IS USING THIS APPLICATION:

# Path to your service account JSON file
service_account_file = r"C:\Users\kj2od\Documents\ServerlessAI\genial-caster-473015-f0-d2fdd5d3592d.json"
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
                    vm.run_code(cell)
                except Exception as e:
                    print(f"❌ An error occurred while running code on the VM:\n{e}")
                finally:
                    vm.delete_vm()
                # # Execute full block of code
                #  # Execute all but the last line
                # code_lines = cell.strip().split("\n")
                # exec_lines, last_line = code_lines[:-1], code_lines[-1]
            
                # # Run the exec part (assignments, imports, etc.)
                # exec("\n".join(exec_lines), ip.user_ns)
            
                # # Evaluate the last line
                # result = eval(last_line, ip.user_ns)
            except Exception as e:
                return f"Error: {e}"
        return f"Ran on a gpu here is the result"
def load_ipython_extension(ipython):
    ipython.register_magics(RunVMMagic)