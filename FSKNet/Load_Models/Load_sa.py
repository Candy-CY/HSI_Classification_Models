import numpy as np
import matplotlib.pyplot as plt
import scipy.io as sio
from keras.models import Sequential, Model
from keras.layers import Convolution2D, MaxPooling2D, Conv3D, MaxPooling3D, ZeroPadding3D
from keras.layers import Activation, Dropout, Flatten, Dense, BatchNormalization, Input
from keras.utils.np_utils import to_categorical
from sklearn.decomposition import PCA
from keras.optimizers import Adam, SGD, Adadelta, RMSprop, Nadam
import keras.callbacks as kcallbacks
from keras.regularizers import l2
import time
import collections
from sklearn import metrics, preprocessing

from Utils import zeroPadding, normalization, doPCA, modelStatsRecord, averageAccuracy, deformable_se_sep_SA,densenet_IN,ssrn_SS_IN,hybrid_in,cnn3_3D_IN


def indexToAssignment(index_, Row, Col, pad_length):
    new_assign = {}
    for counter, value in enumerate(index_):
        assign_0 = value // Col + pad_length
        assign_1 = value % Col + pad_length
        new_assign[counter] = [assign_0, assign_1]
    return new_assign


def assignmentToIndex(assign_0, assign_1, Row, Col):
    new_index = assign_0 * Col + assign_1
    return new_index


def selectNeighboringPatch(matrix, pos_row, pos_col, ex_len):
    selected_rows = matrix[range(pos_row - ex_len, pos_row + ex_len + 1), :]
    selected_patch = selected_rows[:, range(pos_col - ex_len, pos_col + ex_len + 1)]
    return selected_patch


def sampling(proptionVal, groundTruth):  # divide dataset into train and test datasets
    labels_loc = {}
    train = {}
    test = {}
    m = max(groundTruth)
    for i in range(m):
        indices = [j for j, x in enumerate(groundTruth.ravel().tolist()) if x == i + 1]
        np.random.shuffle(indices)
        labels_loc[i] = indices
        nb_val = int(proptionVal * len(indices))
        train[i] = indices[:-nb_val]
        test[i] = indices[-nb_val:]
    # whole_indices = []
    train_indices = []
    test_indices = []
    for i in range(m):
        train_indices += train[i]
        test_indices += test[i]
    np.random.shuffle(train_indices)
    np.random.shuffle(test_indices)
    return train_indices, test_indices


def model_MSDNet():
    model_dense = densenet_IN.ResnetBuilder.build_resnet_8((1, img_rows, img_cols, img_channels),
                                                         nb_classes)

    RMS = RMSprop(lr=0.0003)
    # Let's train the model using RMSprop
    model_dense.compile(loss='categorical_crossentropy', optimizer=RMS, metrics=['accuracy'])

    return model_dense


mat_data = sio.loadmat('F:/transfer code/Tensorflow  Learning/SKNet/datasets/Salinas/Salinas_corrected.mat')
data_IN = mat_data['salinas_corrected']
mat_gt = sio.loadmat('F:/transfer code/Tensorflow  Learning/SKNet/datasets/Salinas/Salinas_gt.mat')
gt_IN = mat_gt['salinas_gt']
print(data_IN.shape)

# new_gt_IN = set_zeros(gt_IN, [result,4,7,9,13,15,16])
new_gt_IN = gt_IN

batch_size = 16
nb_classes = 16
nb_epoch = 200  # 400
img_rows, img_cols = 17, 17  # 27, 27
patience = 200

INPUT_DIMENSION_CONV = 204
INPUT_DIMENSION = 204

# 20%:10%:70% data for training, validation and testing

TOTAL_SIZE = 54129
VAL_SIZE = 5413

TRAIN_SIZE = 21660
TEST_SIZE = TOTAL_SIZE - TRAIN_SIZE
VALIDATION_SPLIT = 0.6
# 0.9  5212
# 0.8  10833
# 0.7  16246
# 0.6  21660
# 0.5  27068

img_channels = 204
PATCH_LENGTH = 8  # Patch_size (13*2+result)*(13*2+result)

data = data_IN.reshape(np.prod(data_IN.shape[:2]), np.prod(data_IN.shape[2:]))
gt = new_gt_IN.reshape(np.prod(new_gt_IN.shape[:2]), )

data = preprocessing.scale(data)

# scaler = preprocessing.MaxAbsScaler()
# data = scaler.fit_transform(data)

data_ = data.reshape(data_IN.shape[0], data_IN.shape[1], data_IN.shape[2])
whole_data = data_
padded_data = zeroPadding.zeroPadding_3D(whole_data, PATCH_LENGTH)

