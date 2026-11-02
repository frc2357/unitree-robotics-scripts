import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32
import random


class HeartbeatPublisher(Node):
    def __init__(self):
        super().__init__("heartbeat_node")
        # Create a publisher on the '/victim_heart_rate' topic
        self.publisher_ = self.create_publisher(Int32, "victim_heart_rate", 10)
        # Publish data every 1 second
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.get_logger().info("Heartbeat node started. Publishing mock data...")

    def timer_callback(self):
        msg = Int32()
        msg.data = random.randint(60, 100)  # Generate a fake BPM between 60-100
        self.publisher_.publish(msg)
        self.get_logger().info(f"Publishing: {msg.data} BPM")


def main(args=None):
    rclpy.init(args=args)
    node = HeartbeatPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
