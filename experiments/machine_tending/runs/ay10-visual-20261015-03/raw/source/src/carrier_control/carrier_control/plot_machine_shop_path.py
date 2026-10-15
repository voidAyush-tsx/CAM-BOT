#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

import numpy as np
import matplotlib.pyplot as plt

from sensor_msgs.msg import JointState


class JointStateRecorder(Node):

    def __init__(self):

        super().__init__('machine_shop_path_recorder')

        self.joint_names = [
            'shoulder_pan_joint',
            'shoulder_lift_joint',
            'elbow_joint',
            'wrist_1_joint',
            'wrist_2_joint',
            'wrist_3_joint'
        ]

        self.samples = []

        self.subscription = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_callback,
            10
        )

        self.get_logger().info(
            'Recording /joint_states...'
        )

    def joint_callback(self, msg):

        positions = []

        for joint in self.joint_names:

            if joint not in msg.name:
                return

            index = msg.name.index(joint)

            positions.append(
                msg.position[index]
            )

        self.samples.append(
            positions
        )


def plot_joint_trajectory(samples):

    data = np.array(samples)

    if len(data) < 10:

        print('Not enough joint-state samples.')

        return

    # =========================================================
    # APPROXIMATE UR5 FORWARD KINEMATICS
    #
    # Standard UR5 dimensions
    # =========================================================

    d1 = 0.089159
    a2 = -0.425
    a3 = -0.39225
    d4 = 0.10915
    d5 = 0.09465
    d6 = 0.0823

    def dh_transform(a, alpha, d, theta):

        ca = np.cos(alpha)
        sa = np.sin(alpha)

        ct = np.cos(theta)
        st = np.sin(theta)

        return np.array([
            [ct, -st * ca, st * sa, a * ct],
            [st, ct * ca, -ct * sa, a * st],
            [0.0, sa, ca, d],
            [0.0, 0.0, 0.0, 1.0]
        ])

    def forward_kinematics(q):

        q1, q2, q3, q4, q5, q6 = q

        T = np.eye(4)

        transforms = [

            dh_transform(
                0.0,
                np.pi / 2,
                d1,
                q1
            ),

            dh_transform(
                a2,
                0.0,
                0.0,
                q2
            ),

            dh_transform(
                a3,
                0.0,
                0.0,
                q3
            ),

            dh_transform(
                0.0,
                np.pi / 2,
                d4,
                q4
            ),

            dh_transform(
                0.0,
                -np.pi / 2,
                d5,
                q5
            ),

            dh_transform(
                0.0,
                0.0,
                d6,
                q6
            )
        ]

        for A in transforms:

            T = T @ A

        return T[:3, 3]

    # =========================================================
    # CALCULATE TCP PATH
    # =========================================================

    xyz = []

    for q in data:

        xyz.append(
            forward_kinematics(q)
        )

    xyz = np.array(xyz)

    x = xyz[:, 0]
    y = xyz[:, 1]
    z = xyz[:, 2]

    # =========================================================
    # 3D FIGURE
    # =========================================================

    fig = plt.figure(
        figsize=(10, 8)
    )

    ax = fig.add_subplot(
        111,
        projection='3d'
    )

    # Trajectory

    ax.plot(
        x,
        y,
        z,
        linewidth=2,
        label='Robot TCP Path'
    )

    # Start

    ax.scatter(
        x[0],
        y[0],
        z[0],
        s=80,
        marker='o',
        label='Start'
    )

    # End

    ax.scatter(
        x[-1],
        y[-1],
        z[-1],
        s=80,
        marker='X',
        label='End'
    )

    # =========================================================
    # MARK APPROXIMATE STATION LOCATIONS
    #
    # Find samples where the robot is nearly stationary.
    # =========================================================

    # Plot every 50th sample as a small station/path marker

    ax.scatter(
        x[::50],
        y[::50],
        z[::50],
        s=15,
        alpha=0.5
    )

    # =========================================================
    # LABELS
    # =========================================================

    ax.set_xlabel(
        'X Position (m)'
    )

    ax.set_ylabel(
        'Y Position (m)'
    )

    ax.set_zlabel(
        'Z Position (m)'
    )

    ax.set_title(
        'UR5 Machine-Shop Cycle — 3D TCP Path'
    )

    ax.grid(True)

    ax.legend()

    # Equal-ish aspect ratio

    max_range = max(
        x.max() - x.min(),
        y.max() - y.min(),
        z.max() - z.min()
    )

    x_mid = (x.max() + x.min()) / 2
    y_mid = (y.max() + y.min()) / 2
    z_mid = (z.max() + z.min()) / 2

    ax.set_xlim(
        x_mid - max_range / 2,
        x_mid + max_range / 2
    )

    ax.set_ylim(
        y_mid - max_range / 2,
        y_mid + max_range / 2
    )

    ax.set_zlim(
        z_mid - max_range / 2,
        z_mid + max_range / 2
    )

    plt.tight_layout()

    output = (
        'machine_shop_3d_path.png'
    )

    plt.savefig(
        output,
        dpi=300,
        bbox_inches='tight'
    )

    print()
    print('==========================================')
    print('3D TRAJECTORY GENERATED')
    print('==========================================')
    print(f'Samples: {len(samples)}')
    print(f'Path X range: {x.min():.3f} → {x.max():.3f} m')
    print(f'Path Y range: {y.min():.3f} → {y.max():.3f} m')
    print(f'Path Z range: {z.min():.3f} → {z.max():.3f} m')
    print()
    print(f'Saved:')
    print(output)
    print('==========================================')

    plt.show()


def main():

    rclpy.init()

    node = JointStateRecorder()

    try:

        print()
        print('==========================================')
        print(' MACHINE SHOP TRAJECTORY RECORDER')
        print('==========================================')
        print()
        print('Start your machine-shop cycle now.')
        print()
        print('Press Ctrl+C AFTER the complete cycle.')
        print()

        rclpy.spin(node)

    except KeyboardInterrupt:

        print()
        print('Recording stopped.')
        print(
            f'Collected {len(node.samples)} samples.'
        )

    finally:

    	samples = node.samples
	
    	node.destroy_node()

    	plot_joint_trajectory(samples)

    	if rclpy.ok():
        	rclpy.shutdown()


if __name__ == '__main__':

    main()
