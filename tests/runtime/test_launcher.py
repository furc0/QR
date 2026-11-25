import socket

from qr_server.launcher import create_server_socket


def test_launcher_skips_a_port_that_is_already_in_use():
    occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    occupied_port = occupied.getsockname()[1]
    selected = None
    try:
        selected, selected_port = create_server_socket(occupied_port)
        assert selected_port > occupied_port
        assert selected.getsockname() == ("127.0.0.1", selected_port)
    finally:
        if selected is not None:
            selected.close()
        occupied.close()
