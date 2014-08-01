"""
compute least squares vector (du,dv)
based on original LKLeastSquares.cpp
"""
from stencil_code.stencil_kernel import StencilKernel
from hindemith.types.stencil import Stencil
from hindemith.utils import clamp
import numpy as np

__author__ = 'chick'


class LkLeastSquares(StencilKernel):
    def __init__(self, radius):
        super(LkLeastSquares, self).__init__()
        self.radius = radius

    class DuComputer(StencilKernel):
        def __init__(self):
            super(LkLeastSquares.DuComputer, self).__init__()

        def kernel(self, image1, image2, err, du):
            assert len(image1.shape) == 2

            mx = image1.shape[1]
            my = image1.shape[2]
            for p in image1.interior_points():
                ix2 = iy2 = ix_iy = ix_it = iy_it = 0.0

                for n_p in image1.neighbor_points():
                    clamp_x = clamp(n_p[0], 0, mx)
                    clamp_y = clamp(n_p[1], 0, my)
                    ix2 += image1[clamp_x, clamp_y] * image1[clamp_x, clamp_y]
                    iy2 += image2[clamp_x, clamp_y] * image2[clamp_x, clamp_y]
                    ix_iy += image1[clamp_x, clamp_y] * image2[clamp_x, clamp_y]
                    ix_it += image1[clamp_x, clamp_y] * err[clamp_x, clamp_y]
                    iy_it += image2[clamp_x, clamp_y] * err[clamp_x, clamp_y]

                det = ix2 * iy2 - ix_iy * ix_iy
                if det != 0:
                    du[p] = (ix_it * iy2 - ix_iy * ix_it) / det
                else:
                    du[p] = 0.0

    class DvComputer(StencilKernel):
        def __init__(self):
            super(LkLeastSquares.DvComputer, self).__init__()

        def kernel(self, image1, image2, err, dv):
            assert len(image1.shape) == 2

            mx = image1.shape[1]
            my = image1.shape[2]
            for p in image1.interior_points():
                ix2 = iy2 = ix_iy = ix_it = iy_it = 0.0

                for n_p in image1.neighbor_points():
                    clamp_x = clamp(n_p[0], 0, mx)
                    clamp_y = clamp(n_p[1], 0, my)
                    ix2 += image1[clamp_x, clamp_y] * image1[clamp_x, clamp_y]
                    iy2 += image2[clamp_x, clamp_y] * image2[clamp_x, clamp_y]
                    ix_iy += image1[clamp_x, clamp_y] * image2[clamp_x, clamp_y]
                    ix_it += image1[clamp_x, clamp_y] * err[clamp_x, clamp_y]
                    iy_it += image2[clamp_x, clamp_y] * err[clamp_x, clamp_y]

                det = ix2 * iy2 - ix_iy * ix_iy
                if det != 0:
                    dv[p]= (ix_it * iy2 - ix_iy * ix_it) / det
                else:
                    dv[p] = 0.0

    def kernel(self, image1, image2, err, du, dv):
        assert len(image1.shape) == 2 and len(image2) == 2

        image_1_stencil = Stencil(image1)
        image_1_stencil.set_neighborhood( 0,
            [(x, y) for x in range(-self.radius, self.radius + 1) for y in range(-self.radius, self.radius + 1)]
        )

        image_2_stencil = Stencil(image2)
        image_2_stencil.set_neighborhood( 0,
            [(x, y) for x in range(-self.radius, self.radius + 1) for y in range(-self.radius, self.radius + 1)]
        )

        LkLeastSquares.ComputeDu()(image_1_stencil, image_2_stencil, err, du)
        LkLeastSquares.ComputeDv()(image_1_stencil, image_2_stencil, err, dv)

if __name__ == '__main__':
    image1 = np.random.random([10, 10])
    image2 = image1.copy()
    error = np.random.random([10, 10])

    print(image2)
    for i in range(3, 6):
        image2[i][2:7] = list(reversed(image2[i][2:7]))

    print image2

    du = np.empty_like(image1)
    dv = np.empty_like(image2)

    lk_least_squares = LkLeastSquares(1)




