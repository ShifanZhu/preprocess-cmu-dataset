#ifndef SE_CORE_CAM_BASE_H
#define SE_CORE_CAM_BASE_H

#include <Eigen/Eigen>
#include <unordered_map>
#include "Utils/cppTypes.h"
#include <opencv2/opencv.hpp>
#include "so3.hpp"
#include "se3.hpp"

namespace se_core {

/**
 * @brief Base pinhole camera model class
 *
 * This is the base class for all our camera models.
 * All these models are pinhole cameras, thus just have standard reprojection logic.
 * See each derived class for detailed examples of each model.
 */
template <typename T>
class CamBase {

public:
  /**
   * @brief Default constructor
   * @param width Width of the camera (raw pixels)
   * @param height Height of the camera (raw pixels)
   */
  CamBase(size_t width, size_t height) : _width(width), _height(height) {
    mapx_ = cv::Mat::zeros(cv::Size(width, height), CV_32FC1);
    mapy_ = cv::Mat::zeros(cv::Size(width, height), CV_32FC1);
    // size_before_ = cv::Size(width-1, height-1);
    size_before_ = cv::Size(width, height);
    size_after_ = cv::Size(width, height);
  }

  virtual ~CamBase() {}

  /**
   * @brief This will set and update the camera calibration values.
   * This should be called on startup for each camera and after update!
   * @param calib Camera calibration information (f_x & f_y & c_x & c_y & k_1 & k_2 & k_3 & k_4)
   */
  virtual void set_value(const DMat<T> &calib) {

    // Assert we are of size eight
    assert(calib.rows() == 9);
    camera_values = calib;

    // Camera matrix
    cv::Matx<T, 3, 3> tempK;
    tempK(0, 0) = calib(0);
    tempK(0, 1) = 0;
    tempK(0, 2) = calib(2);
    tempK(1, 0) = 0;
    tempK(1, 1) = calib(1);
    tempK(1, 2) = calib(3);
    tempK(2, 0) = 0;
    tempK(2, 1) = 0;
    tempK(2, 2) = 1;
    camera_k_OPENCV = tempK;

    // Distortion parameters
    cv::Vec<T, 5> tempD;
    tempD(0) = calib(4);
    tempD(1) = calib(5);
    tempD(2) = calib(6);
    tempD(3) = calib(7);
    tempD(4) = calib(8);
    camera_d_OPENCV = tempD;

    double alpha = 0; // 0 will remove black edges

    camera_k_OPENCV_new = cv::getOptimalNewCameraMatrix(get_K(), 
            camera_d_OPENCV, size_before_, alpha, size_after_, nullptr);
    // CalculatePixelUndistortionMap();
    fx_ = camera_k_OPENCV_new(0, 0);
    fy_ = camera_k_OPENCV_new(1, 1);
    cx_ = camera_k_OPENCV_new(0, 2);
    cy_ = camera_k_OPENCV_new(1, 2);
    fxi_ = 1.0 / fx_;
    fyi_ = 1.0 / fy_;
  }

  void set_depth_K(const Vec4<T> &K) {
    camera_k_depth_OPENCV(0, 0) = K(0);
    camera_k_depth_OPENCV(1, 1) = K(1);
    camera_k_depth_OPENCV(0, 2) = K(2);
    camera_k_depth_OPENCV(1, 2) = K(3);
  }

  // void set_

  void set_mj_depth_parameters(const T& near, const T& far, const T& extent) {
    this->near = near;
    this->far = far;
    this->extent = extent;
    size_before_ = cv::Size(_width-1, _height-1);
    double alpha = 0; // 0 will remove black edges
    camera_k_OPENCV_new = cv::getOptimalNewCameraMatrix(get_K(), 
            camera_d_OPENCV, size_before_, alpha, size_after_, nullptr);
  }

  /**
   * @brief Given a raw uv point, this will undistort it based on the camera matrices into normalized camera coords.
   * @param uv_dist Raw uv coordinate we wish to undistort
   * @return 2d vector of normalized coordinates
   */
  // virtual Eigen::Vector2f undistort_f(const Eigen::Vector2f &uv_dist) = 0;
  virtual Vec2<T> undistort(const Vec2<T> &uv_dist) = 0;
  virtual Vec2<T> undistort_pxl_frame(const Vec2<T> &uv_dist) = 0;

