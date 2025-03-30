import hashlib
import itertools
import json
import os
import socket
import struct
import sys
import threading
import time
from functools import wraps
from typing import Any, Optional

SERVER_ADDR = (sys.argv[1], int(sys.argv[2]))
DATA_FOLDER = "client_data"
CHUNK_SIZE = 16384  # 16KiB
REFRESH_TIME = 5  # Check input file every 5 seconds

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
	def wrapper(*args, **kwargs) -> Any:
		begin_time = time.perf_counter()
		result = func(*args, **kwargs)
		end_time = time.perf_counter()

		total_time = end_time - begin_time
		print(f"Download time:  {total_time:.6f} seconds")
		print(f"Average speed:  {(args[-1] // total_time) // 1000000} MBps")
		print()
		return result
	return wrapper


class Client:
	def __init__(self):
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self._file_list = {}

	def __del__(self):
		self.quit()

	def get_file_list(self) -> None:
		self._sock.sendto("LIST".encode(), SERVER_ADDR)
		data, _ = self._sock.recvfrom(4096)
		self._file_list = {filepath: [file_size, False] for filepath, file_size in json.loads(data.decode()).items()}
		return None

	@measure
	def download(self, filepath: str, file_size: int, new_name: Optional[str] = None) -> bool:
		new_size, unit = convert_size(file_size, base_10=True)
		print("--------------------------------------------------")
		print(f"Downloading [{filepath}] - [{new_size:.2f} {unit}]\n")
		# Prepare downloading
		quotient, remainder = divmod(file_size, 4)
		sizes = [quotient] * 3 + [quotient + remainder]  # Chunk sizes
		offsets = [0] + list(itertools.accumulate(sizes[:-1]))  # Chunk offsets
		chunk_paths = [os.path.join(DATA_FOLDER, f"part_{i}") for i in range(4)]  # Downloaded parts
		# Thread for updating progress bar
		errors = [False] * 4
		totals = [0] * 4
		lock = threading.Lock()
		threads = [threading.Thread(target=Client._update_progress, args=(sizes, totals, errors, lock))]
		# Download threads
		for index, (offset, size, chunk_path) in enumerate(zip(offsets, sizes, chunk_paths)):
			thread = threading.Thread(target=Client._download, args=(filepath, offset, size, chunk_path, totals, errors, index, lock))
			threads.append(thread)

		for thread in threads:
			thread.start()

		for thread in threads:  # Wait for all downloads to finish
			thread.join()

		if any(errors):
			print(f"Failed [{filepath}]")
			return False
		# Number filename if name collision
		filename = new_name or os.path.basename(filepath)
		name, ext = os.path.splitext(filename)
		count = 1
		while True:
			if not os.path.exists((new_filepath := os.path.join(DATA_FOLDER, filename))):
				break
			filename = f"{name} ({count}){ext}"
			count += 1
		# Merge parts
		with open(new_filepath, "wb") as file:
			for chunk_path in chunk_paths:
				with open(chunk_path, "rb") as chunk_file:
					file.write(chunk_file.read())
				os.remove(chunk_path)
		print(f"\nCompleted [{filename}]")
		return True

	@staticmethod
	def _update_progress(sizes: list, totals: list, errors: list, lock: threading.Lock) -> None:
		file_size = sum(sizes)
		while True:
			with lock:
				if any(errors):
					print("\nServer response timeout!")
					break
				progresses = [int(total / size * 100) for total, size in zip(totals, sizes)]
			# Print progress bar
			progress_bar = " | ".join(
				"Part {}: {:12}".format(i, f"{'█' * int(progress / 8.3):12}")
				for i, progress in enumerate(progresses))

			downloaded = sum(totals)
			print("\r{} | {:4} | {:.2f} KBs".format(progress_bar, f'{int(downloaded / file_size * 100)}%', downloaded), end="")

			if all(progress == 100 for progress in progresses):
				print()
				break
			time.sleep(0.02)
		return None

	@staticmethod
	def _download(filepath: str, offset: int, size: int, chunk_path: str, totals: list, errors: list, index: int,
				  lock: threading.Lock) -> bool:
		# Handle downloading a single chunk
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(0.05)
		sock.sendto(f"DOWN {filepath}".encode(), SERVER_ADDR)

		total = 0
		finished = False
		chunk_file = open(chunk_path, "wb")
		while True:
			# Get chunk from server
			chunk_size = min(CHUNK_SIZE, size - total)
			data = Client._try_recv(sock, offset, chunk_size)
			if data is None:
				with lock:
					errors[index] = True
				break

			sock.sendto(f"ACK {offset}".encode(), SERVER_ADDR)
			chunk_file.write(data)

			total = min(total + chunk_size, size)
			with lock:  # Update progress
				totals[index] = total
			if total == size:  # Download complete
				finished = True
				break
			offset += chunk_size

		chunk_file.close()
		sock.sendto("QUIT".encode(), SERVER_ADDR)
		sock.close()
		return finished

	@staticmethod
	def _try_recv(sock: socket.socket, offset: int, chunk_size: int, attempts: int = 5) -> Optional[bytes]:
		data = None
		while attempts:
			sock.sendto(f"GET {offset} {chunk_size}".encode(), SERVER_ADDR)
			try:
				packet, _ = sock.recvfrom(chunk_size + 32)
			except TimeoutError:
				attempts -= 1
				continue
			# Verify packet
			checksum, data = struct.unpack(f"32s{chunk_size}s", packet)
			if checksum != hashlib.md5(data).hexdigest().encode():
				attempts -= 1
				continue
			break
		return data

	def run(self) -> None:
		# Print list of files on server
		self.get_file_list()
		print(f"No. | {'Path':50} | {'Size':15} |")
		for i, (filepath, (file_size, _)) in enumerate(self._file_list.items()):
			new_size, unit = convert_size(file_size, base_10=True)
			print(f"{i + 1:>03}   {filepath:50}   {new_size:.2f} {unit}")
		print()

		try:
			begin_time = 0
			while True:
				end_time = time.perf_counter()
				if end_time - begin_time < REFRESH_TIME:
					continue

				print("Check download queue...")
				with open("input.txt", "r") as file:
					for line in file:
						line = line.rstrip('\n')
						if line.upper() == "STOP":
							print("Client finished")
							return None

						filepath = line.split(' ')[0]
						if self._file_list.get(filepath) is None:  # File unavailable
							continue

						file_size, downloaded = self._file_list[filepath]
						if downloaded:  # File already downloaded
							continue

						if self.download(filepath, file_size):
							self._file_list[filepath][-1] = True
				begin_time = end_time
		except KeyboardInterrupt:
			return None

	def quit(self) -> None:
		self._sock.sendto("QUIT".encode(), SERVER_ADDR)
		self._sock.close()
		return None


if __name__ == "__main__":
	client = Client()
	client.run()
