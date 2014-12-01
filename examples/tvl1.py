import numpy as np
import sys
import cv2
from hindemith.operations.zip_with import zip_with, ZipWith
from hindemith.types.hmarray import hmarray, square, EltWiseArrayOp
from hindemith.operations.map import sqrt, SpecializedMap
from hindemith.utils import symbols
from hindemith.operations.structured_grid import structured_grid
from hindemith.operations.reduce import sum
from hindemith.meta.core import meta
# import logging
# logging.basicConfig(level=20)


EltWiseArrayOp.backend = 'ocl'
ZipWith.backend = 'ocl'
SpecializedMap.backend = 'ocl'


num_warps = 1
n_scales = 1
n_inner = 30
n_outer = 10
median_filtering = 5
theta = .3
tau = .25
l = .15  # lambda
epsilon = 0.01
n = .8

symbol_table = {
    'num_warps': num_warps,
    'n_scales': n_scales,
    'theta': theta,
    'tau': tau,
    'l': l,
    'epsilon': epsilon,
    'n': n
}


@symbols(symbol_table)
def th(rho_elt, gradient_elt, delta_elt, u_elt):
    thresh = l * theta * gradient_elt
    if rho_elt < -thresh:
        return l * theta * delta_elt + u_elt
    elif rho_elt > thresh:
        return -l * theta * delta_elt + u_elt
    elif gradient_elt > 1e-10:
        return -rho_elt / gradient_elt * delta_elt + u_elt
    else:
        return 0


def py_th(rho_elt, gradient_elt, delta_elt, u_elt):
    thresh = l * theta * gradient_elt
    if rho_elt < -thresh:
        return l * theta * delta_elt + u_elt
    elif rho_elt > thresh:
        return -l * theta * delta_elt + u_elt
    elif gradient_elt > 1e-10:
        return -rho_elt / gradient_elt * delta_elt + u_elt
    else:
        return 0


py_thresh = np.vectorize(py_th, otypes=[np.float32])


def py_threshold(u1, u2, rho_c, gradient, I1wx, I1wy):
    rho = rho_c + I1wx * u1 + I1wy * u2
    v1 = py_thresh(rho, gradient, I1wx, u1)
    v2 = py_thresh(rho, gradient, I1wy, u2)
    return v1, v2


@symbols(symbol_table)
def ocl_th(rho_elt, gradient_elt, delta_elt, u_elt):
    thresh = float(l * theta) * gradient_elt
    if rho_elt < -thresh:
        return float(l * theta) * delta_elt + u_elt
    elif rho_elt > thresh:
        return float(-l * theta) * delta_elt + u_elt
    elif gradient_elt > 1e-10:
        return -rho_elt / gradient_elt * delta_elt + u_elt
    else:
        return float(0)


spec_th = zip_with(th)


@meta
def threshold(u1, u2, rho_c, gradient, I1wx, I1wy):
    rho = rho_c + I1wx * u1 + I1wy * u2
    v1 = spec_th(rho, gradient, I1wx, u1)
    v2 = spec_th(rho, gradient, I1wy, u2)
    return v1, v2


def centered_gradient(m):
    return np.gradient(m)


@structured_grid(border='zero')
def dx(src, output):
    for y, x in output:
        output[y, x] = src[y, x + 1] - src[y, x]


@structured_grid(border='zero')
def dy(src, output):
    for y, x in output:
        output[y, x] = src[y + 1, x] - src[y, x]


@structured_grid(border='constant', cval=0)
def divergence(v1, v2, output):
    for y, x in output:
        output[y, x] = v1[y, x] + v2[y, x] - v1[y, x - 1] - v2[y - 1, x]


def forward_gradient(m):
    """

    :rtype : hmarray
    """
    return dx(m), dy(m)


def py_forward_gradient(m):
    dx, dy = np.zeros_like(m), np.zeros_like(m)
    dy[:-1, ...] = m[1:, ...] - m[:-1, ...]
    dx[..., :-1] = m[..., 1:] - m[..., :-1]
    return dx, dy


def py_divergence(v1, v2):
    div = np.zeros_like(v1)
    div[1:, 1:] = v2[1:, 1:] - v2[:-1, 1:] + v1[1:, 1:] - v1[1:, :-1]
    div[1:, 0] = v2[1:, 0] - v2[:-1, 0] + v1[1:, 0]
    div[0, 1:] = v2[0, 1:] + v1[0, 1:] - v1[0, :-1]
    # div[0, 0] = v1[0, 0] + v2[0, 0]
    return div


def pyr_down(m, n_scales, n):
    pyr = [m]
    for _ in range(n_scales - 1):
        pyr.append(cv2.resize(pyr[-1], None, fx=n, fy=n))
    return pyr


