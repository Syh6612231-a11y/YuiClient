import socket
import voice2text
import torch
from pathlib import Path
from qwen_asr import Qwen3ASRModel
import TTS
import myTools
import actions
HOST = "127.0.0.1" # 服务端 IP（本机测试用 127.0.0.1）
PORT = 8888


def main():
    text=""
    input_mode = 2 # 切换输入模式
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    home_status = actions.HomeStatus()
    # ===== 加载 Qwen3-ASR 模型 =====
    print("正在加载 Qwen3-ASR 模型...")
    model_dir = Path("voice2text/Qwen3-ASR-1___7B")
    asr_model = Qwen3ASRModel.from_pretrained(
        str(model_dir),
        dtype=torch.bfloat16,
        device_map="cuda:0",
        max_new_tokens=512,
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
            if text == "团子拜拜":
                client_socket.sendall("6.18$".encode("utf-8"))
                print("[客户端] 已发送断开请求")
                break
            print(f"玉舟哥哥说：{text}")
            # 发送文本，必须以 $ 结尾
            client_socket.sendall((text + "$").encode("utf-8"))
            client_socket.sendall((home_status.to_prompt() + "$").encode("utf-8"))
            # 接收缓存必须定义在外层，不然会丢失信息
            recv_buf = b""
            reply,recv_buf = myTools.get_a_message(client_socket,recv_buf)
            control_code_str,recv_buf = myTools.get_a_message(client_socket,recv_buf)
            sentiment_label,recv_buf = myTools.get_a_message(client_socket,recv_buf) # 接收情感标签
            sentiment_confidence,recv_buf = myTools.get_a_message(client_socket,recv_buf) # 接收情感标签可信度（这是一个浮点数，需要做类型转换）
            print(f"由比滨结衣：{reply}")
            print(f"控制代码：{control_code_str}")
            print(f"情感标签：{sentiment_label}")
            print(f"情感可信度{sentiment_confidence}")
            if control_code_str!="":
                for ch in control_code_str:
                    code = int(ch)
                    actions.do_action(home_status, code)
                print(home_status.to_prompt())
            # ---------- 调用语音生成 ----------
            segments = myTools.split_by_chinese(reply, limit=12)
            TTS.segments2voice(segments,"happiness",sentiment_confidence)
    except ConnectionRefusedError:
        print("[客户端] 连接被拒绝，请确认服务端已启动")
    except KeyboardInterrupt:
        print("\n[客户端] 手动中断")
    finally:
        client_socket.close()
        print("[客户端] 已关闭")


if __name__ == "__main__":
    main()