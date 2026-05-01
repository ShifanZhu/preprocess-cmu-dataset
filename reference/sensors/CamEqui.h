#ifndef SE_CORE_CAM_EQUI_H
#define SE_CORE_CAM_EQUI_H

#include "CamBase.h"

namespace se_core {

/**
 * @brief Fisheye / equadistant model pinhole camera model class
 *
 * As fisheye or wide-angle lenses are widely used in practice, we here provide mathematical derivations
 * of such distortion model as in [OpenCV fisheye](https://docs.opencv.org/3.4/db/d58/group__calib3d__fisheye.html#details).
 *
 * To equate this to one of Kalibr's models, this is what you would use for `pinhole-equi`.
 */
template <typename T>
class CamEqui : public CamBase<T> {

public:
  /**
   * @brief Default constructor
   * @param width Width of the camera (raw pixels)
   * @param height Height of the camera (raw pixels)
   */
  CamEqui(size_t width, size_t height) : CamBase<T>(width, height) {}

  ~CamEqui() {}

  /**
   * @brief Given a raw uv point, this will undistort it based on the camera matrices into normalized camera coords.
   * @param uv_dist Raw uv coordinate we wish to undistort
   * @return 2d vector of normalized coordinates
   */
  // Eigen::Vector2f undistort_f(const Eigen::Vector2f &uv_dist) override {

  //   // Determine what camera parameters we should use
  //   cv::Matx33d camK = this->camera_k_OPENCV;
  //   cv::Vec4d camD = this->camera_d_OPENCV;

  //   // Convert point to opencv format
  //   cv::Mat mat(1, 2, CV_32F);
  //   mat.at<float>(0, 0) = uv_dist(0);
  //   mat.at<float>(0, 1) = uv_dist(1);
  //   mat = mat.reshape(2); // Nx1, 2-channel

  //   // Undistort it!
  //   cv::fisheye::undistortPoints(mat, mat, camK, camD);

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
    cv::fisheye::undistortPoints(mat, mat, camK, camD);

    // Construct our return vector
    Vec2<T> pt_out;
    mat = mat.reshape(1); // Nx2, 1-channel
    pt_out(0) = mat.at<T>(0, 0);
    pt_out(1) = mat.at<T>(0, 1);
    return pt_out;
  }

  Vec2<T> undistort_pxl_frame(const Vec2<T> &uv_dist) override {

    // Determine what camera parameters we should use
    cv::Matx<T, 3, 3> camK = this->camera_k_OPENCV;
    cv::Vec<T, 5> camD = this->camera_d_OPENCV;

    // Convert point to opencv format
    cv::Mat mat(1, 2, (std::is_same<T, float>::value) ? CV_32F : CV_64F);
    mat.at<T>(0, 0) = uv_dist(0);
    mat.at<T>(0, 1) = uv_dist(1);
    mat = mat.reshape(2); // Nx1, 2-channel

    // Undistort it!
    cv::fisheye::undistortPoints(mat, mat, camK, camD);

    // Construct our return vector
    Vec2<T> pt_out;
    mat = mat.reshape(1); // Nx2, 1-channel
    pt_out(0) = camK(0, 0) * mat.at<T>(0, 0) + camK(0, 2);  // x' = fx * x + cx
    pt_out(1) = camK(1, 1) * mat.at<T>(0, 1) + camK(1, 2);  // y' = fy * y + cy

    return pt_out;
  }

  // void CalculatePixelUndistortionMap() {
  //   std::cout << "Start to set pixel undistortion map using opencv undistort points" << std::endl;
  //   // Intrinsic camera matrix
  //   cv::Mat K_old = (cv::Mat_<T>(3, 3) << this->camera_k_OPENCV(0, 0), this->camera_k_OPENCV(0, 1), this->camera_k_OPENCV(0, 2),
  //       this->camera_k_OPENCV(1, 0), this->camera_k_OPENCV(1, 1), this->camera_k_OPENCV(1, 2), 0.0, 0.0, 1.0);
  //   cv::Mat D_old = (cv::Mat_<T>(5, 1) << this->camera_d_OPENCV(0), this->camera_d_OPENCV(1), this->camera_d_OPENCV(2), this->camera_d_OPENCV(3), 0.0);
  //   cv::Size imageSize(this->w(), this->h());
  //   const int alpha = 1; // 0: return the full image, 1: return the valid pixels
  //   cv::Mat K_new = getOptimalNewCameraMatrix(K_old, D_old, imageSize, alpha, imageSize, 0);
    
