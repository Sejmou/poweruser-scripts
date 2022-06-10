import subprocess
import re
import sys
from collections import defaultdict
import warnings

# This script allows you to focus a particular monitor's top window in a multi-monitor setup
# The monitor to select is specified using an integer (0 == left-most monitor, 1 == monitor next to it etc.)
# If the mouse/cursor is on a different screen, it is also moved to the middle of the newly focused screen
# NOTE: to use this script, wmctrl, xrandr, and xdotool must be installed on your system!

# config
monitor_width = 1920  # used for moving the mouse/cursor; as this is currently hardcoded, monitors of varying width are not supported!


def main():
    if len(sys.argv) != 2:
        # note: first entry in args is always name of script
        raise ValueError("Single integer argument (selected monitor) expected!")

    selected_monitor = int(sys.argv[1])
    monitor_x_offsets = get_monitor_x_offsets()
    no_of_monitors = len(monitor_x_offsets)

    if selected_monitor < 0 or selected_monitor >= no_of_monitors:
        raise ValueError(
            f"Invalid monitor ID! Choose either from {list(range(no_of_monitors))}, as {no_of_monitors} monitors are connected."
        )

    window_ids_by_z_idx = get_window_ids_by_z_idx()
    window_x_positions = get_window_x_positions(window_ids_by_z_idx)
    window_ids_and_positions = zip(window_ids_by_z_idx, window_x_positions)

    windows_per_monitor = get_windows_per_monitor(
        window_ids_and_positions, monitor_x_offsets
    )

    subprocess.run(
        f"wmctrl -i -a {windows_per_monitor[selected_monitor][-1]}".split(" ")
    )

    cursor_monitor = get_cursor_monitor(monitor_x_offsets)

    if cursor_monitor != selected_monitor:
        no_of_monitors_to_move = selected_monitor - cursor_monitor
        print(
            f"xdotool mousemove_relative -- {no_of_monitors_to_move * monitor_width} 0"
        )
        subprocess.call(
            f"xdotool mousemove_relative -- {no_of_monitors_to_move * monitor_width} 0",
            shell=True,
        )


def consecutive_whitespace_except_newline_to_space(str):
    return re.sub("[^\S\n]+", " ", str)


def get_windows_per_monitor(window_ids_and_positions, x_offsets):
    def get_monitor(x_pos):
        """
        gets the monitor ID for a particular window (0 being the left-most monitor, 1 the monitor next to it, etc.)

        For determining what monitor a window belongs to, its "horizontal center" (x-coordinate at middle of window on horizontal axis) is used
        """
        monitor = 0
        x_offset = 0

        for curr_monitor, curr_offset in enumerate(x_offsets):
            if curr_offset <= x_pos and curr_offset >= x_offset:
                monitor = curr_monitor
                x_offset = curr_offset

        return monitor

    windows_per_monitor = defaultdict(list)
    for id, pos in window_ids_and_positions:
        windows_per_monitor[get_monitor(pos)].append(id)

    return windows_per_monitor


def get_window_ids_by_z_idx():
    """
    returns all windows of the desktop, ordered by z-index (caution: index 0 is furthest away from top!)
    """

    xprop_output = subprocess.getoutput("xprop -root _NET_CLIENT_LIST_STACKING")
    no_whitespace = "".join(xprop_output.split())
    window_id_strings = no_whitespace[no_whitespace.index("#") + 1 :].split(",")
    return [int(id_str, 16) for id_str in window_id_strings]


def get_window_x_position(window_id):
    # if you're wondering: can't use wmctrl -lG to get window x positions as its output is not reliable, some x-coordinates are just BS lol
    # probably the issue is the arrangment of monitors in a multi-monitor setup (for certain types of windows it is respected, for others not...)
    cmd = f"xwininfo -id {hex(window_id)} | grep -w -e 'Absolute upper-left X' -e '  Width'"
    out = subprocess.getoutput(cmd)
    search_result = re.findall(r"[0-9]+", out)

    if search_result != None:
        x_pos = int(search_result[0])
        width = int(search_result[1])
        return x_pos + width / 2
    else:
        warnings.warn(
            f"output of xwinfo command ({cmd}) was:",
            out,
            "\nCould not find x-coordinate of window",
        )


def get_window_x_positions(window_ids):
    x_positions = [get_window_x_position(id) for id in window_ids]
    return x_positions


def get_monitor_x_offsets():
    xrandr_out = subprocess.getoutput("xrandr --current | grep '\sconnected'").split(
        "\n"
    )

    def extract_monitor_x_offset(xrandr_out_line):
        match = re.search(r"\+[0-9]+", xrandr_out_line)
        if match:
            x_offset = int(match.group(0))
            return x_offset

    x_offsets = []
    for line in xrandr_out:
        x_offset = extract_monitor_x_offset(line)
        if x_offset != None:  # monitor connected
            x_offsets.append(x_offset)

    x_offsets.sort()

    return x_offsets


def get_cursor_monitor(monitor_x_offsets):
    """
    gets the monitor the cursor is currently located at.
    """
    # cursor x-pos is first number in output of xdotool getmouselocation
    cursor_x = int(
        re.search("\d+", subprocess.getoutput("xdotool getmouselocation")).group()
    )

    # monitor id is index of last x-offset <= cursor_x
    # I know, the solution I came up with to get that is a bit of a mindfuck hahaha
    return next(
        len(monitor_x_offsets) - 1 - i
        for i, x in enumerate(reversed(monitor_x_offsets))
        if x <= cursor_x
    )


main()
