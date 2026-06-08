cmake_minimum_required(VERSION 3.5)
project(talos_gazebo)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  worlds
  models
  launch
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()