ITER = 1
CATEGORY = 16

train_data = np.zeros((TRAIN_SIZE, 2 * PATCH_LENGTH + 1, 2 * PATCH_LENGTH + 1, INPUT_DIMENSION_CONV))
test_data = np.zeros((TEST_SIZE, 2 * PATCH_LENGTH + 1, 2 * PATCH_LENGTH + 1, INPUT_DIMENSION_CONV))

KAPPA_3D_MSDNet = []
OA_3D_MSDNet = []
AA_3D_MSDNet = []
TRAINING_TIME_3D_MSDNet = []
TESTING_TIME_3D_MSDNet = []
ELEMENT_ACC_3D_MSDNet = np.zeros((ITER, CATEGORY))

# seeds = [1220, 1221, 1222, 1223, 1224, 1225, 1226, 1227, 1228, 1229]

seeds = [1334]

for index_iter in range(ITER):
    print("# %d Iteration" % (index_iter + 1))

    best_weights_MSDNet_path = 'F:/transfer code/Tensorflow  Learning/SKNet/models-sa-densenet-17-415/sa_best_3D_MSDNet_' + str(
        index_iter + 1) + '.hdf5'

    np.random.seed(seeds[index_iter])
    #    train_indices, test_indices = sampleFixNum.samplingFixedNum(TRAIN_NUM, gt)
    train_indices, test_indices = sampling(VALIDATION_SPLIT, gt)

    y_train = gt[train_indices] - 1
    y_train = to_categorical(np.asarray(y_train))

    y_test = gt[test_indices] - 1
    y_test = to_categorical(np.asarray(y_test))

    train_assign = indexToAssignment(train_indices, whole_data.shape[0], whole_data.shape[1], PATCH_LENGTH)
    for i in range(len(train_assign)):
        train_data[i] = selectNeighboringPatch(padded_data, train_assign[i][0], train_assign[i][1], PATCH_LENGTH)

    test_assign = indexToAssignment(test_indices, whole_data.shape[0], whole_data.shape[1], PATCH_LENGTH)
    for i in range(len(test_assign)):
        test_data[i] = selectNeighboringPatch(padded_data, test_assign[i][0], test_assign[i][1], PATCH_LENGTH)

    x_train = train_data.reshape(train_data.shape[0], train_data.shape[1], train_data.shape[2], INPUT_DIMENSION_CONV)
    x_test_all = test_data.reshape(test_data.shape[0], test_data.shape[1], test_data.shape[2], INPUT_DIMENSION_CONV)

    x_val = x_test_all[-VAL_SIZE:]
    y_val = y_test[-VAL_SIZE:]

    x_test = x_test_all[:-VAL_SIZE]
    y_test = y_test[:-VAL_SIZE]

    # SS Residual Network 4 with BN
    model_MSDNet = model_MSDNet()

    # ????????????????????????
    model_MSDNet.load_weights(best_weights_MSDNet_path)

    pred_test = model_MSDNet.predict(
        x_test.reshape(x_test.shape[0], x_test.shape[1], x_test.shape[2], x_test.shape[3], 1)).argmax(axis=1)
    collections.Counter(pred_test)
    gt_test = gt[test_indices] - 1
    overall_acc = metrics.accuracy_score(pred_test, gt_test[:-VAL_SIZE])
    confusion_matrix = metrics.confusion_matrix(pred_test, gt_test[:-VAL_SIZE])
    each_acc, average_acc = averageAccuracy.AA_andEachClassAccuracy(confusion_matrix)
    kappa = metrics.cohen_kappa_score(pred_test, gt_test[:-VAL_SIZE])
    KAPPA_3D_MSDNet.append(kappa)
    OA_3D_MSDNet.append(overall_acc)
    AA_3D_MSDNet.append(average_acc)
    ELEMENT_ACC_3D_MSDNet[index_iter, :] = each_acc

    print("3D MSDNet  finished.")
    print("# %d Iteration" % (index_iter + 1))

modelStatsRecord.outputStats_assess(KAPPA_3D_MSDNet, OA_3D_MSDNet, AA_3D_MSDNet, ELEMENT_ACC_3D_MSDNet,
                                    CATEGORY,
                                    'F:/transfer code/Tensorflow  Learning/SKNet/records-sa-densenet-17-415/IN_test_3D.txt',
                                    'F:/transfer code/Tensorflow  Learning/SKNet/records-sa-densenet-17-415/IN_test_element_3D.txt')
