#ifndef SE_CORE_CAM_BASE_H
#define SE_CORE_CAM_BASE_H

#include <Eigen/Eigen>
#include <unordered_map>
#include <opencv2/opencv.hpp>
#include "so3.hpp"
#include "Sophus::SE3<T>.hpp"
#include "Utils/cppTypes.h"
#include "CamEqui.h"
#include "CamRadtan.h"

namespace se_core {

Mat3<T> cvMat_to_Mat3(const cv::Matx33d &cv_mat) {
  Mat3<T> mat;
  mat(0, 0) = cv_mat(0, 0);
  mat(0, 1) = cv_mat(0, 1);
  mat(0, 2) = cv_mat(0, 2);
  mat(1, 0) = cv_mat(1, 0);
  mat(1, 1) = cv_mat(1, 1);
  mat(1, 2) = cv_mat(1, 2);
  mat(2, 0) = cv_mat(2, 0);
  mat(2, 1) = cv_mat(2, 1);
  mat(2, 2) = cv_mat(2, 2);
  return mat;
}
  /**
   * Get depth image that is already projected to RGB camera frame
   * Get depth image that is already projected to event camera frame
   * Note: both input output image are ushort type
   */
template <typename T>
bool DepthImageProjectToEventCameraAndRGBCameraPxl2Pxl(
  std::unordered_map<size_t, std::shared_ptr<se_core::CamBase<T>>>
      &camera_intrinsics,
     const cv::Mat &depth_img,
    cv::Mat &eve_depth_img, cv::Mat &rgb_depth_img) {
  int h_rgbd = camera_intrinsics.at(0)->h(), w_rgbd = camera_intrinsics.at(0)->w();
  int h_event = camera_intrinsics.at(1)->h(), w_event = camera_intrinsics.at(1)->w();
  Mat3<T> Ki = cvMat_to_Mat3(camera_intrinsics.at(0)->get_K_depth().inverse());
  Mat3<T> K_event = cvMat_to_Mat3(camera_intrinsics.at(0)->get_K());
  Mat3<T> K_rgbd = cvMat_to_Mat3(camera_intrinsics.at(0)->get_K());
  Sophus::SE3<T> depth_to_event = camera_intrinsics.at(0)->GetDepthtoEvent();
  Sophus::SE3<T> depth_to_rgb = camera_intrinsics.at(0)->GetDepthtoRGB();
  Mat3<T> KRKi_event = K_event * depth_to_event.rotationMatrix() * Ki;
  Mat3<T> KRKi_rgbd = K_rgbd * depth_to_rgb.rotationMatrix() * Ki;
  Vec3<T> Kt_event = K_event * depth_to_event.translation();
  Vec3<T> Kt_rgbd = K_rgbd * depth_to_rgb.translation();

  // cv::Mat output_data = cv::Mat::zeros(cam_out->height_, cam_out->width_,
  // CV_16UC1); #pragma omp parallel for schedule(dynamic) #pragma omp parallel
  // for num_threads(24)
  for (int y = 0; y < h_rgbd; ++y) {
    for (int x = 0; x < w_rgbd; ++x) {
      double d = depth_img.at<ushort>(y, x) * 0.001;
      double di = 1.0 / d;
      // Skip over depth pixels with the value of zero, we have no depth data so
      // we will not write anything into our aligned images
      if (d > 0.1 && d < 50) {
        // Map the top-left corner of the depth pixel onto the other image
        // Vec2 pt_tl(x-0.5f, y-0.5f);
        Vec3<T> pt_tl_3(x - 0.5, y - 0.5, 1.);
        // Vec3<T> pt_c_tl = camera_intrinsics.at(0)->pixel2depthcamera(pt_tl, d);
        // Vec3<T> pt_new_event_tl = camera_intrinsics.at(0)->camera2camera(pt_c_tl,
        // depth_to_event); Vec3<T> pt_new_rgb_tl =
        // camera_intrinsics.at(0)->camera2camera(pt_c_tl, depth_to_rgb); Vec2
        // pxl_new_event_tl = camera_intrinsics.at(1)->camera2pixel(pt_new_event_tl); Vec2
        // pxl_new_rgb_tl = camera_intrinsics.at(0)->camera2pixel(pt_new_rgb_tl);
        Vec2 pxl_new_event_tl =
            camera_intrinsics.at(1)->pixel2pixel(pt_tl_3, KRKi_event, Kt_event, di);
        Vec2 pxl_new_rgbd_tl =
            camera_intrinsics.at(1)->pixel2pixel(pt_tl_3, KRKi_rgbd, Kt_rgbd, di);
        const int pxl_new_event_u_int_tl =
            static_cast<int>(pxl_new_event_tl[0] + 0.5);
        const int pxl_new_event_v_int_tl =
            static_cast<int>(pxl_new_event_tl[1] + 0.5);
        const int pxl_new_rgb_u_int_tl =
            static_cast<int>(pxl_new_rgbd_tl[0] + 0.5);
        const int pxl_new_rgb_v_int_tl =
            static_cast<int>(pxl_new_rgbd_tl[1] + 0.5);

        // Map the bottom-right corner of the depth pixel onto the other image
        // Vec2 pt_br(x+0.5f, y+0.5f);
        Vec3<T> pt_br_3(x + 0.5, y + 0.5, 1.);
        // Vec3<T> pt_c_br = camera_intrinsics.at(0)->pixel2depthcamera(pt_br, d);
        // Vec3<T> pt_new_event_br = camera_intrinsics.at(0)->camera2camera(pt_c_br,
        // depth_to_event); Vec3<T> pt_new_rgb_br =
        // camera_intrinsics.at(0)->camera2camera(pt_c_br, depth_to_rgb); Vec2
        // pxl_new_event_br = camera_intrinsics.at(1)->camera2pixel(pt_new_event_br); Vec2
        // pxl_new_rgbd_br = camera_intrinsics.at(0)->camera2pixel(pt_new_rgb_br);
        Vec2 pxl_new_event_br =
            camera_intrinsics.at(1)->pixel2pixel(pt_br_3, KRKi_event, Kt_event, di);
        Vec2 pxl_new_rgbd_br =
            camera_intrinsics.at(1)->pixel2pixel(pt_br_3, KRKi_rgbd, Kt_rgbd, di);
        const int pxl_new_event_u_int_br =
            static_cast<int>(pxl_new_event_br[0] + 0.5);
        const int pxl_new_event_v_int_br =
            static_cast<int>(pxl_new_event_br[1] + 0.5);
        const int pxl_new_rgb_u_int_br =
            static_cast<int>(pxl_new_rgbd_br[0] + 0.5);
        const int pxl_new_rgb_v_int_br =
            static_cast<int>(pxl_new_rgbd_br[1] + 0.5);
        if (pxl_new_rgb_u_int_tl < 0 || pxl_new_rgb_v_int_tl < 0 ||
            pxl_new_rgb_u_int_br >= w_rgbd || pxl_new_rgb_v_int_br >= h_rgbd) {
        } else {
          // Transfer between the depth pixels and the pixels inside the
          // rectangle on the other image
          for (int pxl_y = pxl_new_rgb_v_int_tl; pxl_y <= pxl_new_rgb_v_int_br;
              ++pxl_y) {
            for (int pxl_x = pxl_new_rgb_u_int_tl;
                pxl_x <= pxl_new_rgb_u_int_br; ++pxl_x) {
              rgb_depth_img.at<ushort>(pxl_y * w_rgbd + pxl_x) =
                  rgb_depth_img.at<ushort>(pxl_y * w_rgbd + pxl_x) ? std::min((int)(rgb_depth_img.at<ushort>(pxl_y * w_rgbd +
                                                pxl_x)), (int)depth_img.at<ushort>(y, x)) : depth_img.at<ushort>(y, x);
            }
          }
        }

        if (pxl_new_event_u_int_tl < 0 || pxl_new_event_v_int_tl < 0 ||
            pxl_new_event_u_int_br >= w_event ||
            pxl_new_event_v_int_br >= h_event) {
        } else {
          // Transfer between the depth pixels and the pixels inside the
          // rectangle on the other image
          for (int pxl_y = pxl_new_event_v_int_tl;
              pxl_y <= pxl_new_event_v_int_br; ++pxl_y) {
            for (int pxl_x = pxl_new_event_u_int_tl;
                pxl_x <= pxl_new_event_u_int_br; ++pxl_x) {
              eve_depth_img.at<ushort>(pxl_y * w_event + pxl_x) =
                  eve_depth_img.at<ushort>(pxl_y * w_event + pxl_x)
                      ? std::min((int)(eve_depth_img.at<ushort>(
                                    pxl_y * w_event + pxl_x)),
                                (int)depth_img.at<ushort>(y, x))
                      : depth_img.at<ushort>(y, x);
            }
          }
        }
      }
    }
  }
  return true;
  }

} // namespace se_core

#endif /* SE_CORE_CAM_BASE_H */