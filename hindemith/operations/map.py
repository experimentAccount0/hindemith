__author__ = 'leonardtruong'

from ctree.frontend import get_ast
from ctree.c.nodes import SymbolRef, FunctionDecl, CFile, Assign, ArrayRef, \
    Constant, BinaryOp, Op, FunctionCall
from ctree.ocl import get_context_and_queue_from_devices
from ctree.nodes import Project, CtreeNode
from ctree.jit import LazySpecializedFunction, ConcreteSpecializedFunction
from ctree.templates.nodes import StringTemplate
from ctree.transformations import PyBasicConversions
from hindemith.types.hmarray import NdArrCfg, hmarray, py_to_ctypes
from hindemith.nodes import kernel_range
import ast
import sys

import numpy as np
import pycl as cl
import ctypes as ct


class ElementReference(CtreeNode):
    _fields = ['name']

    def __init__(self, name):
        super(ElementReference, self).__init__()
        self.name = name


class StoreOutput(CtreeNode):
    _fields = ['target', 'value']

    def __init__(self, target, value):
        super(StoreOutput, self).__init__()
        self.target = target
        self.value = value


class MapFrontendTransformer(PyBasicConversions):
    def __init__(self, params):
        self.params = params
        super(MapFrontendTransformer, self).__init__()

    def visit_FunctionDef(self, node):
        if sys.version_info < (3, 0):
            self.target = node.args.args[0].id
        else:
            self.target = node.args.args[0].arg
        node.body = list(map(self.visit, node.body))
        return node

    def visit_Name(self, node):
        if node.id == self.target:
            return ElementReference(self.params[0].name)
        return super(MapFrontendTransformer, self).visit_Name(node)

    def visit_Return(self, node):
        return StoreOutput(self.params[-1].name, self.visit(node.value))


class MapOclTransform(ast.NodeTransformer):
    def __init__(self, symbols=None, type_table=None):
        if symbols is None:
            self.symbols = {}
        else:
            self.symbols = symbols
        if type_table is None:
            self.type_table = {}
        else:
            self.type_table = type_table

    def infer_type(self, node):
        if isinstance(node, SymbolRef):
            try:
                return self.type_table[node.name]
            except KeyError:
                raise Exception(
                    "Could not infer type of variable {}".format(node.name))
        if isinstance(node, BinaryOp):
            if isinstance(node.op, Op.ArrayRef):
                return self.infer_type(node.left)._dtype_.type
            left = self.infer_type(node.left)
            # right = self.infer_type(node.right)
            return left
        elif isinstance(node, FunctionCall):
            if node.func.name == 'fabs':
                return self.infer_type(node.args[0])
            elif node.func.name == 'pow':
                return self.infer_type(node.args[0])
            elif node.func.name == 'float':
                return ct.c_float
            print(node)
            raise Exception(
                "Could not infer type of call to function {}".format(
                    node.func.name))
        elif isinstance(node, Constant):
            return py_to_ctypes[type(node.value)]
        raise Exception(
            "Could not infer type of variable {}".format(node.name))

    def visit_ElementReference(self, node):
        return ArrayRef(SymbolRef(node.name), SymbolRef('loop_idx'))

    def visit_StoreOutput(self, node):
        return Assign(ArrayRef(SymbolRef(node.target), SymbolRef('loop_idx')),
                      self.visit(node.value))

    def visit_BinaryOp(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        if isinstance(node.op, Op.Assign):
            if isinstance(node.left, SymbolRef) and \
               node.left.type is None:
                node.left.type = self.infer_type(node.right)()
            return node
        return node

    def visit_SymbolRef(self, node):
        if node.name in self.symbols:
            return Constant(self.symbols[node.name])
        if node.name == 'abs':
            node.name = 'fabs'
        if node.type is not None:
            self.type_table[node.name] = node.type
        return node


class OclConcreteMap(ConcreteSpecializedFunction):
    def __init__(self, entry_name, proj, entry_type):
        self._c_function = self._compile(entry_name, proj, entry_type)
        devices = cl.clGetDeviceIDs()
        self.context, self.queue = get_context_and_queue_from_devices(
            [devices[-1]])

    def finalize(self, kernel):
        self.kernel = kernel
        return self

    def __call__(self, arg):
        output = hmarray(np.zeros_like(arg))
        out_buf, evt = cl.buffer_from_ndarray(self.queue, output,
                                              blocking=True)
        output._ocl_buf = out_buf
        output._ocl_dirty = False
        output._host_dirty = True
        evt.wait()
        self._c_function(arg.ocl_buf, out_buf, self.queue, self.kernel)
        return output


class SpecializedMap(LazySpecializedFunction):
    backend = 'ocl'

    def args_to_subconfig(self, args):
        return NdArrCfg(args[0].dtype, args[0].ndim, args[0].shape)

    def transform(self, tree, program_cfg):
        arg_cfg, tune_cfg = program_cfg
        arg_types, params, kernel_params = None, None, None

        if self.backend == 'c':
            arg_types = (np.ctypeslib.ndpointer(
                arg_cfg.dtype, arg_cfg.ndim, arg_cfg.shape),
                np.ctypeslib.ndpointer(arg_cfg.dtype, arg_cfg.ndim,
                                       arg_cfg.shape))
            params = [SymbolRef.unique(sym_type=arg_types[0]()),
                      SymbolRef.unique(sym_type=arg_types[1]())]
        else:
            arg_types = (cl.cl_mem, cl.cl_mem)
            params = [SymbolRef.unique(sym_type=arg_types[0]()),
                      SymbolRef.unique(sym_type=arg_types[0]())]
            kernel_params = [
                SymbolRef(param.name,
                          np.ctypeslib.ndpointer(arg_cfg.dtype,
                                                 arg_cfg.ndim,
                                                 arg_cfg.shape)())
                for param in params
            ]

        tree = MapFrontendTransformer(params).visit(tree).files[0].body[0].body

        func = FunctionDecl(
            None,
            SymbolRef('map'),
            params
        )
        proj = Project([CFile('map', [func])])
        if self.backend == 'ocl':
            backend = MapOclTransform()
            loop_body = list(map(backend.visit, tree))
            proj.files[0].body.insert(0, StringTemplate("""
                #ifdef __APPLE__
                #include <OpenCL/opencl.h>
                #else
                #include <CL/cl.h>
                #endif
                """))
            arg_types += (cl.cl_command_queue, cl.cl_kernel)
            shape = arg_cfg.shape[::-1]
            control, kernel = kernel_range(shape, shape,
                                           kernel_params, loop_body)
            func.defn = control
            entry_type = ct.CFUNCTYPE(*((None,) + arg_types))
            func.params.extend((
                SymbolRef('queue', cl.cl_command_queue()),
                SymbolRef(kernel.body[0].name.name, cl.cl_kernel())
            ))
            fn = OclConcreteMap('map', proj, entry_type)
            print(kernel)
            print(func)
            program = cl.clCreateProgramWithSource(
                fn.context, kernel.codegen()).build()
            return fn.finalize(program[kernel.body[0].name.name])


def hmmap(fn):
    return SpecializedMap(get_ast(fn))


def base_sqrt(elt):
    return sqrt(elt)


sqrt = hmmap(base_sqrt)