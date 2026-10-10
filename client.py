import socket
import voice2text
import torch
from pathlib import Path
from qwen_asr import Qwen3ASRModel
HOST = "127.0.0.1"   # 服务端 IP（本机测试用 127.0.0.1）
PORT = 8888


def main():
    input_mode = 1 # 切换输入模式
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # ===== 加载 Qwen3-ASR 模型 =====
    print("正在加载 Qwen3-ASR 模型...")
    model_dir = Path("voice2text/Qwen3-ASR-1___7B")
    asr_model = Qwen3ASRModel.from_pretrained(
        str(model_dir),
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_new_tokens=256,
    )
    print("模型加载完成！")
    try:
        client_socket.connect((HOST, PORT))
        print(f"[客户端] 已连接到 {HOST}:{PORT}")
        print("输入消息发送给服务器，输入 quit 断开连接。")

        while True:
            if input_mode == 1:
                text = input("请输入: ")   # 读取键盘输入
                if text == "":
                    print("text为空")
                    continue
            elif input_mode == 2:
                text = voice2text.v2t(asr_model)
            if text == "quit":
                client_socket.sendall("6.18.\n".encode("utf-8"))
                print("[客户端] 已发送断开请求")
                break

            # 发送文本，必须以 \n 结尾
            client_socket.sendall((text + "\n").encode("utf-8"))

    except ConnectionRefusedError:
        print("[客户端] 连接被拒绝，请确认服务端已启动")
    except KeyboardInterrupt:
        print("\n[客户端] 手动中断")
    finally:
        client_socket.close()
        print("[客户端] 已关闭")


if __name__ == "__main__":
    main()