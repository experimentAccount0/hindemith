from hindemith.fusion.core import fuse
from hindemith.fusion.core import dont_fuse_fusables

from stencil_code.stencil_kernel import StencilKernel
import numpy

from ctree.util import Timer


radius = 1


class Stencil(StencilKernel):
    @property
    def dim(self):
        return 2

    @property
    def ghost_depth(self):
        return 1

    def neighbors(self, pt, defn=0):
        if defn == 0:
            for x in range(-radius, radius+1):
                for y in range(-radius, radius+1):
                    yield (pt[0] - x, pt[1] - y)

    def kernel(self, in_grid, out_grid):
        for x in self.interior_points(out_grid):
            for y in self.neighbors(x, 0):
                out_grid[x] += in_grid[y]


x = []
iterations = 5
results = [[] for _ in range(3)]
speedup = [[] for _ in range(4)]


for width in range(2**8, 2**11 + 1, 256):
# for width in (2**x for x in range(8, 12)):
    print("Running width: %d" % width)
    total0, total1 = 0, 0
    for _ in range(iterations):
        stencil1 = Stencil(backend='ocl')
        stencil2 = Stencil(backend='ocl')
        stencil3 = Stencil(backend='ocl')
        stencil4 = Stencil(backend='ocl')

        @fuse
        def fused_f(A):
            C = stencil1(A)
            return stencil2(C)

        @dont_fuse_fusables
        def unfused_f(A):
            C = stencil3(A)
            return stencil4(C)

        A = numpy.random.rand(width, width).astype(numpy.float32) * 100

        a = fused_f(A)
        b = unfused_f(A)
        numpy.testing.assert_array_almost_equal(a[2:-2, 2:-2], b[2:-2, 2:-2])
        # x.append(width)
        with Timer() as fused_time:
            fused_f(A)
        results[0].append(fused_time.interval)
        total0 += fused_time.interval

        with Timer() as unfused_time:
            unfused_f(A)
        results[1].append(unfused_time.interval)
        total1 += unfused_time.interval
    total0 /= iterations
    total1 /= iterations
    speedup[0].append(total1/total0)
    # x.append(width)

    for _ in range(iterations):
        stencil1 = Stencil(backend='ocl')
        stencil2 = Stencil(backend='ocl')
        stencil3 = Stencil(backend='ocl')
        stencil4 = Stencil(backend='ocl')
        stencil5 = Stencil(backend='ocl')
        stencil6 = Stencil(backend='ocl')

        @fuse
        def fused_f(A):
            B = stencil1(A)
            C = stencil2(B)
            return stencil3(C)

        @dont_fuse_fusables
        def unfused_f(A):
            B = stencil4(A)
            C = stencil5(B)
            return stencil6(C)

        A = numpy.random.rand(width, width).astype(numpy.float32) * 100

        a = fused_f(A)
        b = unfused_f(A)
        numpy.testing.assert_array_almost_equal(a[2:-2, 2:-2], b[2:-2, 2:-2])
        # x.append(width)
        with Timer() as fused_time:
            fused_f(A)
        results[0].append(fused_time.interval)
        total0 += fused_time.interval

        with Timer() as unfused_time:
            unfused_f(A)
        results[1].append(unfused_time.interval)
        total1 += unfused_time.interval
    total0 /= iterations
    total1 /= iterations
    speedup[1].append(total1/total0)
    x.append(width)

    total0, total1 = 0, 0
    for _ in range(iterations):
        stencil1 = Stencil(backend='ocl')
        stencil2 = Stencil(backend='ocl')
        stencil3 = Stencil(backend='ocl')
        stencil4 = Stencil(backend='ocl')
        stencil5 = Stencil(backend='ocl')
        stencil6 = Stencil(backend='ocl')
        stencil7 = Stencil(backend='ocl')
        stencil8 = Stencil(backend='ocl')

        @fuse
        def fused_f(A):
            B = stencil1(A)
            C = stencil2(B)
            D = stencil3(C)
            return stencil4(D)

        @dont_fuse_fusables
        def unfused_f(A):
            B = stencil5(A)
            C = stencil6(B)
            D = stencil7(C)
            return stencil8(D)

        A = numpy.random.rand(width, width).astype(numpy.float32) * 100

        a = fused_f(A)
        b = unfused_f(A)
        numpy.testing.assert_array_almost_equal(a[4:-4, 4:-4], b[4:-4, 4:-4])
        # x.append(width)
        with Timer() as fused_time:
            fused_f(A)
        results[0].append(fused_time.interval)
        total0 += fused_time.interval

        with Timer() as unfused_time:
            unfused_f(A)
        results[1].append(unfused_time.interval)
        total1 += unfused_time.interval
    total0 /= iterations
    total1 /= iterations
    speedup[2].append(total1/total0)
    # x.append(width)
    total0, total1 = 0, 0
    for _ in range(iterations):
        stencil1 = Stencil(backend='ocl')
        stencil2 = Stencil(backend='ocl')
        stencil3 = Stencil(backend='ocl')
        stencil4 = Stencil(backend='ocl')
        stencil5 = Stencil(backend='ocl')
        stencil6 = Stencil(backend='ocl')
        stencil7 = Stencil(backend='ocl')
        stencil8 = Stencil(backend='ocl')
        stencil9 = Stencil(backend='ocl')
        stencil10 = Stencil(backend='ocl')

        @fuse
        def fused_f(A):
            B = stencil1(A)
            C = stencil2(B)
            D = stencil3(C)
            E = stencil4(D)
            return stencil5(E)

        @dont_fuse_fusables
        def unfused_f(A):
            B = stencil6(A)
            C = stencil7(B)
            D = stencil8(C)
            E = stencil9(D)
            return stencil10(E)

        A = numpy.random.rand(width, width).astype(numpy.float32) * 100

        a = fused_f(A)
        b = unfused_f(A)
        numpy.testing.assert_array_almost_equal(a[4:-4, 4:-4], b[4:-4, 4:-4])
        # x.append(width)
        with Timer() as fused_time:
            fused_f(A)
        results[0].append(fused_time.interval)
        total0 += fused_time.interval

        with Timer() as unfused_time:
            unfused_f(A)
        results[1].append(unfused_time.interval)
        total1 += unfused_time.interval
    total0 /= iterations
    total1 /= iterations
    speedup[3].append(total1/total0)


colors = ['b', 'c', 'r', 'g']
import matplotlib.pyplot as plt

r1 = plt.scatter(x, speedup[0], marker='x', color=colors[0])
r2 = plt.scatter(x, speedup[1], marker='x', color=colors[1])
r3 = plt.scatter(x, speedup[2], marker='x', color=colors[2])
r4 = plt.scatter(x, speedup[3], marker='x', color=colors[3])

plt.legend((r1, r2, r3, r4),
           ('2 Stencils', '3 Stencils', '4 Stencils', '5 Stencils'),
           scatterpoints=1,
           loc='lower left',
           ncol=3,
           fontsize=8)
plt.show()
