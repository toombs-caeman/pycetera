import ast
import sys
def label(name):
    pass

def j(lineno):
    """Implements goto, with labels."""
    frame = sys._getframe().f_back
    called_from = frame

    if isinstance(lineno, str):
        with open(called_from.f_code.co_filename) as f:
            for node in ast.walk(ast.parse(f.read())):
                if isinstance(node, ast.Call) \
                    and isinstance(node.func, ast.Name) \
                    and node.func.id == 'label' \
                    and lineno == ast.literal_eval(node.args[0]):
                   lineno = node.lineno

    def hook(frame, event, arg):
        if event == 'line' and frame == called_from:
            try:
                frame.f_lineno = lineno
            except ValueError as e:
                print ("jump failed:", e)
            while frame:
                frame.f_trace = None
                frame = frame.f_back
            return None
        return hook

    while frame:
        frame.f_trace = hook
        frame = frame.f_back
    sys.settrace(hook)


def foo():
    a = 1
    j('l1')
    label('l2')
    a = 2
    print (1)
    label('l1')
    print (2)
    if a == 1:
        j('l2')
    print (4)


foo()