def pyr_up(m, shape):
    return cv2.resize(m, shape)


def build_flow_map(idxs, u1, u2):
    _x = idxs[1].__add__(u1)
    _y = idxs[0].__add__(u2)
    return _x, _y


def warp(im, f1, f2):
    return cv2.remap(im, f1, f2, cv2.INTER_CUBIC)


def py_flow(I0, I1, u1, u2):
    p11 = np.zeros(I1.shape, dtype=np.float32)
    p12 = np.zeros(I1.shape, dtype=np.float32)
    p21 = np.zeros(I1.shape, dtype=np.float32)
    p22 = np.zeros(I1.shape, dtype=np.float32)
    i1y, i1x = centered_gradient(I1)
    i1x = i1x.astype(np.float32)
    i1y = i1y.astype(np.float32)
    indices = np.indices(u1.shape).astype(np.float32)
    for w in range(num_warps):
        _f1, _f2 = build_flow_map(indices, u1, u2)
        i1w = warp(I1, _f1, _f2)
        i1wx = warp(i1x, _f1, _f2)
        i1wy = warp(i1y, _f1, _f2)
        grad = np.square(i1wx) + np.square(i1wy)
        rho_c = i1w - i1wx * u1 - i1wy * u2 - I0
        n0 = 0
        error = sys.maxint
        while n0 < n_outer and error > epsilon * epsilon * I0.size:
            # u1 = cv2.medianBlur(u1, median_filtering)
            # u2 = cv2.medianBlur(u2, median_filtering)
            n1 = 0
            while n1 < n_inner and error > epsilon * epsilon * I0.size:
                v1, v2 = py_threshold(u1, u2, rho_c, grad, i1wx, i1wy)
                div_p1 = py_divergence(p11, p12)
                div_p2 = py_divergence(p21, p22)
                u1_old = u1
                u2_old = u2
                u1 = v1 + div_p1 * theta
                u2 = v2 + div_p2 * theta
                error = np.sum(np.square(u1 - u1_old) + np.square(u2 - u2_old))
                u1x, u1y = py_forward_gradient(u1)
                u2x, u2y = py_forward_gradient(u2)
                ng1 = 1.0 + tau / theta * np.sqrt(np.square(u1x) +
                                                  np.square(u1y))
                ng2 = 1.0 + tau / theta * np.sqrt(np.square(u2x) +
                                                  np.square(u2y))
                p11 = (p11 + tau / theta * u1x) / ng1
                p12 = (p12 + tau / theta * u1y) / ng1
                p21 = (p21 + tau / theta * u2x) / ng2
                p22 = (p22 + tau / theta * u2y) / ng2
                n1 += 1
            n0 += 1
    return u1, u2


def compute_flow(i0, i1, u1, u2):
    p11 = hmarray(np.zeros(i1.shape, dtype=np.float32))
    p12 = hmarray(np.zeros(i1.shape, dtype=np.float32))
    p21 = hmarray(np.zeros(i1.shape, dtype=np.float32))
    p22 = hmarray(np.zeros(i1.shape, dtype=np.float32))
    i1y, i1x = centered_gradient(i1)
    i1x = i1x.astype(np.float32)
    i1y = i1y.astype(np.float32)
    u1, u2 = hmarray(u1), hmarray(u2)
    i0 = hmarray(i0)
    indices = np.indices(u1.shape).astype(np.float32)
    for w in range(num_warps):
        _f1, _f2 = build_flow_map(indices, u1, u2)
        i1w = warp(i1, _f1, _f2)
        i1wx = warp(i1x, _f1, _f2)
        i1wy = warp(i1y, _f1, _f2)
        i1wx = hmarray(i1wx)
        i1wy = hmarray(i1wy)
        i1w = hmarray(i1w)
        grad = square(i1wx) + square(i1wy)
        rho_c = i1w - i1wx * u1 - i1wy * u2 - i0
        n0 = 0
        error = sys.maxint
        while n0 < n_outer and error > epsilon * epsilon * i0.size:
            # u1 = cv2.medianBlur(u1, median_filtering)
            # u2 = cv2.medianBlur(u2, median_filtering)
            n1 = 0
            while n1 < n_inner and error > epsilon * epsilon * i0.size:
                v1, v2 = threshold(u1, u2, rho_c, grad, i1wx, i1wy)
                div_p1 = divergence(p11, p12)
                div_p2 = divergence(p21, p22)
                u1_old = u1
                u2_old = u2
                u1 = v1 + div_p1 * theta
                u2 = v2 + div_p2 * theta
                error = sum(square(u1 - u1_old) + square(u2 - u2_old))
                u1x, u1y = forward_gradient(u1)
                u2x, u2y = forward_gradient(u2)
                ng1 = 1.0 + tau / theta * sqrt(square(u1x) +
                                               square(u1y))
                ng2 = 1.0 + tau / theta * sqrt(square(u2x) +
                                               square(u2y))
                p11 = (p11 + tau / theta * u1x) / ng1
                p12 = (p12 + tau / theta * u1y) / ng1
                p21 = (p21 + tau / theta * u2x) / ng2
                p22 = (p22 + tau / theta * u2y) / ng2
                n1 += 1
            n0 += 1
        u1.copy_to_host_if_dirty()
        u2.copy_to_host_if_dirty()
    u1, u2 = np.copy(u1), np.copy(u2)
    return u1, u2


