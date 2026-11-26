#!/usr/bin/env python3
"""so101.launch.py - the whole stack, one include per node launch file.

    ros2 launch so101_bringup so101.launch.py                               # simulation
    ros2 launch so101_bringup so101.launch.py use_sim:=false port:=<port>   # real arm
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, IncludeLaunchDescription, LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def include(package: str, file: str, **arguments) -> IncludeLaunchDescription:
    return IncludeLaunchDescription(
        PathJoinSubstitution([FindPackageShare(package), "launch", file]),
        launch_arguments=arguments.items(),
    )


def stop_on_crash(event, context):
    """A node crashed: stop the stack, so its error stays the last thing on screen."""
    if event.returncode == 0 or context.is_shutdown:
        return None
    message = f"{event.action.name} crashed (exit code {event.returncode}): its error is just above. Stopping the stack."
    return [LogInfo(msg=message), EmitEvent(event=Shutdown(reason=message))]


def generate_launch_description():
    return LaunchDescription([
        RegisterEventHandler(OnProcessExit(on_exit=stop_on_crash)),
        DeclareLaunchArgument("use_sim", default_value="true", description="Simulated backend or real robot"),
        DeclareLaunchArgument("port", default_value="", description="Serial port of the real SO-ARM101"),
        include("so101_driver", "driver.launch.py",
                use_sim=LaunchConfiguration("use_sim"), port=LaunchConfiguration("port")),
        include("so101_description", "viz.launch.py"),
        # Add your nodes here, e.g. include("so101_perception", "perception.launch.py"),
        include("so101_brain", "brain.launch.py"),
    ])
