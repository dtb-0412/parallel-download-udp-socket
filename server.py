import json
import os
import socket
import threading
import time

PASSWORD = "admin@1234"
SERVER_PORT = 12345
DATA_FOLDER = os.path.join("server_data")
SEND_BUF = 65536  # 32KiB
RECV_BUF = 1024  # 1KiB


class Server:
	def __init__(self):
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Master socket
		self._sock.bind(("192.168.100.24", SERVER_PORT))
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, SEND_BUF)
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF)
		print("Server is initiated")

		self._clients = {}  # Client address: file descriptor, waiting ACK list

		self._run = False

		self._ack_thread = threading.Thread(target=self._handle_ack, args=())

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
			case "LIST":  # Client requests list of files on server side
				file_list = {}
				for filename in os.listdir(DATA_FOLDER):
					filepath = os.path.join(DATA_FOLDER, filename)
					file_list[filepath] = os.path.getsize(filepath)
				self._sock.sendto(json.dumps(file_list).encode(), addr)
				print(f"Client {addr} requested list of files in [{DATA_FOLDER}]")

			case "DOWN":  # Client requests to download a file
				# Massage: DOWN {filepath}
				_, filepath = msg_parts
				if os.path.exists(filepath):
					file = open(filepath, "rb")
					self._clients[addr] = {
						"fd": file, "seq": 0, "ack_list": []
					}  # Register the client to the requested file
					print(f"Client {addr} registered to download file [{filepath}]")

			case "GET":  # Client requests a part of the currently registered file
				# Message: GET {offset} {size}
				# Return the contents from {offset} to {offset} + {size}. If {size} is -1, return the rest of the file
				_, offset, size = msg_parts
				file = self._clients[addr]["fd"]
				file.seek(int(offset))  # Move cursor to offset position

				chunk_size = min(abs(int(size)), SEND_BUF)

				self._clients[addr]["seq"] += chunk_size
				# contents = bytearray()
				contents = file.read(chunk_size or -1)  # Read the chunk
				# time.sleep(0.1)
				self._sock.sendto(contents, addr)
				# self._clients[addr]["ack_list"].append()

			case "ACK":
				# print(f"Client {addr} response [{msg.decode()}]")
				pass

			case "QUIT":
				if self._clients.get(addr) is not None:  # Remove client
					client = self._clients.pop(addr)
					client["fd"].close()
				print(f"Client {addr} disconnected!")

			case "TERM":  # Admin terminate command
				# Message: TERMINATE {password}
				_, password = msg_parts
				if password == PASSWORD:
					self._run = False

		return None

	def _handle_ack(self) -> None:
		# while True:
		# 	pass
		return None


if __name__ == "__main__":
	server = Server()
	server.run()
