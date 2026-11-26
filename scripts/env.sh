# Sourced by pixi on activation (pixi run / pixi shell). Do not run directly.

# Drop a system ROS 2 sourced in the shell: its libraries would shadow the env's.
_so101_drop_system_ros() {
  local var val entry kept
  for var in PATH LD_LIBRARY_PATH PYTHONPATH PKG_CONFIG_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH; do
    eval "val=\${$var-}"
    [ -n "$val" ] || continue
    kept=""
    while IFS= read -r -d: entry; do
      case "$entry" in /opt/ros/*|*/dist-packages*|"") ;; *) kept="${kept:+$kept:}$entry" ;; esac
    done <<< "$val:"
    export "$var=$kept"  # not unset: pixi would restore the shell's value
  done
  export ROS_LOCALHOST_ONLY=
}
_so101_drop_system_ros

# Overlay of your workspace, once built (pixi run build).
if [ -f "$PIXI_PROJECT_ROOT/ros2_ws/install/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "$PIXI_PROJECT_ROOT/ros2_ws/install/setup.bash"
  _so101_drop_system_ros  # a workspace built with a system ROS sourced chains it
fi
unset -f _so101_drop_system_ros

# Rolling distros (Arch, Fedora): the system Mesa needs a newer libdrm than the env's.
for _drm in /usr/lib64/libdrm.so.2 /usr/lib/libdrm.so.2 /usr/lib/x86_64-linux-gnu/libdrm.so.2 /usr/lib/aarch64-linux-gnu/libdrm.so.2; do
  [ -e "$_drm" ] || continue
  _sys=$(readlink -f "$_drm") _env=$(readlink -f "$CONDA_PREFIX/lib/libdrm.so.2")
  if [ "$(printf '%s\n' "${_sys##*.so.}" "${_env##*.so.}" | sort -V | tail -n1)" != "${_env##*.so.}" ]; then
    _libs=$(printf '%s:' "${_drm%/*}"/libdrm*.so.[0-9])
    export LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD:}${_libs%:}"
  fi
  break
done
unset _drm _sys _env _libs

# NixOS: no /usr/share/glvnd, the EGL vendors (MuJoCo camera) are in /run/opengl-driver.
if [ -z "${__EGL_VENDOR_LIBRARY_DIRS-}" ] && [ -d /run/opengl-driver/share/glvnd/egl_vendor.d ]; then
  export __EGL_VENDOR_LIBRARY_DIRS=/run/opengl-driver/share/glvnd/egl_vendor.d
fi
# NixOS: no ld.so.cache, so glvnd cannot find libGLX_mesa (RViz) by name.
if [ -e /run/opengl-driver/lib/libGLX_mesa.so.0 ]; then
  case ":${LD_LIBRARY_PATH-}:" in
    *:/run/opengl-driver/lib:*) ;;
    *) export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}/run/opengl-driver/lib" ;;
  esac
fi

# ROS 2 discovery limited to this machine.
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
