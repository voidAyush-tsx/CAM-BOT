#include <QApplication>
#include <rviz_common/visualizer_app.hpp>
#include <rviz_common/visualization_frame.hpp>
#include <rviz_common/visualization_manager.hpp>
void rviz_common::VisualizerApp::checkContinue()
{
  if (!ros_client_abstraction_->ok()) {
    if (frame_) {
      frame_->getManager()->stopUpdate();
      frame_->setWindowModified(false);
    }
    QApplication::closeAllWindows();
  }
}
