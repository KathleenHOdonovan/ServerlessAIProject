from IPython.core.magic import (Magics, magics_class, line_cell_magic)
# from IPython.core.hooks import shutdown_hook as default_shutdown_hook
from connectContainer import CloudContainer
import time
import atexit

from google.cloud import compute_v1

import ipywidgets as widgets
from IPython.display import display, clear_output

from sshCommands import CloudVM
import os
import io
import contextlib
import traceback


# STATIC VARIABLES THAT CAN BE CHANGED DEPENDING ON WHO IS USING THIS APPLICATION
service_account_file = r"C:\Users\kj2od\Documents\ServerlessAI\genial-caster-473015-f0-d2fdd5d3592d.json"
project_id = "genial-caster-473015-f0"
zone = "us-east4-c"

# Global VM instance
'''This global vm instance allows the vm to be initialized during the initilization of this magic command
so when the magic command itself is run there is limited latency'''
vm = None
packages = ""
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
                vm.run_code(cell,"")
            end = time.time()
            print(f"⏱ Total execution time: {end - start:.2f} seconds")
        except Exception as e:
            print(f"❌ An error occurred while running code on the VM:\n{e}")
        return f"Finished Running Command on Container"

#------------------GUI FUNCTIONS--------------------------

gpu_type_limits = {}
    
# 1. Basic Config
service_account_text = widgets.Text(
    description="Service JSON",
    placeholder="Path to your service account file",
    layout=widgets.Layout(width="500px"),
)

project_id_text = widgets.Text(
    description="Project ID",
    placeholder="your-gcp-project-id",
    layout=widgets.Layout(width="400px"),
)

zone_dropdown = widgets.Dropdown(
    options=["us-east4-b", "us-central1-a", "us-central1-b"],
    value="us-east4-b",
    description="Zone",
    layout=widgets.Layout(width="250px"),
)

machine_type_dropdown = widgets.Dropdown(
    options=[],          
    description="Machine",
    layout=widgets.Layout(width="250px"),
)

gpu_type_dropdown = widgets.Dropdown(
    options=[
        ("No GPU", "none"),
        ("NVIDIA T4", "nvidia-tesla-t4"),
        ("NVIDIA L4", "nvidia-l4"),
    ],
    value="none",
    description="GPU type",
    layout=widgets.Layout(width="300px"),
)

gpu_count_int = widgets.BoundedIntText(
    value=1,
    min=1,
    max=8,
    step=1,
    description="#GPU",
    layout=widgets.Layout(width="150px"),
)

packages_text = widgets.Text(
    description="Packages",
    placeholder="torch torchvision",
    layout=widgets.Layout(width="500px"),
)

code_textarea = widgets.Textarea(
    description="Code",
    placeholder="Write Python code here to run on the VM",
    layout=widgets.Layout(width="800px", height="200px"),
)

run_button = widgets.Button(
    description="Run on GPU VM",
    button_style="primary",
)

output_area = widgets.Output()

load_mtypes_button = widgets.Button(
    description="Load machine types",
    button_style="info",
    layout=widgets.Layout(width="200px"),
)

#Refresh Functions for gui

def refresh_machine_types(*args):
    output_area.clear_output()
    with output_area:
        service_account_file = service_account_text.value.strip()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_file
        project_id = project_id_text.value.strip()
        zone = zone_dropdown.value

        if not project_id:
            print("❌ Please enter Project ID first.")
            return

        print(f"🔄 Loading machine types for project={project_id}, zone={zone} ...")

        try:
            client = compute_v1.MachineTypesClient()
            mts = list(client.list(project=project_id, zone=zone))
            names = [mt.name for mt in mts]
            names.sort()
            machine_type_dropdown.options = names
            if names:
                machine_type_dropdown.value = names[0]
            print(f"✅ Loaded {len(names)} machine types.")
        except Exception as e:
            print("❌ Failed to load machine types:")
            print(e)