def py_tvl1(im0, im1):
    im0 = im0.astype(np.float32)
    im1 = im1.astype(np.float32)
    # im0 = (cv2.GaussianBlur(im0))
    # im1 = (cv2.GaussianBlur(im1))
    im0_pyr = pyr_down(im0, n_scales, n)
    im1_pyr = pyr_down(im1, n_scales, n)
    u1 = np.zeros(im0_pyr[-1].shape, dtype=np.float32)
    u2 = np.zeros(im0_pyr[-1].shape, dtype=np.float32)
    for s in reversed(range(n_scales)):
        u1, u2, = py_flow(im0_pyr[s], im1_pyr[s], u1, u2)
        if s > 0:
            u1 = pyr_up(u1, im0_pyr[s - 1].shape[::-1]) * (1.0 / n)
            u2 = pyr_up(u2, im0_pyr[s - 1].shape[::-1]) * (1.0 / n)
    return u1, u2


def tvl1(im0, im1):
    im0 = im0.astype(np.float32)
    im1 = im1.astype(np.float32)
    # im0 = (cv2.GaussianBlur(im0))
    # im1 = (cv2.GaussianBlur(im1))
    im0_pyr = pyr_down(im0, n_scales, n)
    im1_pyr = pyr_down(im1, n_scales, n)
    u1 = np.zeros(im0_pyr[-1].shape, dtype=np.float32)
    u2 = np.zeros(im0_pyr[-1].shape, dtype=np.float32)
    for s in reversed(range(n_scales)):
        u1, u2, = compute_flow(im0_pyr[s], im1_pyr[s], u1, u2)
        if s > 0:
            u1 = pyr_up(u1, im0_pyr[s - 1].shape[::-1]) * (1.0 / n)
            u2 = pyr_up(u2, im0_pyr[s - 1].shape[::-1]) * (1.0 / n)
    return u1, u2

import os
file_path = os.path.dirname(os.path.realpath(__file__))

frame0 = cv2.imread(file_path + '/frame0.png')
frame1 = cv2.imread(file_path + '/frame1.png')
im0 = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY)
im1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
# tvl1(im0, im1)
# import cProfile
# cProfile.run('tvl1(im0, im1)')
# exit()
py_u1, py_u2 = py_tvl1(im0, im1)
u = tvl1(im0, im1)
np.testing.assert_allclose(py_u1, np.copy(u[0]), 1e-7, 1)
np.testing.assert_allclose(py_u2, np.copy(u[1]), 1e-7, 1)
print("PASSED")
from ctree.util import Timer
# with Timer() as t:
#     py_tvl1(im0, im1)
# print("Python time: {}".format(t.interval))
with Timer() as t:
    tvl1(im0, im1)
print("Specialized time: {}".format(t.interval))
exit()
# np.save("u1-cached", u1)
# np.save("u2-cached", u2)
# u1_expected = np.load(file_path + "/u1-cached.npy")
# u2_expected = np.load(file_path + "/u2-cached.npy")
# np.testing.assert_array_almost_equal(u1, u1_expected)
# np.testing.assert_array_almost_equal(u2, u2_expected)
# print("PASSED")
# exit()
mag, ang = cv2.cartToPolar(u[0], u[1])
hsv = np.zeros_like(frame0)
hsv[..., 1] = 255
hsv[..., 0] = ang*180/np.pi/2
hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
cv2.imshow('frame1', rgb)

# Baseline
# hsv2 = np.zeros_like(frame0)
# flow = cv2.calcOpticalFlowFarneback(im0, im1, 0.5, 5, 15, 3, 5, 1.2, 0)
# mag2, ang2 = cv2.cartToPolar(flow[..., 0], flow[..., 1])
# hsv2[..., 1] = 255
# hsv2[..., 0] = ang2*180/np.pi/2
# hsv2[..., 2] = cv2.normalize(mag2, None, 0, 255, cv2.NORM_MINMAX)
# rgb2 = cv2.cvtColor(hsv2, cv2.COLOR_HSV2BGR)
# cv2.imshow('frame2', rgb2)
k = cv2.waitKey() & 0xff