import time
from dataclasses import dataclass
from typing import Generator, Optional

import cv2
import numpy as np


@dataclass
class MotionEvent:
	timestamp: float
	frame: Optional[np.ndarray]
	last_notified_at: float = 0.0
	motion_area: int = 0
	num_contours: int = 0

	def should_notify(self, min_interval_seconds: int) -> bool:
		if self.last_notified_at == 0.0:
			self.last_notified_at = self.timestamp
			return True
		if self.timestamp - self.last_notified_at >= min_interval_seconds:
			self.last_notified_at = self.timestamp
			return True
		return False

	def encode_jpeg(self, quality: int = 90):
		if self.frame is None:
			return False, b""
		encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
		ret, buf = cv2.imencode(".jpg", self.frame, encode_params)
		return ret, buf.tobytes() if ret else b""


class MotionDetector:
	def __init__(self, device_index: int = 0, min_contour_area: int = 500):
		self.device_index = device_index
		self.min_contour_area = min_contour_area
		self.cap = cv2.VideoCapture(self.device_index)
		if not self.cap.isOpened():
			raise RuntimeError(f"Unable to open camera device {self.device_index}")
		self.prev_gray = None

	def detect_events(self) -> Generator[MotionEvent, None, None]:
		while True:
			ok, frame = self.cap.read()
			if not ok:
				time.sleep(0.1)
				continue

			gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
			if self.prev_gray is None:
				self.prev_gray = gray
				continue

			diff = cv2.absdiff(self.prev_gray, gray)
			_, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
			contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

			# Aggregate motion metrics
			total_area = 0
			qualifying = []
			for c in contours:
				area = cv2.contourArea(c)
				if area >= self.min_contour_area:
					total_area += int(area)
					qualifying.append(c)

			motion_detected = total_area > 0

			self.prev_gray = gray

			if motion_detected:
				yield MotionEvent(
					timestamp=time.time(),
					frame=frame,
					motion_area=total_area,
					num_contours=len(qualifying),
				)

	def close(self) -> None:
		if self.cap is not None:
			self.cap.release()
