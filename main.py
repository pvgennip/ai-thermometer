import itertools
import os
import time

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Thread

import cv2
import numpy as np

from ir import IRThread
from rgb import RGBThread
from ui import make_ir_view, make_rgb_view, make_combined_view

from config import (
    HZ_CAP,
    LOG_DIR,
    SHOW_DISPLAY,
    SAVE_FRAMES,
    MAX_FILE_QUEUE,
    FRAME_SIZE,  # TODO: make everything size-independent
    IR_WIN_NAME,
    IR_WIN_SIZE,
    VIS_WIN_NAME,
    VIS_WIN_SIZE,
    X_DISPLAY_ADDR,
    VIS_BBOX_COLOR,
    IR_BBOX_COLOR,
)


def exit_handler():
    print("exit handler called")
    rgb_thread.stop()
    ir_thread.stop()

    rgb_thread.join()
    ir_thread.join()

    cv2.destroyAllWindows()


def setup_display(display_addr):
    if os.environ.get("DISPLAY") is None:
        os.environ["DISPLAY"] = display_addr
    elif X_DISPLAY_ADDR:
        print("WARN: Using $DISPLAY from environment, not from config")

    cv2.namedWindow(VIS_WIN_NAME)
    cv2.namedWindow(IR_WIN_NAME)
    cv2.moveWindow(IR_WIN_NAME, VIS_WIN_SIZE[1], 0)


def mainloop():

    for i in itertools.count(start=0, step=1):

        time_start = time.monotonic()

        ir_raw = ir_thread.raw
        ir_arr = ir_thread.frame
        temps = ir_thread.temperatures

        rgb_arr = rgb_thread.frame
        scores, boxes, landms = rgb_thread.get_detections()

        # only keep detections with confidence above 50%
        scores = np.array(scores)
        boxes = np.array(boxes)
        landms = np.array(landms)

        keep = scores > 0.5

        scores = scores[keep]
        boxes = boxes[keep]
        landms = landms[keep]

        rgb_view = make_rgb_view(rgb_arr, scores, boxes, landms, VIS_WIN_SIZE)

        ir_arr_zoomed_out = zoom_out(ir_arr)
        arr_combined = make_combined_view(rgb_arr, ir_arr_zoomed_out)

        # TODO: fix in new UI
        ir_view = ir_arr
        # ir_view = make_ir_view(
        #     rgb_arr, ir_arr, dets, temps, IR_WIN_SIZE, bb_color=IR_BBOX_COLOR
        # )

        # Show
        if SHOW_DISPLAY:
            cv2.imshow(VIS_WIN_NAME, rgb_view)
            cv2.imshow(IR_WIN_NAME, ir_view)
            cv2.imshow("Combined", arr_combined)
            key = cv2.waitKey(1) & 0xFF

            # if the `q` key was pressed in the cv2 window, break from the loop
            if key == ord("q"):
                break

        # Save frames
        if SAVE_FRAMES:
            if executor._work_queue.qsize() > MAX_FILE_QUEUE:
                print(
                    "Error: Too many files in file queue. Not saving frames from this iteration."
                )
            else:
                # TODO: catch writing errors due to full SD card
                # For examlple: libpng error: Write Error
                # The ret value of imwrite can be obtained from:
                # future = executor.submit(...)
                # future.result()
                executor.submit(
                    cv2.imwrite, f"{LOG_DIR}/frames/{i:05d}-rgb.jpg", rgb_view
                )
                executor.submit(
                    cv2.imwrite, f"{LOG_DIR}/frames/{i:05d}-ir.png", ir_view
                )

        main_latency = time.monotonic() - time_start

        # Quick f-string format specifiers reference:
        # f'{value:{width}.{precision}}'
        print(
            f"RGB thread latency={rgb_thread._delay:6.2f}ms   "
            f"IR thread latency={ir_thread.latency:6.2f}ms    "
            f"Main thread latency={1000*main_latency:6.2f}ms"
        )

        time.sleep(max(0, 1 / HZ_CAP - main_latency))


if __name__ == "__main__":

    rgb_thread = RGBThread()
    rgb_thread.start()

    ir_thread = IRThread(resize_to=FRAME_SIZE)
    ir_thread.start()

    if SAVE_FRAMES:
        executor = ThreadPoolExecutor(max_workers=4)

    if SHOW_DISPLAY:
        setup_display(X_DISPLAY_ADDR)

    while rgb_thread.frame is None:
        print("Waiting for RGB frames")
        time.sleep(1)

    while ir_thread.frame is None:
        print("Waiting for IR frames")
        time.sleep(1)

    try:
        mainloop()

    finally:
        exit_handler()
