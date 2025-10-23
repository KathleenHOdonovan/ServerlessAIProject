from IPython.core.magic import (Magics, magics_class, line_cell_magic)

@magics_class
class StackqlMagic(Magics):

    @line_cell_magic
    def stackql(self, line, cell=None):
        if cell is None:
            try:
                # Evaluate in the user’s namespace
                ip = get_ipython()
                result = eval(line, ip.user_ns)
            except Exception as e:
                return f"Error: {e}"
        else:
            try:
                ip = get_ipython()
                # Execute full block of code
                 # Execute all but the last line
                code_lines = cell.strip().split("\n")
                exec_lines, last_line = code_lines[:-1], code_lines[-1]
            
                # Run the exec part (assignments, imports, etc.)
                exec("\n".join(exec_lines), ip.user_ns)
            
                # Evaluate the last line
                result = eval(last_line, ip.user_ns)
            except Exception as e:
                return f"Error: {e}"
        return f"Ran on a gpu here is the result : {result}"
def load_ipython_extension(ipython):
    ipython.register_magics(StackqlMagic)