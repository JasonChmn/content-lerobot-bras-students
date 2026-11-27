#!/usr/bin/env python3
"""driver.launch.py - launches the SO-ARM101 driver node

    ros2 launch so101_driver driver.launch.py                # simulation
    ros2 launch so101_driver driver.launch.py use_sim:=false port:=<port> # real robot
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("use_sim", default_value="true",
                              description="Simulated backend or real robot"),
        DeclareLaunchArgument("port", default_value="",
                              description="Serial port of the real SO-ARM101 (lerobot-find-port)"),
        Node(
            package="so101_driver",
            executable="driver",
            name="so101_driver",
            output="screen",
            ros_arguments=["-p", ["use_sim:=", LaunchConfiguration("use_sim")],
                           "-p", ["port:='", LaunchConfiguration("port"), "'"]],
        ),
    ])