  //   // cv::Mat cameraMatrix_old = (cv::Mat_<double>(3,3) << fx_ori_, 0.0, cx_ori_, 0.0, fy_ori_, cy_ori_, 0.0, 0.0, 1.0);
  //   // cv::Mat cameraMatrix_new = (cv::Mat_<double>(3,3) << fx_, 0.0, cx_, 0.0, fy_, cy_, 0.0, 0.0, 1.0);

  //   // Distortion coefficients (k1, k2, p1, p2, k3)
  //   // cv::Mat distCoeffs = (cv::Mat_<double>(1,5) << coeffs_[0], coeffs_[1], coeffs_[2], coeffs_[3], coeffs_[4]);

  //   std::vector<cv::Point2f> distortedPoint;
  //   std::vector<cv::Point2f> undistortedPoint;
  //   for (int u = 0; u < this->_width; u++) {
  //     for (int v = 0; v < this->_height; v++) {
  //       cv::Point2f pt = { cv::Point2f(u, v) };
  //       distortedPoint.push_back(pt);
  //     }
  //   }
  //   // Undistort the point
  //   cv::undistortPoints(distortedPoint, undistortedPoint, K_old, D_old, cv::noArray(), K_new);

  //   int64_t cnt = 0;
  //   for (int v = 0; v < this->_height; v++) {
  //     float* mapx_ptr = this->mapx_.template ptr<float>(v);  // Use `template`
  //     float* mapy_ptr = this->mapy_.template ptr<float>(v);

  //     for (int u = 0; u < this->_width; u++) {
  //       if (cnt >= undistortedPoint.size()) {
  //         std::cerr << "Error: undistortedPoint out of bounds at index " << cnt << std::endl;
  //         return;
  //       }
  //       mapx_ptr[u] = undistortedPoint[cnt].x;
  //       mapy_ptr[u] = undistortedPoint[cnt].y;
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
  // Eigen::Vector2f distort_f(const Eigen::Vector2f &uv_norm) override {

  //   // Get our camera parameters
  //   Eigen::MatrixXd cam_d = this->camera_values;

  //   // Calculate distorted coordinates for fisheye
  //   double r = std::sqrt(uv_norm(0) * uv_norm(0) + uv_norm(1) * uv_norm(1));
  //   double theta = std::atan(r);
  //   double theta_d = theta + cam_d(4) * std::pow(theta, 3) + cam_d(5) * std::pow(theta, 5) + cam_d(6) * std::pow(theta, 7) +
  //                    cam_d(7) * std::pow(theta, 9);

  //   // Handle when r is small (meaning our xy is near the camera center)
  //   double inv_r = (r > 1e-8) ? 1.0 / r : 1.0;
  //   double cdist = (r > 1e-8) ? theta_d * inv_r : 1.0;

  //   // Calculate distorted coordinates for fisheye
  //   Eigen::Vector2f uv_dist;
  //   double x1 = uv_norm(0) * cdist;
  //   double y1 = uv_norm(1) * cdist;
  //   uv_dist(0) = (float)(cam_d(0) * x1 + cam_d(2));
  //   uv_dist(1) = (float)(cam_d(1) * y1 + cam_d(3));
  //   return uv_dist;
  // }

