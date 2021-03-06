import hindemith as hm
from hindemith.types import hmarray
from hindemith.operations.conv import ConvForward
from hindemith.operations.relu import ReluForward
from hindemith.operations.pool import PoolForward
from hindemith.operations.lrn import LrnForward
from hindemith.operations.softmax import SoftmaxForward
from hindemith.operations.inner_product import InnerProductForward
from hindemith.core import compose
from hindemith.cl import queues
import pycl as cl
import caffe
import numpy as np
import time

prototxt = "benchmarks/alexnet.prototxt"
caffemodel = "models/alexnet-ng/alexnet-ng.caffemodel"

caffe.set_mode_gpu()
caffe.set_device(2)
# caffe.set_mode_cpu()
caffe_net = caffe.Net(prototxt, caffemodel, caffe.TEST)

conv1_filters = caffe_net.params['conv1'][0].data.view(hmarray)
conv1_bias = caffe_net.params['conv1'][1].data.view(hmarray)
conv1 = hm.zeros(caffe_net.blobs['conv1'].data.shape)

norm1 = hm.zeros(caffe_net.blobs['norm1'].data.shape)
norm1_scale = hm.zeros(norm1.shape)

pool1 = hm.zeros(caffe_net.blobs['pool1'].data.shape)
pool1_mask = hm.zeros(pool1.shape)

conv2_filters = caffe_net.params['conv2'][0].data.view(hmarray)
conv2_bias = caffe_net.params['conv2'][1].data.view(hmarray)
conv2 = hm.zeros(caffe_net.blobs['conv2'].data.shape)

norm2 = hm.zeros(caffe_net.blobs['norm2'].data.shape)
norm2_scale = hm.zeros(norm2.shape)

pool2 = hm.zeros(caffe_net.blobs['pool2'].data.shape)
pool2_mask = hm.zeros(pool2.shape)

conv3_filters = caffe_net.params['conv3'][0].data.view(hmarray)
conv3_bias = caffe_net.params['conv3'][1].data.view(hmarray)
conv3 = hm.zeros(caffe_net.blobs['conv3'].data.shape)

conv4_filters = caffe_net.params['conv4'][0].data.view(hmarray)
conv4_bias = caffe_net.params['conv4'][1].data.view(hmarray)
conv4 = hm.zeros(caffe_net.blobs['conv4'].data.shape)

conv5_filters = caffe_net.params['conv5'][0].data.view(hmarray)
conv5_bias = caffe_net.params['conv5'][1].data.view(hmarray)
conv5 = hm.zeros(caffe_net.blobs['conv5'].data.shape)

pool5 = hm.zeros(caffe_net.blobs['pool5'].data.shape)
pool5_mask = hm.zeros(pool5.shape)

fc6_filters = caffe_net.params['fc6'][0].data.view(hmarray)
fc6_bias = caffe_net.params['fc6'][1].data.view(hmarray)
fc6 = hm.zeros(caffe_net.blobs['fc6'].data.shape)

fc7_filters = caffe_net.params['fc7'][0].data.view(hmarray)
fc7_bias = caffe_net.params['fc7'][1].data.view(hmarray)
fc7 = hm.zeros(caffe_net.blobs['fc7'].data.shape)

fc8_filters = caffe_net.params['fc8'][0].data.view(hmarray)
fc8_bias = caffe_net.params['fc8'][1].data.view(hmarray)
fc8 = hm.zeros(caffe_net.blobs['fc8'].data.shape)

prob = hm.zeros(caffe_net.blobs['prob'].data.shape)

local_size = 5
alpha = 0.0001
beta = 0.75