  /**
   * @brief Given a raw uv point, this will undistort it based on the camera matrices into normalized camera coords.
   * @param uv_dist Raw uv coordinate we wish to undistort
   * @return 2d vector of normalized coordinates
   */
  // Eigen::Vector2d undistort_d(const Eigen::Vector2d &uv_dist) {
  //   Eigen::Vector2f ept1, ept2;
  //   ept1 = uv_dist.cast<float>();
  //   ept2 = undistort_f(ept1);
  //   return ept2.cast<double>();
  // }
  // Vec2<T> undistort(const Vec2<T> &uv_dist) {
  //   Vec2<T> ept1, ept2;
  //   ept1 = uv_dist;
  //   ept2 = undistort(ept1);
  //   return ept2;
  // }

  /**
   * @brief Given a raw uv point, this will undistort it based on the camera matrices into normalized camera coords.
   * @param uv_dist Raw uv coordinate we wish to undistort
   * @return 2d vector of normalized coordinates
   */
  // cv::Point2f undistort_cv(const cv::Point2f &uv_dist) {
  //   Eigen::Vector2f ept1, ept2;
  //   ept1 << uv_dist.x, uv_dist.y;
  //   ept2 = undistort_f(ept1);
  //   cv::Point2f pt_out;
  //   pt_out.x = ept2(0);
  //   pt_out.y = ept2(1);
  //   return pt_out;
  // }
  cv::Point_<T> undistort_cv(const cv::Point_<T> &uv_dist) {
    // Eigen::Vector2f ept1, ept2;
    Vec2<T> ept1, ept2;
    ept1 << uv_dist.x, uv_dist.y;
    ept2 = undistort(ept1);
    cv::Point_<T> pt_out;
    pt_out.x = ept2(0);
    pt_out.y = ept2(1);
    return pt_out;
  }

  cv::Point_<T> undistort_cv_pxl_frame(const cv::Point_<T> &uv_dist) {
    // Eigen::Vector2f ept1, ept2;
    Vec2<T> ept1, ept2;
    ept1 << uv_dist.x, uv_dist.y;
    ept2 = undistort_pxl_frame(ept1);
    cv::Point_<T> pt_out;
    pt_out.x = ept2(0);
    pt_out.y = ept2(1);
    return pt_out;
  }

  // cv::Point_<T> undistort_cv_pxl(const cv::Point_<T> &uv_dist) {
  //   int u = static_cast<int>(uv_dist.x);
  //   int v = static_cast<int>(uv_dist.y);

  //   // Ensure v is within bounds to avoid accessing invalid memory
  //   if (v < 0 || v >= mapx_.rows || u < 0 || u >= mapx_.cols) {
  //     return cv::Point_<T>(0, 0);
  //   }

  //   // Get the undistorted coordinates
  //   T undist_x = static_cast<T>(mapx_.template ptr<float>(v)[u]);
  //   T undist_y = static_cast<T>(mapy_.template ptr<float>(v)[u]);
  //   // std::cout << "uv, undist_x, undist_y: " << u << " " << v << " " << undist_x << " " << undist_y
  //   //           << std::endl; 

  //   // Validate undistorted pixel coordinates
  //   if (undist_x >= 0 && undist_y >= 0 && undist_x < _width && undist_y < _height) {
  //     return cv::Point_<T>(undist_x, undist_y);
  //   } else {
  //     return cv::Point_<T>(0, 0);
  //   }
  // }

  // Vec2<T> undistort_cv_pxl(const Vec2<T>& pxl) {
  //   int u = pxl[0];
  //   int v = pxl[1];
  //   // LOG(INFO)<<"uv = "<<u<<" "<<v<<" "<<pxl.transpose();
  //   Vec2<T> pxl_un(double(mapx_.ptr<float>(v)[u]), double(mapy_.ptr<float>(v)[u]));
  //   if (pxl_un[0]>=0 && pxl_un[1]>=0 && pxl_un[0]<_width&&pxl_un[1]<_height) {
  //       return pxl_un;
  //   } else {
  //       return Vec2<T>(0, 0);
  //   }
  // }


