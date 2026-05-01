#ifndef SE_CORE_CAM_RADTAN_H
#define SE_CORE_CAM_RADTAN_H

#include "CamBase.h"
#include <glog/logging.h>

namespace se_core {

/**
 * @brief Radial-tangential / Brown–Conrady model pinhole camera model class
 *
 * To calibrate camera intrinsics, we need to know how to map our normalized coordinates
 * into the raw pixel coordinates on the image plane. We first employ the radial distortion
 * as in [OpenCV model](https://docs.opencv.org/3.4/da/d54/group__imgproc__transform.html#details):
 *
 * To equate this camera class to Kalibr's models, this is what you would use for `pinhole-radtan`.
 *
 */
template <typename T>
class CamRadtan : public CamBase<T> {

public:
  /**
   * @brief Default constructor
   * @param width Width of the camera (raw pixels)
   * @param height Height of the camera (raw pixels)
   */
  CamRadtan(size_t width, size_t height) : CamBase<T>(width, height) {}

  ~CamRadtan() {}

  /**
   * @brief Given a raw uv point, this will undistort it based on the camera matrices into normalized camera coords.
   * @param uv_dist Raw uv coordinate we wish to undistort
   * @return 2d vector of normalized coordinates
   */
  // Eigen::Vector2f undistort_f(const Eigen::Vector2f &uv_dist) override {

  //   // Determine what camera parameters we should use
  //   cv::Matx33d camK = this->camera_k_OPENCV;
  //   cv::Vec4d camD = this->camera_d_OPENCV;

  //   // Convert to opencv format
  //   cv::Mat mat(1, 2, CV_32F);
  //   mat.at<float>(0, 0) = uv_dist(0);
  //   mat.at<float>(0, 1) = uv_dist(1);
  //   mat = mat.reshape(2); // Nx1, 2-channel

  //   // Undistort it!
  //   cv::undistortPoints(mat, mat, camK, camD);

  //   // Construct our return vector
  //   Eigen::Vector2f pt_out;
  //   mat = mat.reshape(1); // Nx2, 1-channel
  //   pt_out(0) = mat.at<float>(0, 0);
  //   pt_out(1) = mat.at<float>(0, 1);
  //   return pt_out;
  // }


  Vec2<T> undistort(const Vec2<T> &uv_dist) override {

    // Determine what camera parameters we should use
    cv::Matx<T, 3, 3> camK = this->camera_k_OPENCV;
    cv::Vec<T, 5> camD = this->camera_d_OPENCV;

    // Convert point to opencv format
    cv::Mat mat(1, 2, (std::is_same<T, float>::value) ? CV_32F : CV_64F);
    mat.at<T>(0, 0) = uv_dist(0);
    mat.at<T>(0, 1) = uv_dist(1);
    mat = mat.reshape(2); // Nx1, 2-channel

    // Undistort it!
    cv::undistortPoints(mat, mat, camK, camD);

    // Construct our return vector
    Vec2<T> pt_out;
    mat = mat.reshape(1); // Nx2, 1-channel
    pt_out(0) = mat.at<T>(0, 0);
    pt_out(1) = mat.at<T>(0, 1);
    return pt_out;
  }