@compose(fusion=False)
def forward(data):
    global fc6, fc7, fc8
    conv1 = ConvForward(data, conv1_filters, conv1_bias,
                        kernel_size=(11, 11), padding=(0, 0),
                        stride=(4, 4))
    conv1 = ReluForward(conv1)
    norm1, norm1_scale = LrnForward(conv1, alpha=alpha, beta=beta,
                                    local_size=local_size, k=1)
    pool1, pool1_mask = PoolForward(norm1, kernel_size=(3, 3),
                                    padding=(0, 0), stride=(2, 2))

    conv2 = ConvForward(pool1, conv2_filters, conv2_bias,
                        kernel_size=(5, 5), padding=(2, 2),
                        stride=(1, 1))
    conv2 = ReluForward(conv2)
    norm2, norm2_scale = LrnForward(conv2, alpha=alpha, beta=beta,
                                    local_size=local_size, k=1)
    pool2, pool2_mask = PoolForward(norm2, kernel_size=(3, 3),
                                    padding=(0, 0), stride=(2, 2))

    conv3 = ConvForward(pool2, conv3_filters, conv3_bias,
                        kernel_size=(3, 3), padding=(1, 1),
                        stride=(1, 1))
    conv3 = ReluForward(conv3)

    conv4 = ConvForward(conv3, conv4_filters, conv4_bias,
                        kernel_size=(3, 3), padding=(1, 1),
                        stride=(1, 1))
    conv4 = ReluForward(conv4)

    conv5 = ConvForward(conv4, conv5_filters, conv5_bias,
                        kernel_size=(3, 3), padding=(1, 1),
                        stride=(1, 1))
    conv5 = ReluForward(conv5)
    pool5, pool5_mask = PoolForward(conv5, kernel_size=(3, 3),
                                    padding=(0, 0), stride=(2, 2))

    fc6 = InnerProductForward(pool5, fc6_filters, fc6_bias)
    fc6 = ReluForward(fc6)

    fc7 = InnerProductForward(fc6, fc7_filters, fc7_bias)
    fc7 = ReluForward(fc7)

    fc8 = InnerProductForward(fc7, fc8_filters, fc8_bias)
    prob = SoftmaxForward(fc8)
    return prob

im = caffe.io.load_image('data/cat.jpg')
transformer = caffe.io.Transformer(
    {'data': caffe_net.blobs['data'].data.shape})
transformer.set_mean(
    'data', np.load('models/ilsvrc_2012_mean.npy').mean(1).mean(1))
transformer.set_transpose('data', (2, 0, 1))
transformer.set_channel_swap('data', (2, 1, 0))
transformer.set_raw_scale('data', 255.0)


def get_data():
    # data = np.asarray([
    #     transformer.preprocess('data', im),
    # ]).view(hmarray)
    data = hm.random((128, 3, 227, 227), _range=(0, 255))

    # data *= hmarray.random((5, 3, 227, 227), _range=(0, 2))
    # data -= hmarray.random((5, 3, 227, 227), _range=(-20, +20))
    data.sync_ocl()
    return data

num_trials = 10
hm_time = 0
caffe_time = 0

# warmup and test correctness
for _ in range(2):
    data = get_data()
    forward(data)
    caffe_net.forward_all(data=data)

    for blob_name in caffe_net.blobs.keys():
        blob = globals()[blob_name]
        blob.sync_host()
        if "_diff" in blob_name:
            continue
        print("Checking blob {}".format(blob_name))
        caffe_blob = caffe_net.blobs[blob_name].data
        np.testing.assert_array_almost_equal(blob, caffe_blob, decimal=1)
    caffe_prob = caffe_net.blobs['prob'].data
    prob.sync_host()
    np.testing.assert_array_almost_equal(prob, caffe_prob, decimal=4)

data = get_data()
cl.clFinish(queues[0])
for i in range(num_trials):
    start = time.clock()
    forward(data)
    hm_time += time.clock() - start
    start = time.clock()
    caffe_net.forward_all(data=data)
    caffe_time += time.clock() - start

    # for blob_name in caffe_net.blobs.keys():
    #     blob = globals()[blob_name]
    #     blob.sync_host()
    #     if "_diff" in blob_name:
    #         continue
    #     print("Checking blob {}".format(blob_name))
    #     caffe_blob = caffe_net.blobs[blob_name].data
    #     np.testing.assert_array_almost_equal(blob, caffe_blob, decimal=3)
    # print(np.argmax(prob))
    # print(np.argmax(caffe_net.blobs['prob'].data))
print("Hindemith AVG        : {}".format(hm_time / num_trials))
print("Caffe AVG            : {}".format(caffe_time / num_trials))
print("Speedup (CAFFE / HM) : {}".format(caffe_time / hm_time))
print "SUCCESS"