  // void CalculatePixelUndistortionMap() {
  //   std::cout << "Start to set pixel undistortion map using opencv undistort points" << std::endl;
  //   // Intrinsic camera matrix
  //   // cv::Mat K_old = (cv::Mat_<T>(3, 3) << camera_k_OPENCV(0, 0), camera_k_OPENCV(0, 1), camera_k_OPENCV(0, 2),
  //   //     camera_k_OPENCV(1, 0), camera_k_OPENCV(1, 1), camera_k_OPENCV(1, 2), 0.0, 0.0, 1.0);
  //   // cv::Mat D_old = (cv::Mat_<T>(5, 1) << camera_d_OPENCV(0), camera_d_OPENCV(1), camera_d_OPENCV(2), camera_d_OPENCV(3), -0.0220816992223263);
  //   cv::Size imageSize(w(), h());
  //   const int alpha = 0; // 0: remove black edge
  //   cv::Mat K_new = cv::getOptimalNewCameraMatrix(get_K(), get_D(), imageSize, alpha, imageSize, 0);
    
  //   std::vector<cv::Point2f> distortedPoint;
  //   std::vector<cv::Point2f> undistortedPoint;
  //   for (size_t u = 0; u < _width; u++) {
  //     for (size_t v = 0; v < _height; v++) {
  //       cv::Point2f pt = cv::Point2f(u, v);
  //       distortedPoint.push_back(pt);
  //     }
  //   }
  //   // Undistort the point
  //   cv::undistortPoints(distortedPoint, undistortedPoint, get_K(), get_D());
  //   std::cout << "distortedPoint[0]: " << distortedPoint[0] << std::endl;
  //   std::cout << "undistortedPoint[0]: " << undistortedPoint[0] << std::endl;
  //   std::cout << "K_new: " << get_new_K() << std::endl;
  //   std::cout << "K_old: " << get_K() << std::endl;
  //   std::cout << "D_old: " << get_D() << std::endl;

  //   int64_t cnt = 0;
  //   for (size_t v = 0; v < _height; v++) {
  //     for (size_t u = 0; u < _width; u++) {
  //       if (cnt >= undistortedPoint.size()) {
  //         std::cerr << "Error: undistortedPoint out of bounds at index " << cnt << std::endl;
  //         return;
  //       }
  //       mapx_.template ptr<float>(v)[u] = undistortedPoint[cnt].x;
  //       mapy_.template ptr<float>(v)[u] = undistortedPoint[cnt].y;
  //       // if (v % 20 == 0 && u % 20 == 0) {
  //       //   std::cout << "uv: " << u << " " << v << " " << mapx_.template ptr<float>(v)[u] << " " 
  //       //   << mapy_.template ptr<float>(v)[u] << " " << undistortedPoint[cnt].x << " " << undistortedPoint[cnt].y << std::endl;
  //       // }
  //       cnt++;
  //     }
  //   }

  //   std::cout<<"Set pixel undistortion map finished" << std::endl;
  //   return;
  // }

  /**
   * @brief Given a normalized uv coordinate this will distort it to the raw image plane
   * @param uv_norm Normalized coordinates we wish to distort
   * @return 2d vector of raw uv coordinate
   */
  // virtual Eigen::Vector2f distort_f(const Eigen::Vector2f &uv_norm) = 0;
  virtual Vec2<T> distort(const Vec2<T> &uv_norm) = 0;

  /**
   * @brief Given a normalized uv coordinate this will distort it to the raw image plane
   * @param uv_norm Normalized coordinates we wish to distort
   * @return 2d vector of raw uv coordinate
   */
  // Eigen::Vector2d distort_d(const Eigen::Vector2d &uv_norm) {
  //   Eigen::Vector2f ept1, ept2;
  //   ept1 = uv_norm.cast<float>();
  //   ept2 = distort_f(ept1);
  //   return ept2.cast<double>();
  // }

  // Vec2<T> distort(const Vec2<T> &uv_norm) {
  //   Vec2<T> ept1, ept2;
  //   ept1 = uv_norm;
  //   ept2 = distort(ept1);
  //   return ept2;
  // }

  /**
   * @brief Given a normalized uv coordinate this will distort it to the raw image plane
   * @param uv_norm Normalized coordinates we wish to distort
   * @return 2d vector of raw uv coordinate
   */
  // cv::Point2f distort_cv(const cv::Point2f &uv_norm) {
  //   Eigen::Vector2f ept1, ept2;
  //   ept1 << uv_norm.x, uv_norm.y;
  //   ept2 = distort_f(ept1);
  //   cv::Point2f pt_out;
  //   pt_out.x = ept2(0);
  //   pt_out.y = ept2(1);
  //   return pt_out;
  // }

