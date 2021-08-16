"""
The simplest example of using PureThemal2 board: 
- reads the USB UVC device
- prints the resulting numpy array
"""


import time
import cv2
import numpy as np
from queue import Queue

# IR camera
from libuvc_wrapper import *

BUF_SIZE = 2
q = Queue(BUF_SIZE)


def py_frame_callback(frame, userptr):

    array_pointer = cast(
        frame.contents.data,
        POINTER(c_uint16 * (frame.contents.width * frame.contents.height)),
    )
    data = np.frombuffer(array_pointer.contents, dtype=np.dtype(np.uint16)).reshape(
        frame.contents.height, frame.contents.width
    )  # no copy

    # data = np.fromiter(
    #   frame.contents.data, dtype=np.dtype(np.uint8), count=frame.contents.data_bytes
    # ).reshape(
    #   frame.contents.height, frame.contents.width, 2
    # ) # copy

    if frame.contents.data_bytes != (2 * frame.contents.width * frame.contents.height):
        return

    if not q.full():
        q.put(data)


PTR_PY_FRAME_CALLBACK = CFUNCTYPE(None, POINTER(uvc_frame), c_void_p)(py_frame_callback)

def ktoc(val):
    return (val - 27315) / 100.0

def setup():
    ctx = POINTER(uvc_context)()
    dev = POINTER(uvc_device)()
    devh = POINTER(uvc_device_handle)()
    ctrl = uvc_stream_ctrl()

    res = libuvc.uvc_init(byref(ctx), 0)
    if res < 0:
        print("uvc_init error")
        exit(res)

    res = libuvc.uvc_find_device(ctx, byref(dev), PT_USB_VID, PT_USB_PID, 0)
    if res < 0:
        print("uvc_find_device error")
        exit(res)

    res = libuvc.uvc_open(dev, byref(devh))
    if res < 0:
        print("uvc_open error {}".format(res))
        exit(res)

    print("device opened!")

    print_device_info(devh)
    print_device_formats(devh)

    frame_formats = uvc_get_frame_formats_by_guid(devh, VS_FMT_GUID_Y16)
    if len(frame_formats) == 0:
        print("device does not support Y16")
        exit(1)

    libuvc.uvc_get_stream_ctrl_format_size(
        devh,
        byref(ctrl),
        UVC_FRAME_FORMAT_Y16,
        frame_formats[0].wWidth,
        frame_formats[0].wHeight,
        int(1e7 / frame_formats[0].dwDefaultFrameInterval),
    )

    res = libuvc.uvc_start_streaming(
        devh, byref(ctrl), PTR_PY_FRAME_CALLBACK, None, 0
    )
    if res < 0:
        print("uvc_start_streaming failed: {0}".format(res))
        exit(1)


    return ctx, dev, devh, ctrl

def filterTempArray(temp_arr, t_thres_low=0, t_thres_high=50):
    filter_arr = []
    for v in temp_arr:
        print(v)
        if v >= t_thres_low and v <= t_thres_high:
            filter_arr.append(True)
        else:
            filter_arr.append(False)

    return temp_arr[filter_arr]

def getTempArray(t_thres_low=0, t_thres_high=50):
    ctx, dev, devh, ctrl = setup()

    for i in range (1, 5):
        data = q.get(True, 500)
        tcnt = len(data)
        if tcnt == 120:
            temps= ktoc(data)
            temps= filterTempArray(temps, t_thres_low, t_thres_high)
            #temps= np.sort(temps)[2:tcnt-2]
            tcnt = len(temps)
            tmin = np.min(temps)
            tmax = np.max(temps)
            tave = np.mean(temps)
            tmip = np.percentile(temps, 5)
            tmep = np.percentile(temps, 50)
            tmap = np.percentile(temps, 95)
            print("values: {}, min={}, max={}, ave={}, mid_perc={}, low_5perc={}, high_5perc={}".format(tcnt, tmin, tmax, tave, tmep, tmip, tmap))
        else:
            print("too few values: {}".format(tcnt))

    libuvc.uvc_stop_streaming(devh)
    libuvc.uvc_unref_device(dev)
    libuvc.uvc_exit(ctx)




if __name__ == "__main__":

    getTempArray(5,45)