def refresh_gpu_types(*args):
    output_area.clear_output()
    with output_area:
        project_id = project_id_text.value.strip()
        zone = zone_dropdown.value

        if not project_id:
            print("❌ Please enter Project ID first.")
            return

        print(f"🔄 Loading GPU types for project={project_id}, zone={zone} ...")

        try:
            client = compute_v1.AcceleratorTypesClient()
            ats = list(client.list(project=project_id, zone=zone))

            options = [("No GPU", "none")]
            gpu_type_limits.clear()

            for at in ats:

                label = f"{at.name} ({at.description})"
                options.append((label, at.name))
                gpu_type_limits[at.name] = at.maximum_cards_per_instance

            gpu_type_dropdown.options = options
            gpu_type_dropdown.value = "none"

            gpu_count_int.max = 1
            gpu_count_int.value = 1

            print(f"✅ Loaded {len(ats)} GPU types.")
        except Exception as e:
            print("❌ Failed to load GPU types:")
            print(e)

def on_gpu_type_change(change):
    if change["name"] != "value":
        return

    value = change["new"]

    if value == "none":
        gpu_count_int.max = 1
        gpu_count_int.value = 1
    else:
        max_cards = gpu_type_limits.get(value, 4)  
        gpu_count_int.max = max_cards
        if gpu_count_int.value > max_cards:
            gpu_count_int.value = max_cards
gpu_type_dropdown.observe(on_gpu_type_change, names="value")

def on_run_button_clicked(b):
    global vm
    output_area.clear_output()
    buf = io.StringIO()

    with output_area:
        print("▶ Starting remote GPU run...\n")

        # service_account_file = service_account_text.value.strip() #ADD THIS BACK
        project_id = project_id_text.value.strip()
        zone = zone_dropdown.value
        machine_type = machine_type_dropdown.value
        gpu_type = gpu_type_dropdown.value
        gpu_count = gpu_count_int.value if gpu_type != "none" else 0
        packages = packages_text.value.strip()
        code = code_textarea.value

        if not service_account_file or not project_id:
            print("❌ Please provide both Service JSON path and Project ID.")
            return
        with contextlib.redirect_stdout(buf):
            try:
                print("attempting vm creation")
                print(service_account_file)
                vm = CloudVM(
                    service_account_file=service_account_file,
                    project_id=project_id,
                    zone=zone,
                    machine_type=machine_type,
                    gpu_type=None if gpu_type == "none" else gpu_type,
                    gpu_count=gpu_count,
                )
                print("VM created")
                vm.create_vm()
                vm.run_code(code, packages)
            except Exception:
                print("❌ An error occurred:")
                traceback.print_exc()
            # finally:
            #     try:
            #         # vm.delete_vm()
            #       print("▶ Ending remote GPU run...\n")

            #     except Exception:
            #         print("\n⚠ Failed to delete VM, please check manually.")
            #         traceback.print_exc()

        print(buf.getvalue())

run_button.on_click(on_run_button_clicked)

def on_load_button_clicked(b):
    refresh_machine_types()
    refresh_gpu_types()
    
# ---------------- EXTENSION LOAD/UNLOAD ----------------
def load_ipython_extension(ipython):
    global vm
    ipython.register_magics(RunContainerMagic)    
    #ATTEMPTING TO IMPLEMENT GUI
    
    config_box = widgets.VBox(
        [
            service_account_text,
            project_id_text,
            widgets.HBox([zone_dropdown, machine_type_dropdown, load_mtypes_button]),
            widgets.HBox([gpu_type_dropdown, gpu_count_int]),
            packages_text,
        ]
    )
    
    gui = widgets.VBox(
        [
            config_box,
            code_textarea,
            run_button,
            widgets.Label("Output:"),
            output_area,
        ]
    )
    
    load_mtypes_button.on_click(on_load_button_clicked)
    
    
    display(gui)
    #END OF GUI??



    
    # print("⏳ Initializing CloudContainer and starting/resuming VM...")
    # vm = CloudContainer(
    #     service_account_file=service_account_file,
    #     project_id=project_id,
    #     zone=zone
    # )
    # vm.connect_vm()  # VM resumes here
    # print("✅ VM is ready for running containers!")

    # # Optional: pre-pull container image to speed up first run
    # print("📦 starting container...")
    # try:
    #     vm.start_container()  # starts container and keeps it alive
    # except Exception as e:
    #     print(f"⚠️ Could not start container image: {e}")

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
