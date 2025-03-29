import itertools
import json
import os
import socket
import threading
import time
from functools import wraps
from typing import Optional

SERVER_ADDR = ("127.0.0.1", 12345)
DATA_FOLDER = "client_data"
CHUNK_SIZE = 8192  # 8KiB

BASE_10_UNITS = (
	(pow(1000, 0), "B"),  # Byte
	(pow(1000, 1), "KB"),  # Kilobyte
	(pow(1000, 2), "MB"),  # Megabyte
	(pow(1000, 3), "GB"),  # Gigabyte
	(pow(1000, 4), "TB"),  # Terabyte
)

BASE_2_UNITS = (
	(pow(1024, 0), "B"),  # Byte
	(pow(1024, 1), "KiB"),  # Kibibyte
	(pow(1024, 2), "MiB"),  # Mebibyte
	(pow(1024, 3), "GiB"),  # Gibibyte
	(pow(1024, 4), "TiB"),  # Tebibyte
)


def convert_size(size: int, base_10: bool) -> tuple[int | float, str]:
	"""
	Convert size in bytes to the largest possible unit

	:param size: Size in bytes
	:param base_10: Whether to use base 10 or 2 units
	:return: New size and unit
	"""
	units = BASE_10_UNITS if base_10 else BASE_2_UNITS
	factor, unit = units[0]
	for next_factor, next_unit in units[1:]:
		if size < next_factor:
			return size / factor, unit  # Convert to the smallest unit large enough to contain size
		factor, unit = next_factor, next_unit
	return size / factor, unit  # Overflow, convert to the current largest unit


def measure(func):
	@wraps(func)
	def wrapper(*args, **kwargs) -> None:
		begin_time = time.perf_counter()
		func(*args, **kwargs)
		end_time = time.perf_counter()

		total_time = end_time - begin_time
		print(f"Download time:  {total_time:.6f} seconds")
		print(f"Average speed:  {(args[-1] // total_time) // 1000000} MBps")
		print()
		return None
	return wrapper


class Client:
	def __init__(self):
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

	def __del__(self):
		self.quit()

	def get_file_list(self) -> dict:
		self._sock.sendto("LIST".encode(), SERVER_ADDR)
		data, _ = self._sock.recvfrom(4096)
		return json.loads(data.decode())

	@measure
	def download(self, filepath: str, file_size: int, new_name: Optional[str] = None) -> None:
		new_size, unit = convert_size(file_size, base_10=True)
		print(f"Downloading [{filepath}] - [{new_size:.2f} {unit}]")

		self._sock.sendto(f"DOWN {filepath}".encode(), SERVER_ADDR)
		# Prepare downloading
		quotient, remainder = divmod(file_size, 4)
		sizes = [quotient] * 3 + [quotient + remainder]  # Chunk sizes
		offsets = [0] + list(itertools.accumulate(sizes[:-1]))  # Chunk offsets
		chunk_paths = [os.path.join(DATA_FOLDER, f"part_{i}") for i in range(4)]  # Downloaded parts
		# Thread for updating progress bar
		progresses = [0] * 4
		lock = threading.Lock()
		threads = [threading.Thread(target=Client._update_progress, args=(progresses, lock))]
		# Download threads
		for index, (offset, size, chunk_path) in enumerate(zip(offsets, sizes, chunk_paths)):
			thread = threading.Thread(target=Client._download_chunk, args=(offset, size, chunk_path, progresses, index, lock))
			threads.append(thread)

		for thread in threads:
			thread.start()

		for thread in threads:  # Wait for all downloads to finish
			thread.join()
		# Number filename if name collision
		filename = new_name or os.path.basename(filepath)
		name, ext = os.path.splitext(filename)
		count = 1
		while True:
			if not os.path.exists(os.path.join(DATA_FOLDER, filename)):
				break
			filename = f"{name} ({count}){ext}"
			count += 1
		# Merge parts
		with open(os.path.join(DATA_FOLDER, filename), "wb") as file:
			for chunk_path in chunk_paths:
				with open(chunk_path, "rb") as chunk_file:
					file.write(chunk_file.read())
				os.remove(chunk_path)
		print(f"\nCompleted [{filename}]")
		return None

	@staticmethod
	def _update_progress(progresses: list, lock: threading.Lock) -> None:
		while True:
			with lock:
				current_progresses = progresses.copy()
			# Print progress bar
			progress_bar = " | ".join(
				"Part {}: {:30}".format(i, f"{'█' * (progress // 4):25} {progress}%")
				for i, progress in enumerate(current_progresses))
			print(f"\r{progress_bar} |", end="")

			if all(progress == 100 for progress in current_progresses):
				break
			time.sleep(0.05)
		return None

	@staticmethod
	def _download_chunk(offset: int, size: int, chunk_path: str, progresses: list, index: int, lock: threading.Lock) -> None:
		# Handle downloading a single chunk
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		chunk_file = open(chunk_path, "wb")
		total = 0
		while True:
			# Get chunk from server
			chunk_size = min(CHUNK_SIZE, size - total)
			sock.sendto(f"GET {offset} {chunk_size}".encode(), SERVER_ADDR)
			data, _ = sock.recvfrom(chunk_size)

			# sock.sendto(f"ACK {offset}".encode(), SERVER_ADDR)
			chunk_file.write(data)

			total = min(total + chunk_size, size)
			with lock:  # Update progress
				progresses[index] = int(total / size * 100)

			if total == size:  # Download complete
				break
			offset += chunk_size
			# time.sleep(0.01)
		chunk_file.close()
		return None

	def quit(self) -> None:
		self._sock.sendto("QUIT".encode(), SERVER_ADDR)
		self._sock.close()
		return None


if __name__ == "__main__":
	client = Client()

	file_list = list(client.get_file_list().items())

	for filepath, file_size in file_list:
		client.download(filepath, file_size)

	# filepath, file_size = file_list[-1]
	# client.download(filepath, file_size)
