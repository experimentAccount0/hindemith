import ast
from pycl import clCreateProgramWithSource

from ctree.frontend import get_ast
from ctree.c.nodes import SymbolRef, Op
from ctree.jit import LazySpecializedFunction
import ctree

from hindemith.core import coercer
from hindemith.utils import unique_python_name, unique_name
from hindemith.operations.dense_linear_algebra.array_op import ArrayOpConcrete

import ctypes as ct

import logging
LOG = logging.getLogger('Hindemith')

def fuse(fn_locals, fn_globals):
    def wrapped_fuser(fn):
        def fused(*args, **kwargs):
            tree = get_ast(fn)
            # ctree.browser_show_ast(tree, 'tmp.png')
            return fn(*args, **kwargs)
        return fused
    return wrapped_fuser


def get_blocks(tree):
    """Convenience method for getting the blocks from an ast

    :tree: @todo
    :returns: @todo

    """
    blocks = []
    BlockBuilder(blocks).visit(tree)
    return blocks


class BlockBuilder(ast.NodeVisitor):

    """Docstring for BlockBuilder. """

    def __init__(self, blocks):
        """@todo: to be defined1.

        :blocks: @todo

        """
        ast.NodeVisitor.__init__(self)

        self._blocks = blocks

    def visit_FunctionDef(self, node):
        """@todo: Docstring for visit_FunctionDef.

        :node: @todo
        :returns: @todo

        """
        self._blocks.extend(node.body)
        

class Fuser(object):

    """Docstring for Fuser. """

    def __init__(self, blocks, _locals, _globals):
        """@todo: to be defined1.

        :blocks: @todo
        :_locals: @todo
        :_globals: @todo

        """
        self._blocks = blocks
        self._locals = _locals
        self._globals = _globals
        self._symbol_table = dict(_locals, **_globals)
        self._defns = []

    def do_fusion(self):
        """@todo: Docstring for do_fusion.

        :blocks: @todo
        :returns: @todo

        """
        fused_blocks = [[self._blocks.pop()]]
        for block in self._blocks:
            print(ast.dump(block))
            if self._is_fusable(fused_blocks[-1][-1], block):
                fused_blocks[-1].append(block)
            else:
                fused_blocks.append([block])
        self._blocks = list(map(self._fuse, fused_blocks))

    def _is_fusable(self, block_1, block_2):
        """@todo: Docstring for _is_fusable.

        :block_1: @todo
        :block_2: @todo
        :returns: @todo

        """
        if isinstance(block_1, ast.Assign) and isinstance(block_2, ast.Assign):
            if isinstance(block_1.value, ast.Call) and \
               isinstance(block_2.value, ast.Call):
                func_1 = self._symbol_table[block_1.value.func.id]
                func_2 = self._symbol_table[block_2.value.func.id]
                return hasattr(func_1, 'fusable') and func_1.fusable() and \
                       hasattr(func_2, 'fusable') and func_2.fusable()
        return False

    def _fuse(self, blocks):
        """@todo: Docstring for _fuse.

        :block_1: @todo
        :block_2: @todo
        :returns: @todo

        """
        if len(blocks) == 1:
            return blocks[0] 
        pass



# def fuse(fn_locals, fn_globals):
#     def wrapped_fuser(fn):
#         def fused_fn(*args, **kwargs):
#             symbol_table = dict(fn_locals, **fn_globals)
#             arg_table = {}
#             a = []
#             for name, value in kwargs.items():
#                 symbol_table[name] = value
#                 arg_table[name] = value
#                 a.append(name)
#             tree = get_ast(fn)
#             blocks = tree.body[0].body

#             MagicMethodProcessor().visit(tree)
#             decls = []
#             BlockBuilder(symbol_table, decls).visit(tree)
#             # init = [get_specializer(blocks[0], symbol_table)]
#             decls.extend(tree.body[0].body)
#             tree.body[0].body = decls
#             tree.body[0].decorator_list = []
#             tree.body.append(
#                 ast.Assign(
#                     [ast.Subscript(
#                         ast.Name('symbol_table', ast.Load()),
#                         ast.Index(ast.Str('E')),
#                         ast.Store())],
#                     ast.Call(
#                         func=ast.Name(fn.__name__, ast.Load()),
#                         args=[],
#                         keywords=[ast.keyword(arg, ast.Subscript(
#                             ast.Name('symbol_table', ast.Load()),
#                             ast.Index(ast.Str(arg)),
#                             ast.Load()))
#                             for arg in a]
#                     )
#                 )
#             )
#             tree = ast.fix_missing_locations(tree)
#             exec(compile(tree, filename='', mode='exec')) in fn_globals, locals()
#             # from ctree import browser_show_ast
#             # browser_show_ast(tree, 'tmp.png')
#             return symbol_table['E']
#         return fused_fn
#     return wrapped_fuser


# def fusable(prev, next):
#     return True


# def do_fusion(prev, next):
#     if True:  # TODO: Fusability check
#         return True
#     else:
#         return False


# class PromoteToRegister(ast.NodeTransformer):
#     def __init__(self, name, new_name, new_type):
#         super(PromoteToRegister, self).__init__()
#         self.target = name
#         self.new_target = new_name
#         self.new_type = new_type

#     def visit_FunctionDecl(self, node):
#         node.defn = list(map(self.visit, node.defn))
#         node.params = list(filter(lambda x: x.name != self.target, node.params))
#         node.defn.insert(0, SymbolRef(self.new_target, self.new_type))
#         return node

#     def visit_BinaryOp(self, node):
#         if isinstance(node.op, Op.ArrayRef):
#             if node.left.name == self.target:
#                 return SymbolRef(self.new_target)

