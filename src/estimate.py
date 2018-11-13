
import json
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import axes3d, Axes3D 
import numpy as np
import pickle
import tensorflow as tf

import densepose_methods as dp_utils
from model import Model


SMPL_MODEL_PATH = '../models/neutral_smpl_with_cocoplus_reg.pkl'
# SMPL_MODEL_PATH = '../models/basicmodel_m_lbs_10_207_0_v1.0.0.pkl'
NUM_SMPL_VERTS = 6890

# coco joints
# 0,  Nose
# 1,  LEye
# 2,  REye
# 3,  LEar
# 4,  REar
# 5,  LShoulder 16
# 6,  RShoulder 17
# 7,  LElbow    18
# 8,  RElbow    19
# 9,  LWrist    20
# 10, RWrist    21
# 11, LHip      1
# 12, RHip      2
# 13, LKnee     4
# 14, Rknee     5
# 15, LAnkle    7
# 16, RAnkle    8
# [ 0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20. 21, 22, 23]
# [-1, 11, 12, -1，13, 14, -1, 15, 16, -1, -1, -1, -1, -1, -1. -1.  5,  6,  7,  8,  9, 10, -1, -1]

def main():

  # read the smpl model.
  # with open('../models/basicmodel_m_lbs_10_207_0_v1.0.0.pkl', 'rb') as f:
  with open(SMPL_MODEL_PATH, 'rb') as f:
    data = pickle.load(f)
    Vertices = data['v_template']  # Loaded vertices of size (6890, 3)
    X,Y,Z = [Vertices[:,0], Vertices[:,1],Vertices[:,2]]
  print("Read model done")
  print("X.sum: %s" % str(np.sum(X)))
  print("Y.sum: %s" % str(np.sum(Y)))
  print("Z.sum: %s" % str(np.sum(Z)))

  DP = dp_utils.DensePoseMethods()
  pkl_file = open('../data/demo_dp_single_ann.pkl', 'rb')
  Demo = pickle.load(pkl_file)

  # collect respective points on SMPL model
  collected_x = np.zeros(Demo['x'].shape)
  collected_y = np.zeros(Demo['x'].shape)
  collected_z = np.zeros(Demo['x'].shape)

  info_list = []
  for i, (ii,uu,vv) in enumerate(zip(Demo['I'],Demo['U'],Demo['V'])):
    # Convert IUV to FBC (faceIndex and barycentric coordinates.)
    FaceIndex,bc1,bc2,bc3 = DP.IUV2FBC(ii,uu,vv)
    # Use FBC to get 3D coordinates on the surface.
    p, info = DP.FBC2PointOnSurface(FaceIndex, bc1,bc2,bc3, Vertices)
    collected_x[i] = p[0]
    collected_y[i] = p[1]
    collected_z[i] = p[2]
    info_list.append(info)

  weight_map = np.zeros([NUM_SMPL_VERTS], dtype=np.float32)
  visible_points2d = np.zeros([NUM_SMPL_VERTS, 2], dtype=np.float32)
  for index_info, x, y in zip(info_list, Demo['x'], Demo['y']):
    (i1, w1), (i2, w2), (i3, w3) = index_info
    weight_map[i1] = w1
    weight_map[i2] = w2
    weight_map[i3] = w3
    visible_points2d[i1, :] = [x, y]
    visible_points2d[i2, :] = [x, y]
    visible_points2d[i3, :] = [x, y]

  weight_map = np.reshape(weight_map, [1, NUM_SMPL_VERTS])
  visible_points2d = np.reshape(visible_points2d, [1, NUM_SMPL_VERTS, 2])

  # load 2d keypoints info
  keypoints_info = json.load(open("../data/icrop.json"))
  kps = keypoints_info["keypoints"]
  kps = kps.reshape([1, -1, 3])
  kps = np.vstack((kps, [0, 0, 0]))
  kp_weights = kps[:, :, 2]
  kps = kps[:, :, :2]

  #  [ 0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20. 21, 22, 23]
  kps_map_coco_to_smpl = [
      -1, 11, 12, -1, 13, 14, -1, 15, 16, -1, -1, -1, -1, -1, -1, -1,  5,  6,  7,  8,  9, 10, -1, -1]

  kps = kps[:, kps_map_coco_to_smpl, :]
  kp_weights = kp_weights[:, kps_map_coco_to_smpl, :]

  model = Model(SMPL_MODEL_PATH)
  (index_map, img_verts, proj_verts_2d_op) = model.build_model()

  with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())

    for var in tf.global_variables():
      var_value = sess.run(var)
      print("name: %s, value.sum: %f, std: %f" % (var.name, np.sum(var_value), np.std(var_value)))

    lps_weights = sess.run(model.smplModel.weights)
    print("lbs_weights.sum: %s" % str(np.sum(lps_weights)))

    def show_step():
      proj_verts_2d, proj_joints_2d, poses, shapes = sess.run(
          [model.proj_verts_2d, model.proj_joints_2d, model.poses, model.shapes])
      X,Y = proj_verts_2d[0, :,0], proj_verts_2d[0, :,1]
      collected_x = np.zeros(len(info_list))
      collected_y = np.zeros(len(info_list))
      for i, index_info in enumerate(info_list):
        (i1, w1), (i2, w2), (i3, w3) = index_info
        collected_x[i] = X[i1]*w1 + X[i2]*w2 + X[i3]*w3
        collected_y[i] = Y[i1]*w1 + Y[i2]*w2 + Y[i3]*w3

      print("poses: %s" % str(poses))
      print("shapes: %s" % str(shapes))
      print("X.sum: %s" % str(np.sum(X)))
      print("Y.sum: %s" % str(np.sum(Y)))
      print("proj_verts_2d.shape:", proj_verts_2d.shape)

      # Visualize the image and collected points.
      fig = plt.figure(figsize=[12,12])
      ax = fig.add_subplot(221)
      ax.imshow(Demo['ICrop'])
      ax.scatter(Demo['x'],Demo['y'],11, np.arange(len(Demo['y'])))
      plt.title('Points on the image')
      ax.axis('equal')
      # ax.axis('off')

      ## Visualize the full body smpl male template model and collected points
      ax = fig.add_subplot(222)
      ax.scatter(X, Y, s=0.02,c='k')
      ax.scatter(collected_x, collected_y, s=25, c=np.arange(len(collected_x)))
      ax.set_xlim([0, 350])
      ax.set_ylim([0, 350])
      ax.invert_yaxis()
      plt.title('Points on the SMPL model')
      plt.show()

      # original picture with 2D keypoints
      ax = fig.add_subplot(223)
      ax.imshow(Demo['ICrop'])
      ax.scatter(kps[0, :, 0], kps[0, :, 0], s=30, c=np.arange(len(kps_map_coco_to_smpl)))
      ax.set_xlim([0, 350])
      ax.set_ylim([0, 350])
      plt.title('2D keypoints on the original image')

      ax = fig.add_subplot(224)
      ax.imshow(Demo['ICrop'])
      ax.scatter(proj_joints_2d[0, :, 0], proj_joints_2d[0, :, 0], s=30, c=np.arange(len(kps_map_coco_to_smpl)))
      ax.set_xlim([0, 350])
      ax.set_ylim([0, 350])
      plt.title('2D keypoints on the smpl model')

    # draw the initial pose
    show_step()

    for step in range(100):
      _, lossVal = sess.run(
          [model.train_op_cams, model.loss_op],
          feed_dict={index_map: weight_map,
                     img_verts: visible_points2d,
                     model.learning_rate: 0.01})
      print("step: %d, loss: %f" % (step, lossVal))
      if step % 24 == 0:
        show_step()

    angle_prior_weights = [4.04 * 1e2, 4.04 * 1e2, 57.4, 4.78]
    steps_in_all = 1000
    for step in range(steps_in_all):
      angle_weight = angle_prior_weights[step // (steps_in_all//len(angle_prior_weights))]
      _, angle_prior_loss,  lossVal = sess.run(
          [model.train_op_poses, model.angle_prior_loss,  model.loss_op],
          feed_dict={index_map: weight_map,
                     img_verts: visible_points2d,
                     model.learning_rate: 0.01,
                     model.angle_prior_weight: angle_weight})
      print("step: %d, loss: %f, angle_prior_loss: %f" % (step, lossVal, angle_prior_loss))

      if step % 100 == 0:
        show_step()


if __name__ == "__main__":
  main()

