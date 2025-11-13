###########################################
# Base image
###########################################
FROM ubuntu:24.04 AS rvc-jazzy-base

ENV DEBIAN_FRONTEND=noninteractive

# Install language
RUN apt-get update && apt-get install -y \
  locales \
  && locale-gen en_US.UTF-8 \
  && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
  && rm -rf /var/lib/apt/lists/*
ENV LANG en_US.UTF-8

# Install timezone
RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime \
  && export DEBIAN_FRONTEND=noninteractive \
  && apt-get update \
  && apt-get install -y tzdata \
  && dpkg-reconfigure --frontend noninteractive tzdata \
  && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get -y upgrade \
  && rm -rf /var/lib/apt/lists/*

# Install common programs
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  gnupg2 \
  lsb-release \
  sudo \
  software-properties-common \
  wget \
  python3-venv \
  && rm -rf /var/lib/apt/lists/*

# Install ROS2
RUN sudo add-apt-repository universe \
  && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null \
  && apt-get update && apt-get install -y --no-install-recommends \
  ros-jazzy-ros-base \
  python3-argcomplete \
  && rm -rf /var/lib/apt/lists/*

RUN bash -c 'wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/intel-repo-keyring.gpg > /dev/null' \
  && bash -c 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/intel-repo-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list' \
  && bash -c 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/intel-repo-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main" | tee /etc/apt/sources.list.d/intel-openvino-2024.list' \
  && apt-get update && apt-get install -y --no-install-recommends \
  ros-jazzy-controller-manager \
  ros-jazzy-control-toolbox \
  ros-jazzy-xacro \
  ros-jazzy-librealsense2 \
  ros-jazzy-realsense2-camera \
  ros-jazzy-realsense2-description \
  ros-jazzy-pcl-conversions \
  ros-jazzy-diagnostic-updater \
  ros-jazzy-joint-state-broadcaster \
  ros-jazzy-joint-trajectory-controller \
  ros-jazzy-joint-state-publisher \
  ros-jazzy-forward-command-controller \
  ros-jazzy-moveit-ros-planning \
  ros-jazzy-moveit-ros-planning-interface \
  ros-jazzy-moveit-ros-visualization \
  ros-jazzy-moveit-servo \
  ros-jazzy-velocity-controllers \
  ros-jazzy-position-controllers \
  ros-jazzy-forward-command-controller \
  ros-jazzy-moveit-ros-visualization \
  ros-jazzy-compressed-depth-image-transport \
  ros-jazzy-compressed-image-transport \
  ros-jazzy-image-transport-plugins \
  openvino-libraries-dev \
  nlohmann-json3-dev \
  libnlopt-cxx-dev \
  && rm -rf /var/lib/apt/lists/*


ENV ROS_DISTRO=jazzy
ENV AMENT_PREFIX_PATH=/opt/ros/jazzy
ENV COLCON_PREFIX_PATH=/opt/ros/jazzy
ENV LD_LIBRARY_PATH=/opt/ros/jazzy/lib
ENV PATH=/opt/ros/jazzy/bin:$PATH
ENV PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages
ENV ROS_PYTHON_VERSION=3
ENV ROS_VERSION=2
ENV DEBIAN_FRONTEND=

###########################################
#  Development image
###########################################
FROM rvc-jazzy-base AS rvc-jazzy-dev

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
  bash-completion \
  build-essential \
  cmake \
  gdb \
  git \
  openssh-client \
  python3-argcomplete \
  python3-pip \
  ros-dev-tools \
  ros-jazzy-ament-* \
  vim \
  && rm -rf /var/lib/apt/lists/*

RUN rosdep init || echo "rosdep already initialized"

ARG USERNAME=ros
# user 1000 already exists so creating one user that doesn't conflict
# especially since we're adding sudo support to it
ARG USER_UID=10001
ARG USER_GID=$USER_UID

# Create a non-root user
RUN groupadd --gid $USER_GID $USERNAME \
  && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
  # Add sudo support for the non-root user
  && apt-get update \
  && apt-get install -y sudo \
  && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME\
  && chmod 0440 /etc/sudoers.d/$USERNAME \
  && rm -rf /var/lib/apt/lists/*

# Set up autocompletion for user
RUN apt-get update && apt-get install -y git-core bash-completion \
  && echo "if [ -f /opt/ros/${ROS_DISTRO}/setup.bash ]; then source /opt/ros/${ROS_DISTRO}/setup.bash; fi" >> /home/$USERNAME/.bashrc \
  && echo "if [ -f /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash ]; then source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash; fi" >> /home/$USERNAME/.bashrc \
  && rm -rf /var/lib/apt/lists/* 

ENV DEBIAN_FRONTEND=
ENV AMENT_CPPCHECK_ALLOW_SLOW_VERSIONS=1

# Set up auto-source of workspace for ros user
ARG WORKSPACE=/rvc
RUN echo "if [ -f ${WORKSPACE}/install/setup.bash ]; then source ${WORKSPACE}/install/setup.bash; fi" >> /home/$USERNAME/.bashrc