  Vec2<T> undistort_pxl_frame(const Vec2<T> &uv_dist) override {

    // Determine what camera parameters we should use
    // cv::Matx<T, 3, 3> camK = this->camera_k_OPENCV;
    // cv::Vec<T, 4> camD = this->camera_d_OPENCV;
    // std::cout << "camK: \n" << this->camK << std::endl;
    // std::cout << "camD: \n" << this->camD << std::endl;


    // Convert point to opencv format
    // cv::Mat mat(1, 2, (std::is_same<T, float>::value) ? CV_32F : CV_64F);
    // mat.at<T>(0, 0) = uv_dist(0);
    // mat.at<T>(0, 1) = uv_dist(1);
    // mat = mat.reshape(2); // Nx1, 2-channel
    std::vector<cv::Point_<T>> points = {cv::Point_<T>(uv_dist(0), uv_dist(1))};
    std::vector<cv::Point_<T>> undistortedPoints;
    // LOG(INFO) << "points: " << points[0].x << " " << points[0].y;
    // Undistort it!
    cv::undistortPoints(points, undistortedPoints, this->get_K(), this->get_D());
    // LOG(INFO) << "K: "<< this->get_K();
    // LOG(INFO) << "D: "<< this->get_D();
    // LOG(INFO) << "undist points: " << undistortedPoints[0].x << " " << undistortedPoints[0].y << std::endl;

    // Construct our return vector
    Vec2<T> pt_out;
    // mat = mat.reshape(1); // Nx2, 1-channel
    // std::cout << "camera_k_OPENCV_new: " << this->camera_k_OPENCV_new << std::endl;
    pt_out(0) = this->camera_k_OPENCV_new(0, 0) * undistortedPoints[0].x + this->camera_k_OPENCV_new(0, 2);  // x' = fx * x + cx
    pt_out(1) = this->camera_k_OPENCV_new(1, 1) * undistortedPoints[0].y + this->camera_k_OPENCV_new(1, 2);  // y' = fy * y + cy
    // LOG(INFO) << "rgb_new_k: " << this->camera_k_OPENCV_new;
    // LOG(INFO) << "pt_out: " << pt_out.transpose();
    // std::cout << "pt_cout: " << pt_out << std::endl;

    return pt_out;
  }

  /**
   * @brief Given a normalized uv coordinate this will distort it to the raw image plane
   * @param uv_norm Normalized coordinates we wish to distort
   * @return 2d vector of raw uv coordinate
   */
  // Eigen::Vector2f distort_f(const Eigen::Vector2f &uv_norm) override {

  //   // Get our camera parameters
  //   DMat<T> cam_d = this->camera_values;

  //   // Calculate distorted coordinates for radial
  //   double r = std::sqrt(uv_norm(0) * uv_norm(0) + uv_norm(1) * uv_norm(1));
  //   double r_2 = r * r;
  //   double r_4 = r_2 * r_2;
  //   double x1 = uv_norm(0) * (1 + cam_d(4) * r_2 + cam_d(5) * r_4) + 2 * cam_d(6) * uv_norm(0) * uv_norm(1) +
  //               cam_d(7) * (r_2 + 2 * uv_norm(0) * uv_norm(0));
  //   double y1 = uv_norm(1) * (1 + cam_d(4) * r_2 + cam_d(5) * r_4) + cam_d(6) * (r_2 + 2 * uv_norm(1) * uv_norm(1)) +
  //               2 * cam_d(7) * uv_norm(0) * uv_norm(1);

  //   // Return the distorted point
  //   Eigen::Vector2f uv_dist;
  //   uv_dist(0) = (float)(cam_d(0) * x1 + cam_d(2));
  //   uv_dist(1) = (float)(cam_d(1) * y1 + cam_d(3));
  //   return uv_dist;
  // }



  Vec2<T> distort(const Vec2<T> &uv_norm) override {

    // Get our camera parameters
    DMat<T> cam_d = this->camera_values;

    // Calculate distorted coordinates for radial
    T r = std::sqrt(uv_norm(0) * uv_norm(0) + uv_norm(1) * uv_norm(1));
    T r_2 = r * r;
    T r_4 = r_2 * r_2;
    T x1 = uv_norm(0) * (1 + cam_d(4) * r_2 + cam_d(5) * r_4) + 2 * cam_d(6) * uv_norm(0) * uv_norm(1) +
                cam_d(7) * (r_2 + 2 * uv_norm(0) * uv_norm(0));
    T y1 = uv_norm(1) * (1 + cam_d(4) * r_2 + cam_d(5) * r_4) + cam_d(6) * (r_2 + 2 * uv_norm(1) * uv_norm(1)) +
                2 * cam_d(7) * uv_norm(0) * uv_norm(1);

    // Return the distorted point
    Vec2<T> uv_dist;
    uv_dist(0) = (T)(cam_d(0) * x1 + cam_d(2));
    uv_dist(1) = (T)(cam_d(1) * y1 + cam_d(3));
    return uv_dist;
  }