  Vec2<T> distort(const Vec2<T> &uv_norm) override {

    // Get our camera parameters
    DMat<T> cam_d = this->camera_values;

    // Calculate distorted coordinates for fisheye
    T r = std::sqrt(uv_norm(0) * uv_norm(0) + uv_norm(1) * uv_norm(1));
    T theta = std::atan(r);
    T theta_d = theta + cam_d(4) * std::pow(theta, 3) + cam_d(5) * std::pow(theta, 5) + cam_d(6) * std::pow(theta, 7) +
                     cam_d(7) * std::pow(theta, 9);

    // Handle when r is small (meaning our xy is near the camera center)
    T inv_r = (r > 1e-8) ? 1.0 / r : 1.0;
    T cdist = (r > 1e-8) ? theta_d * inv_r : 1.0;

    // Calculate distorted coordinates for fisheye
    Vec2<T> uv_dist;
    T x1 = uv_norm(0) * cdist;
    T y1 = uv_norm(1) * cdist;
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

    // Calculate distorted coordinates for fisheye
    T r = std::sqrt(uv_norm(0) * uv_norm(0) + uv_norm(1) * uv_norm(1));
    T theta = std::atan(r);
    T theta_d = theta + cam_d(4) * std::pow(theta, 3) + cam_d(5) * std::pow(theta, 5) + cam_d(6) * std::pow(theta, 7) +
                     cam_d(7) * std::pow(theta, 9);

    // Handle when r is small (meaning our xy is near the camera center)
    T inv_r = (r > 1e-8) ? 1.0 / r : 1.0;
    T cdist = (r > 1e-8) ? theta_d * inv_r : 1.0;

    // Jacobian of distorted pixel to "normalized" pixel
    Eigen::Matrix<T, 2, 2> duv_dxy = Eigen::Matrix<T, 2, 2>::Zero();
    duv_dxy << cam_d(0), 0, 0, cam_d(1);

    // Jacobian of "normalized" pixel to normalized pixel
    Eigen::Matrix<T, 2, 2> dxy_dxyn = Eigen::Matrix<T, 2, 2>::Zero();
    dxy_dxyn << theta_d * inv_r, 0, 0, theta_d * inv_r;

    // Jacobian of "normalized" pixel to r
    Eigen::Matrix<T, 2, 1> dxy_dr = Eigen::Matrix<T, 2, 1>::Zero();
    dxy_dr << -uv_norm(0) * theta_d * inv_r * inv_r, -uv_norm(1) * theta_d * inv_r * inv_r;

    // Jacobian of r pixel to normalized xy
    Eigen::Matrix<T, 1, 2> dr_dxyn = Eigen::Matrix<T, 1, 2>::Zero();
    dr_dxyn << uv_norm(0) * inv_r, uv_norm(1) * inv_r;

    // Jacobian of "normalized" pixel to theta_d
    Eigen::Matrix<T, 2, 1> dxy_dthd = Eigen::Matrix<T, 2, 1>::Zero();
    dxy_dthd << uv_norm(0) * inv_r, uv_norm(1) * inv_r;

    // Jacobian of theta_d to theta
    T dthd_dth = 1 + 3 * cam_d(4) * std::pow(theta, 2) + 5 * cam_d(5) * std::pow(theta, 4) + 7 * cam_d(6) * std::pow(theta, 6) +
                      9 * cam_d(7) * std::pow(theta, 8);

    // Jacobian of theta to r
    T dth_dr = 1 / (r * r + 1);

    // Total Jacobian wrt normalized pixel coordinates
    H_dz_dzn = DMat<T>::Zero(2, 2);
    H_dz_dzn = duv_dxy * (dxy_dxyn + (dxy_dr + dxy_dthd * dthd_dth * dth_dr) * dr_dxyn);

    // Calculate distorted coordinates for fisheye
    T x1 = uv_norm(0) * cdist;
    T y1 = uv_norm(1) * cdist;

    // Compute the Jacobian in respect to the intrinsics
    H_dz_dzeta = DMat<T>::Zero(2, 8);
    H_dz_dzeta(0, 0) = x1;
    H_dz_dzeta(0, 2) = 1;
    H_dz_dzeta(0, 4) = cam_d(0) * uv_norm(0) * inv_r * std::pow(theta, 3);
    H_dz_dzeta(0, 5) = cam_d(0) * uv_norm(0) * inv_r * std::pow(theta, 5);
    H_dz_dzeta(0, 6) = cam_d(0) * uv_norm(0) * inv_r * std::pow(theta, 7);
    H_dz_dzeta(0, 7) = cam_d(0) * uv_norm(0) * inv_r * std::pow(theta, 9);
    H_dz_dzeta(1, 1) = y1;
    H_dz_dzeta(1, 3) = 1;
    H_dz_dzeta(1, 4) = cam_d(1) * uv_norm(1) * inv_r * std::pow(theta, 3);
    H_dz_dzeta(1, 5) = cam_d(1) * uv_norm(1) * inv_r * std::pow(theta, 5);
    H_dz_dzeta(1, 6) = cam_d(1) * uv_norm(1) * inv_r * std::pow(theta, 7);
    H_dz_dzeta(1, 7) = cam_d(1) * uv_norm(1) * inv_r * std::pow(theta, 9);
  }
};

} // namespace se_core

#endif /* SE_CORE_CAM_EQUI_H */