  cv::Point_<T> distort_cv(const cv::Point_<T> &uv_norm) {
    Eigen::Vector2f ept1, ept2;
    ept1 << uv_norm.x, uv_norm.y;
    ept2 = distort(ept1);
    cv::Point_<T> pt_out;
    pt_out.x = ept2(0);
    pt_out.y = ept2(1);
    return pt_out;
  }

  /**
   * @brief Computes the derivative of raw distorted to normalized coordinate.
   * @param uv_norm Normalized coordinates we wish to distort
   * @param H_dz_dzn Derivative of measurement z in respect to normalized
   * @param H_dz_dzeta Derivative of measurement z in respect to intrinic parameters
   */
  virtual void compute_distort_jacobian(const Vec2<T> &uv_norm, DMat<T> &H_dz_dzn, DMat<T> &H_dz_dzeta) = 0;


  T get_depth(const cv::Mat& depth_img, size_t u, size_t v) {
    constexpr T scale = 0.001;  // Convert depth values to meters

    // Bounds check
    if (u >= depth_img.cols || v >= depth_img.rows) {
      return -1.0;
    }

    // Direct pointer access (SIMD optimized)
    const ushort* row_ptr = depth_img.ptr<ushort>(v);
    T best_depth = row_ptr[u] * scale;

    // // If depth is valid, return immediately
    // if (d > 0.1) {
    //     return d;
    // }

    // Define search pattern (left, up, right, down)
    static const int dx[4] = {-2, 0, 2, 0};
    static const int dy[4] = {0, -2, 0, 2};

    // T best_depth = std::numeric_limits<T>::max();  // Initialize to max value

    // Search in 4-neighborhood
    for (int i = 0; i < 4; i++) {
      int new_u = u + dx[i];
      int new_v = v + dy[i];

      // Ensure within bounds
      if (new_u >= 0 && new_u < depth_img.cols && new_v >= 0 && new_v < depth_img.rows) {
        const ushort* neighbor_ptr = depth_img.ptr<ushort>(new_v);
        T neighbor_d = neighbor_ptr[new_u] * scale;

        // Select the smallest valid depth in range (0.4m - 50m)
        if (neighbor_d > 0.05 && neighbor_d < 50) {
          best_depth = std::min(best_depth, neighbor_d);
        }
      }
    }

    // If no valid depth was found, return -1.0
    return (best_depth <= 0.0) ? -1.0 : best_depth;
  }

  T get_depth_mj(const cv::Mat& depth_img, size_t x, size_t y) {
    // Bounds check
    if (x >= depth_img.cols || y >= depth_img.rows) {
      return -1.0;
    }

    // Compute depth at (x, y)
    // T best_depth = static_cast<T>((this->near * this->far) / 
    //     (this->far + this->near - depth_img.at<float>(y, x) * (this->far - this->near)));
    T best_depth = static_cast<T>((this->near) / 
        (1.0 - depth_img.at<float>(y, x) * (1.0 - this->near/this->far)));
    // Define search pattern (left, up, right, down)
    static const int dx[8] = {-2, 0, 2, 0, -4, 0, 4, 0};
    static const int dy[8] = {0, -2, 0, 2, 0, -4, 0, 4};

    // Search for the smallest valid depth in the 4-neighborhood
    for (int i = 0; i < 8; i++) {
      int new_x = x + dx[i];
      int new_y = y + dy[i];

      // Ensure within bounds
      if (new_x >= 0 && new_x < depth_img.cols && new_y >= 0 && new_y < depth_img.rows) {
        T neighbor_depth = static_cast<T>((this->near) / 
              (1.0 - depth_img.at<float>(new_y, new_x) * (1.0 - this->near/this->far)));

        // Select the smallest valid depth in range (0.4m - 50m)
        if (neighbor_depth > 0.05 && neighbor_depth < 50) {
          best_depth = std::min(best_depth, neighbor_depth);
        }
      }
    }

    // If best_depth is outside the valid range, return -1.0
    return (best_depth > 0.05 && best_depth < 50) ? best_depth : -1.0;
  }


  /// Gets the complete intrinsic vector
  DMat<T> get_value() { return camera_values; }