  /**
   * @brief Computes the derivative of raw distorted to normalized coordinate.
   * @param uv_norm Normalized coordinates we wish to distort
   * @param H_dz_dzn Derivative of measurement z in respect to normalized
   * @param H_dz_dzeta Derivative of measurement z in respect to intrinic parameters
   */
  void compute_distort_jacobian(const Vec2<T> &uv_norm, DMat<T> &H_dz_dzn, DMat<T> &H_dz_dzeta) override {

    // Get our camera parameters
    DMat<T> cam_d = this->camera_values;

    // Calculate distorted coordinates for radial
    T r = std::sqrt(uv_norm(0) * uv_norm(0) + uv_norm(1) * uv_norm(1));
    T r_2 = r * r;
    T r_4 = r_2 * r_2;

    // Jacobian of distorted pixel to normalized pixel
    H_dz_dzn = DMat<T>::Zero(2, 2);
    T x = uv_norm(0);
    T y = uv_norm(1);
    T x_2 = uv_norm(0) * uv_norm(0);
    T y_2 = uv_norm(1) * uv_norm(1);
    T x_y = uv_norm(0) * uv_norm(1);
    H_dz_dzn(0, 0) = cam_d(0) * ((1 + cam_d(4) * r_2 + cam_d(5) * r_4) + (2 * cam_d(4) * x_2 + 4 * cam_d(5) * x_2 * r_2) +
                                 2 * cam_d(6) * y + (2 * cam_d(7) * x + 4 * cam_d(7) * x));
    H_dz_dzn(0, 1) = cam_d(0) * (2 * cam_d(4) * x_y + 4 * cam_d(5) * x_y * r_2 + 2 * cam_d(6) * x + 2 * cam_d(7) * y);
    H_dz_dzn(1, 0) = cam_d(1) * (2 * cam_d(4) * x_y + 4 * cam_d(5) * x_y * r_2 + 2 * cam_d(6) * x + 2 * cam_d(7) * y);
    H_dz_dzn(1, 1) = cam_d(1) * ((1 + cam_d(4) * r_2 + cam_d(5) * r_4) + (2 * cam_d(4) * y_2 + 4 * cam_d(5) * y_2 * r_2) +
                                 2 * cam_d(7) * x + (2 * cam_d(6) * y + 4 * cam_d(6) * y));

    // Calculate distorted coordinates for radtan
    T x1 = uv_norm(0) * (1 + cam_d(4) * r_2 + cam_d(5) * r_4) + 2 * cam_d(6) * uv_norm(0) * uv_norm(1) +
                cam_d(7) * (r_2 + 2 * uv_norm(0) * uv_norm(0));
    T y1 = uv_norm(1) * (1 + cam_d(4) * r_2 + cam_d(5) * r_4) + cam_d(6) * (r_2 + 2 * uv_norm(1) * uv_norm(1)) +
                2 * cam_d(7) * uv_norm(0) * uv_norm(1);

    // Compute the Jacobian in respect to the intrinsics
    H_dz_dzeta = DMat<T>::Zero(2, 8);
    H_dz_dzeta(0, 0) = x1;
    H_dz_dzeta(0, 2) = 1;
    H_dz_dzeta(0, 4) = cam_d(0) * uv_norm(0) * r_2;
    H_dz_dzeta(0, 5) = cam_d(0) * uv_norm(0) * r_4;
    H_dz_dzeta(0, 6) = 2 * cam_d(0) * uv_norm(0) * uv_norm(1);
    H_dz_dzeta(0, 7) = cam_d(0) * (r_2 + 2 * uv_norm(0) * uv_norm(0));
    H_dz_dzeta(1, 1) = y1;
    H_dz_dzeta(1, 3) = 1;
    H_dz_dzeta(1, 4) = cam_d(1) * uv_norm(1) * r_2;
    H_dz_dzeta(1, 5) = cam_d(1) * uv_norm(1) * r_4;
    H_dz_dzeta(1, 6) = cam_d(1) * (r_2 + 2 * uv_norm(1) * uv_norm(1));
    H_dz_dzeta(1, 7) = 2 * cam_d(1) * uv_norm(0) * uv_norm(1);
  }
};

} // namespace se_core

#endif /* SE_CORE_CAM_RADTAN_H */