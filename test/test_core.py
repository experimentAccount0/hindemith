import unittest
import numpy
from numpy import testing
from hindemith.core import coercer, fuse
from hindemith.operations.dense_linear_algebra.array_op import square
from hindemith.operations.optical_flow.warp_img2D import warp_img2d
from hindemith.types.common import Float32, Int, Scalar, Array
from hindemith.utils import unique_name, UnsupportedTypeError
from stencil_code.stencil_grid import StencilGrid
from stencil_code.stencil_kernel import StencilKernel

__author__ = 'leonardtruong'


class TestCoercer(unittest.TestCase):
    def _check(self, value, type):
        self.assertIsInstance(coercer(('name', value))[1], type)

    def test_Float32(self):
        self._check(0.0, Float32)

    def test_Int(self):
        self._check(54, Int)

    def test_Array(self):
        array = Array(unique_name(), numpy.ones((10, 10)))
        self._check(array, Array)

    def test_Scalar(self):
        scalar = Scalar(unique_name(), 3)
        self._check(scalar, Scalar)

    def test_ndarray(self):
        array = numpy.ones((20, 20))
        self._check(array, Array)

    def test_not_support(self):
        self.assertRaises(UnsupportedTypeError, coercer, ('name', 'string'))


class StencilA(StencilKernel):
    def kernel(self, input, output):
        for x in input.interior_points():
            for y in input.neighbors(x, 0):
                output[x] = input[y] * .083333333
            for y in input.neighbors(x, 1):
                output[x] = input[y] * .666666667
            for y in input.neighbors(x, 2):
                output[x] = input[y] * -.666666667
            for y in input.neighbors(x, 3):
                output[x] = input[y] * -.083333333


class StencilB(StencilKernel):
    def kernel(self, input, output):
        for x in input.interior_points():
            for y in input.neighbors(x, 0):
                output[x] = input[y] * .083333333
            for y in input.neighbors(x, 1):
                output[x] = input[y] * .333333333

stencil_a = StencilA(backend='omp').kernel
stencil_b = StencilB(backend='omp').kernel


class TestDecorator(unittest.TestCase):
    def test_dec(self):
        @fuse
        def test_func(arg=None):
            return arg

        a = test_func(arg=1)
        self.assertEqual(a.value, 1)

    def test_fusion(self):
        @fuse
        def test_func(A=None, B=None, C=None):
            D = A * B
            E = C - D
            return E

        A = Array('A', numpy.random.rand(200, 200).astype(numpy.float32))
        B = Array('B', numpy.random.rand(200, 200).astype(numpy.float32))
        C = Array('C', numpy.random.rand(200, 200).astype(numpy.float32))
        actual = test_func(A=A, B=B, C=C)
        expected = C.data - (A.data * B.data)
        try:
            testing.assert_array_almost_equal(actual.data, expected, decimal=3)
        except AssertionError as e:
            self.fail("Outputs not equal: %s" % e.message)

    def test_hs_jacobi(self):
        @fuse
        def hs_jacobi_solver(im1_data, im2_data, u, v, zero, lam2, num_iter):
            du = zero * u
            dv = zero * v

            old_im2_data = im2_data
            im2_data = StencilGrid(im2_data.shape, data=im2_data.data)
            for index, defn in enumerate(
                    [[(-2, 0)], [(-1, 0)], [(1, 0)], [(2, 0)]]):
                im2_data.set_neighborhood(index, defn)
            tex_Ix = stencil_a(im2_data)
            tex_Iy = stencil_a(im2_data)
            im2_data = old_im2_data
            tex_Ix = Array(unique_name(), tex_Ix.data)
            tex_Iy = Array(unique_name(), tex_Iy.data)
            Ix = warp_img2d(tex_Ix, u, v)
            Iy = warp_img2d(tex_Iy, u, v)
            It = im1_data - warp_img2d(im2_data, u, v)
            Ix2 = square(Ix)
            Iy2 = square(Iy)

            for i in range(num_iter.value):
                du = StencilGrid(du.shape, data=du.data)
                dv = StencilGrid(dv.shape, data=dv.data)
                for index, defn in enumerate(
                    [[(-1, -1), (1, -1), (1, 0), (0, 1)],
                     [(0, -1), (-1, 0), (-1, 1), (1, 1)]]):
                    du.set_neighborhood(index, defn)
                    dv.set_neighborhood(index, defn)
                ubar = stencil_b(du)
                ubar = Array(unique_name(), ubar.data)
                vbar = stencil_b(dv)
                vbar = Array(unique_name(), vbar.data)
                num = Ix * ubar + Iy * vbar + It
                den = Ix2 + Iy2
                den = lam2 + den
                du = ubar - (Ix * num) / den
                dv = vbar - (Iy * num) / den
            return du, dv

        def py_hs_jacobi_solver(im1_data, im2_data, u, v, zero, lam2, num_iter):
            du = zero * u
            dv = zero * v

            im2_data = StencilGrid(im2_data.shape, data=im2_data)
            for index, defn in enumerate(
                    [[(-2, 0)], [(-1, 0)], [(1, 0)], [(2, 0)]]):
                im2_data.set_neighborhood(index, defn)
            tex_Ix = stencil_a(im2_data).data
            tex_Iy = stencil_a(im2_data).data
            im2_data = Array(unique_name(), im2_data.data)
            u = Array(unique_name(), u)
            v = Array(unique_name(), v)
            Ix = warp_img2d(Array(unique_name(), tex_Ix), u, v).data
            Iy = warp_img2d(Array(unique_name(), tex_Iy), u, v).data
            It = im1_data - warp_img2d(im2_data, u, v).data
            Ix2 = Ix * Ix
            Iy2 = Iy * Iy

            for i in range(num_iter):
                du = StencilGrid(du.shape, data=du)
                dv = StencilGrid(dv.shape, data=dv)
                for index, defn in enumerate(
                    [[(-1, -1), (1, -1), (1, 0), (0, 1)],
                     [(0, -1), (-1, 0), (-1, 1), (1, 1)]]):
                    du.set_neighborhood(index, defn)
                    dv.set_neighborhood(index, defn)
                ubar = stencil_b(du).data
                vbar = stencil_b(dv).data
                num = Ix * ubar + Iy * vbar + It
                den = Ix2 + Iy2 + lam2
                du = ubar - (Ix * num) / den
                dv = vbar - (Iy * num) / den
            return du, dv

        im1 = numpy.random.rand(120, 80).astype(numpy.float32)
        im2 = numpy.random.rand(120, 80).astype(numpy.float32)
        u = numpy.zeros((120, 80), numpy.float32)
        v = numpy.zeros((120, 80), numpy.float32)
        zero = 0.0
        alpha = 0.1
        lam2 = alpha ** 2
        num_iter = 10
        du, dv = hs_jacobi_solver(
            im1_data=im1, im2_data=im2, u=u, v=v, zero=zero, lam2=lam2,
            num_iter=num_iter
        )

        py_du, py_dv = py_hs_jacobi_solver(
            im1_data=im1, im2_data=im2, u=u, v=v, zero=zero, lam2=lam2,
            num_iter=num_iter
        )

        testing.assert_array_almost_equal(du.data, py_du)
        testing.assert_array_almost_equal(dv.data, py_dv)
