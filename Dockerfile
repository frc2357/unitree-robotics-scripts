FROM ros:humble-ros-base

WORKDIR /root/ros2_ws

# Install ONLY the Foxglove bridge and curl (required by the uv installer)
RUN apt-get update && apt-get install -y \
    ros-humble-foxglove-bridge \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv directly
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin:$PATH"
ENV UV_SYSTEM_PYTHON=1

# Copy dependency files and install
COPY pyproject.toml uv.lock* ./
RUN uv pip install -r pyproject.toml

# Source ROS 2 automatically
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

CMD ["bash"]