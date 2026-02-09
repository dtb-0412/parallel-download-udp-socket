import hashlib
import json
import os
import socket
import struct

PASSWORD = "admin@1234"
SERVER_PORT = 12345
DATA_FOLDER = os.path.abspath("server_data")
SEND_BUF = 65536  # 64KiB
RECV_BUF = 1024  # 1KiB
PERMISSIONS_FILEPATH = os.path.abspath("permissions.txt")


class Server:
	def __init__(self):
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Master socket
		self._sock.bind(("0.0.0.0", SERVER_PORT))
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUF)
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF)
		print(f"Server is initiated on {self._sock.getsockname()}")

		self._permissions = {"whitelist": [], "blacklist": []}
		self._load_permissions()

		self._file_list = {}
		self._scan()

		self._clients = {}  # Client address: file descriptor
		self._run = False


	def __del__(self):
		print("Server is closed")
		self._sock.close()

	def run(self) -> None:
		print("Server is running...")
		self._run = True
		while self._run:
			try:
				msg, addr = self._sock.recvfrom(RECV_BUF)
			except Exception as e:
				print(f"Exception: {e}")
			else:
				self.handle_client(msg, addr)

	def handle_client(self, msg: bytes, addr: tuple) -> None:
		msg_parts = msg.decode().split(' ')
		match msg_parts[0]:
			case "HELLO":  # Connectivity check
				print(f"Established connection with client {addr}!")
				self._sock.sendto(f"Connection established.".encode(), addr)

			# Client communication
			case "LIST":  # Client requests list of files on server side
				file_list = {os.path.join(DATA_FOLDER, os.path.relpath(path, DATA_FOLDER)): size
							 for path, size in self._file_list.items()}
				self._sock.sendto(json.dumps(file_list).encode(), addr)
				print(f"Client {addr} requested list of files in [{DATA_FOLDER}]")

			case "DOWN":  # Client requests to download a file
				# Message: DOWN {filepath}
				_, filepath = msg_parts
				if self._validate_path(filepath) and os.path.exists(filepath):
					file = open(filepath, "rb")
					self._clients[addr] = file  # Register the client to the requested file
					print(f"Client {addr} registered to download file [{filepath}]")

			case "GET":  # Client requests a part of the currently registered file
				# Message: GET {offset} {size}
				# Send from {offset} to {offset} + {size}. If {size} is -1, send the rest of the file
				_, offset, size = msg_parts
				file = self._clients[addr]
				file.seek(int(offset))  # Move cursor to offset position

				chunk_size = min(abs(int(size)), SEND_BUF)
				contents = file.read(chunk_size or -1)
				checksum = hashlib.md5(contents).hexdigest().encode()
				packet = struct.pack(f"32s{chunk_size}s", checksum, contents)
				self._sock.sendto(packet, addr)

			case "QUIT":
				if self._clients.get(addr) is not None:  # Remove client
					file = self._clients.pop(addr)
					file.close()
				print(f"Client {addr} disconnected!\n")

			# Admin communication
			case "SCAN":  # Re-scan the data folder to update file list
				# Message: SCAN {password}
				_, password = msg_parts
				if password == PASSWORD:
					self._load_permissions()
					self._scan()
					print("Updated file list successfully!\n")

			case "TERM":  # Stop server
				# Message: TERMINATE {password}
				_, password = msg_parts
				if password == PASSWORD:
					self._run = False

			case "LOG":
				_, password = msg_parts
				if password == PASSWORD:
					print("\nFile permissions:")
					for key, value in self._permissions.items():
						print(f"{key.upper()}:")
						for path in value:
							print(f"\t{path}")

					print(f"\nFile list:")
					if not self._file_list:
						print("\tEmpty")
					else:
						for filepath in self._file_list:
							print(f"\t{filepath}")
					print()
		return None


	def _validate_path(self, filepath: str) -> bool:
		"""
		Validate the requested filepath

		:param filepath: Filepath requested
		:return: Whether filepath is allowed for download
		"""
		full_path = os.path.abspath(filepath)
		if os.path.commonpath([full_path, DATA_FOLDER]) != DATA_FOLDER:
			return False

		if not any(os.path.commonpath([full_path, path]) == path for path in self._permissions["whitelist"]):
			return False

		if any(os.path.commonpath([full_path, path]) == path for path in self._permissions["blacklist"]):
			return False
		return True

	def _load_permissions(self) -> None:
		if not os.path.exists(PERMISSIONS_FILEPATH):
			return None

		current = None
		self._permissions.update({"whitelist": [], "blacklist": []})
		with open(PERMISSIONS_FILEPATH, "r") as file:
			for line in file:
				line = line.strip()
				if not line:
					continue

				if line.lower() == "[whitelist]":
					current = "whitelist"
					continue

				if line.lower() == "[blacklist]":
					current = "blacklist"
					continue

				if current is not None:
					path = os.path.abspath(os.path.join(DATA_FOLDER, line))
					self._permissions[current].append(path)
		return None


	def _scan(self) -> None:
		"""
		Scan through data folder and make a list of all files allowed for download

		:return: None
		"""
		self._file_list.clear()
		for root, _, files in os.walk(DATA_FOLDER):
			for file in files:
				filepath = os.path.join(root, file)
				if self._validate_path(filepath):
					self._file_list[filepath] = os.path.getsize(filepath)
		return None


if __name__ == "__main__":
	server = Server()
	server.run()
