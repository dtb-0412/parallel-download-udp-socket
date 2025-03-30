import socket

PASSWORD = "admin@1234"
SERVER_ADDR = ("192.168.100.24", 12345)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(f"TERM {PASSWORD}".encode(), SERVER_ADDR)
sock.close()
print(f"Admin finished!")
