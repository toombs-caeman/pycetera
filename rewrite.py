import ast
"""
using ast to rewrite expressions with virtual for
"""
class ItemOfTransformer(ast.NodeTransformer):
    def __init__(self):
        super(ItemOfTransformer, self).__init__()
        self.targets = []

    def visit_Expr(self, node):
        node = super(ItemOfTransformer, self).generic_visit(node)
        if hasattr(node.value, 'vfor_'):
            return node.value
        return node
    def visit_Call(self, node):
        if node.func.id == 'vfor':
            if not len(self.targets):
                return
            old_var = node.args[0].id
            new_var = 'vfor_' + old_var
            self.targets[-1].append(old_var)
            return ast.Name(id = new_var, ctx=ast.Load())
        self.targets.append([])
        new_node = super(ItemOfTransformer, self).generic_visit(node)
        t = self.targets.pop()
        node = ast.Expr(value=node)
        for t_ in t:
            node = ast.For(
                target=ast.Name(id='vfor_' + t_, ctx=ast.Store()),
                iter=ast.Name(id=t_, ctx=ast.Load()),
                body=[node],
                orelse=[],
            )
        node.vfor_ = True
        # starting at each call, look through the args
        return node

root = ast.parse("""
x = [1,2,3]
y = [4,5,6]
print(vfor(x), vfor(y))
""")
output = ast.parse("""
x = [1,2,3]
y = [4,5,6]
for vfor_y in y:
    for vfor_x in x:
        print(vfor_x, vfor_y)
""")
def astPrint(node):
    print(ast.dump(node), '\n')
# names = sorted({node.id for node in ast.walk(root) if isinstance(node, ast.Name)})
astPrint(root)
node = ItemOfTransformer().visit(root)
node = ast.fix_missing_locations(node)
astPrint(node)
astPrint(output)
exec(compile(node, "transformer", "exec"))