  /// Gets the camera matrix
  cv::Matx33d get_K() { return camera_k_OPENCV; }
  cv::Matx33d get_K_depth() { return camera_k_depth_OPENCV; }
  cv::Matx33d get_new_K() { return camera_k_OPENCV_new; }

  /// Gets the camera distortion
  cv::Vec<double, 5> get_D() { return camera_d_OPENCV; }

  /// Gets the width of the camera images
  size_t w() { return _width; }

  /// Gets the height of the camera images
  size_t h() { return _height; }

  const Sophus::SE3<T> GetDepthtoEvent() {
    return depth_to_event_;
  }

  const Sophus::SE3<T> GetDepthtoRGB() {
    return depth_to_rgb_;
  }

  const Sophus::SE3<T> GetIMUtoRGB() {
    return imu_to_rgb_;
  }

  const Sophus::SE3<T> GetRGBtoEvent() {
    return rgb_to_event_;
  }

  void SetDepthtoEvent(Sophus::SE3<T> ex_pose) {
    depth_to_event_ = ex_pose;
  }

  void SetRGBtoEvent(Sophus::SE3<T> ex_pose) {
    rgb_to_event_ = ex_pose;
  }

  void SetDepthtoRGB(Sophus::SE3<T> ex_pose) {
    depth_to_rgb_ = ex_pose;
  }

  void SetIMUtoRGB(Sophus::SE3<T> ex_pose) {
    imu_to_rgb_ = ex_pose;
  }

  inline Vec3<T> camera2camera(const Vec3<T>& p_c, const Sophus::SE3<T>& T_c_c) {
    return T_c_c * p_c;
  }

  inline Vec2<T> camera2pixel(Vec3<T> &p_c) {
    T zi = 1.0 / p_c(2, 0);
    return Vec2<T>(fx_ * p_c(0, 0) * zi + cx_, fy_ * p_c(1, 0) * zi + cy_);
  }

  inline Vec3<T> pixel2camera(const Vec2<T>& p_p, const T& depth = 1.) {
    return Vec3<T>(
      (p_p(0, 0) - cx_) * depth * fxi_,
      (p_p(1, 0) - cy_) * depth * fyi_,
      depth
    );
  }

  inline Vec3<T> pixel2camera(const Vec2<T>& p_p) {
    return Vec3<T>(
      (p_p(0, 0) - cx_) * fxi_,
      (p_p(1, 0) - cy_) * fyi_,
      1.
    );
  }

  inline Vec2<T> pixel2pixel(const Vec3<T>& pxl_3d, const Mat3<T>& KRKi, const Vec3<T>& Kt, const T& depth_inv) {
    Vec3<T> ptp2 = KRKi * pxl_3d + Kt * depth_inv;
    T id = 1.0/ptp2[2];
    return Vec2<T>(ptp2[0]*id, ptp2[1]*id);
  }

protected:
  // Cannot construct the base camera class, needs a distortion model
  CamBase() = default;

  /// Raw set of camera intrinic values (f_x & f_y & c_x & c_y & k_1 & k_2 & k_3 & k_4)
  DMat<T> camera_values;

  /// Camera intrinsics in OpenCV format
  cv::Matx33d camera_k_OPENCV;
  cv::Matx33d camera_k_depth_OPENCV;
  cv::Matx33d camera_k_OPENCV_new; // new camera intrinsics after undistortion

  /// Camera distortion in OpenCV format
  cv::Vec<double, 5> camera_d_OPENCV;

  /// Width of the camera (raw pixels)
  size_t _width;

  /// Height of the camera (raw pixels)
  size_t _height;

  cv::Mat mapx_;
  cv::Mat mapy_;
  cv::Size size_before_;
  cv::Size size_after_;

  Sophus::SE3<T> robot_to_imu_, imu_to_marker_, imu_to_lidar_;
  Sophus::SE3<T> depth_to_event_;
  Sophus::SE3<T> depth_to_rgb_;
  Sophus::SE3<T> rgb_to_event_;
  Sophus::SE3<T> imu_to_rgb_;
  // Mujoco sim parameters to get depth
  T near, far, extent;
  T fx_ = 0, fy_ = 0, cx_ = 0, cy_ = 0;
  T fxi_ = 0, fyi_ = 0;
};

} // namespace se_core

#endif /* SE_CORE_CAM_BASE_H */