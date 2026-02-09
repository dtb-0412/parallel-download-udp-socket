import socket

PASSWORD = "admin@1234"
SERVER_ADDR = ("127.0.0.1", 12345)


def main():
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.settimeout(2)
	# Check connectivity
	try:
		sock.sendto("HELLO".encode(), SERVER_ADDR)
		_ = sock.recvfrom(1024)
		print("Connected to server successfully!")
	except TimeoutError:
		print("Cannot connect to server (connection timed out).")
		return
	except Exception as e:
		print(f"Unexpected error: {e}")
		return

	print("Admin client started. Type \'help\' for list of commands.")

	try:
		while True:
			cmd = input("- ").strip().lower()
			if not cmd:
				continue

			match cmd:
				case "help":
					print("List of commands:\n"
						  "\'scan\': Server reload file permissions and update file list.\n"
						  "\'log\': Log file permissions and file list on server side.\n"
						  "\'term\'/\'terminate\': Shutdown server.\n"
						  "\'quit\'/\'exit\': Shutdown admin client.\n")
				case "scan":
					sock.sendto(f"SCAN {PASSWORD}".encode(), SERVER_ADDR)
				case "log":
					sock.sendto(f"LOG {PASSWORD}".encode(), SERVER_ADDR)
				case "term" | "terminate" :
					confirm = input("Are you sure? Type \'yes\' to confirm server termination. Type anything else to cancel.\n"
									"Confirm: ").strip().lower()
					if confirm == "yes":
						sock.sendto(f"TERM {PASSWORD}".encode(), SERVER_ADDR)
					else:
						print("Termination cancelled.\n")
				case "quit" | "exit":
					break
				case _:
					print("Unknown command. Type \'help\' for list of commands.\n")
	finally:
		sock.close()
		print(f"Admin finished!")


if __name__ == "__main__":
	main()