#         node.left = self.visit(node.left)
#         node.right = self.visit(node.right)
#         return node


# class BlockBuilder(ast.NodeTransformer):
#     def __init__(self, symbol_table, decls):
#         self.symbol_table = symbol_table
#         self.decls = decls
#         self.prev = None

#     def get_if_specializer(self, name, attr):
#         try:
#             func = self.symbol_table[name]
#             if attr is not None:
#                 func = getattr(func, attr)
#             if hasattr(func, 'specialized') and \
#                isinstance(func.specialized, LazySpecializedFunction):
#                 return func.specialized
#             else:
#                 return None
#         except KeyError:
#             return None

#     def get_specializer(self, node):
#         if hasattr(node, 'func'):
#             if isinstance(node.func, ast.Attribute):
#                 arg = getattr(
#                     self.symbol_table[node.func.value.id], node.func.attr
#                 )
#                 name = node.func.value.id
#                 attr = "" + node.func.attr
#             else:
#                 name = node.func.id
#                 attr = None
#         else:
#             return False
#         exec(
#             "self.result = self.get_if_specializer('{0}', {1})".format(name, attr),
#             globals(), dict(self.symbol_table, **{'self': self})
#         )
#         return self.result

#     def attempt_fusion(self, previous, next_tree):
#         prev = self.get_specializer(previous.value)
#         next = self.get_specializer(next_tree.value)
#         print(prev, next)
#         if not prev or not next:
#             LOG.debug(
#                 "Fusing failed because one of the operations is not a \
#                  specializer: %s %s",
#                 prev, next
#             )
#             return

#         fused_name = unique_python_name()
#         fused = ast.Call(
#             func=ast.Subscript(
#                 ast.Name('symbol_table', ast.Load()),
#                 ast.Index(ast.Str(fused_name)),
#                 ast.Load()),
#             args=previous.value.args + [next_tree.value.func.value],
#             keywords=[]
#         )
#         list1 = prev.get_fusable_nodes(
#             self.symbol_table[previous.value.args[0].id],
#             self.symbol_table[previous.targets[0].id].name
#         )
#         list2 = next.get_fusable_nodes(
#             self.symbol_table[next_tree.value.args[0].id],
#             self.symbol_table[next_tree.targets[0].id].name
#         )

#         args = []
#         args.append(self.symbol_table[previous.value.args[0].id])
#         # args.append(self.symbol_table[previous.value.func.value.id])
#         args.append(self.symbol_table[next_tree.value.args[0].id])
#         args.append(self.symbol_table[next_tree.targets[0].id])
#         tree = list1[0]
#         kernel = tree.body[0]
#         tree2 = list2[0]
#         kernel2 = tree2.body[0]
#         kernel.params.extend(kernel2.params)
#         kernel.defn.append(kernel2.defn[-1])

#         PromoteToRegister('D', unique_name(), ct.c_float()).visit(kernel)
#         # tree.body.append(list2[0].body[0])
#         print(kernel)
#         fn = ArrayOpConcrete(
#             self.symbol_table[previous.value.func.value.id].data, args[-1]
#         )

#         program = clCreateProgramWithSource(
#             fn.context, kernel.codegen()
#         ).build()
#         ptr = program[kernel.name]
#         func = fn.finalize(
#             ptr, self.symbol_table[previous.value.func.value.id].data.shape
#         )
#         self.symbol_table[fused_name] = func
#         previous.value = ast.copy_location(fused, previous.value)
#         previous.targets = next_tree.targets
#         return True

#     def visit_FunctionDef(self, node):
#         body = []
#         for child in node.body:
#             result = self.visit(child)
#             # Currently only support fusing assign nodes
#             if isinstance(result, ast.Assign):
#                 if isinstance(result.value, ast.Call):
#                     if self.prev:
#                         LOG.debug(
#                             "Attempting fusion with %s, %s", self.prev, child
#                         )
#                         if self.attempt_fusion(self.prev, child):
#                             self.prev = child
#                             continue
#                     self.prev = child
#             else:
#                 self.prev = None
#             body.append(child)
#         node.body = body
#         return node

#     def visit_Assign(self, node):
#         LOG.debug('Found Assign node, attempting type inference.')
#         specializer = self.get_specializer(node.value)
#         if specializer:
#             output = specializer.generate_output(
#                 *(self.symbol_table[arg.id] for arg in node.value.args)
#             )
#             self.symbol_table[output.name] = output
#             LOG.debug('Found specializer that returns type %s', type(output))
#         node.value = self.visit(node.value)
#         return node


# class MagicMethodProcessor(ast.NodeTransformer):
#     """
#     Converts locations in a python AST where a magic method would be called to a
#     Call node for that magic method.

#     For example, ``a + b`` would become ``a.__add__(b)``.

#     By exposing references to these magic methods, we can check if they are
#     subclasses of LazySpecializedFunction.  If so, we can do further checks to
#     determine their fusability.
#     """
#     def __init__(self):
#         self.result = False

#     def visit_BinOp(self, node):
#         attr_map = {
#             ast.Mult: '__mul__',
#             ast.Div: '__div__',
#             ast.Sub: '__sub__',
#             ast.Add: '__add__'
#         }
#         attr = attr_map[type(node.op)]
#         expr = ast.Call(
#             func=ast.Attribute(
#                 value=node.left,
#                 attr=attr,
#                 ctx=ast.Load()
#             ),
#             args=[node.right],
#             keywords=[]
#         )

#         expr = ast.fix_missing_locations(expr)
#         return ast.copy_location(expr, node)
