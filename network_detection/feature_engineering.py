from scapy.all import sniff


class PacketCapture:

    def __init__(self):
        pass

    def capture_packets(self, count=10):
        """
        Capture live network packets.
        """

        print(f"Capturing {count} packets...\n")

        packets = sniff(count=count)

        print(f"Captured {len(packets)} packets.")

        return packets