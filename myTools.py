# 入 Python 的正则表达式模块 re，后面要用 re.match() 判断"某个字是不是中文汉字"。
import re
# 按照标点符号拆分中文语段
def split_by_chinese(text, limit=15):
    # 创建空列表用来保存每一段切片
    segments = []
    # 冲区buf，它用来"攒"当前这一小段——每读一个字就拼进来，等攒够 15 个汉字，就把 buf 存进 segments，然后清空重新攒下一段。
    buf = ""
    count = 0
    for ch in text:
        buf += ch
        # 句号：无论攒了多少字，立刻断句
        if ch == '。':
            segments.append(buf)
            buf, count = "", 0
            continue
        # 如果读取到的是中文字符就让count+1
        # re.match(模式, 字符串)：从字符串开头尝试匹配模式，匹配成功返回首个匹配对象，失败返回 None
        # r'...'：原始字符串，里面的 \u 不会被 Python 提前转义，交给正则处理。
        # [\u4e00-\u9fff]：一个字符类，表示范围在 U+4E00 到 U+9FFF 之间的字符——这正是 Unicode 里常用汉字的编码区间。
        if re.match(r'[\u4e00-\u9fff]', ch):  # 只统计中文汉字
            count += 1
        # 已攒够 limit 个汉字，并且遇到逗号：断句
        if count >= limit and ch == '，':
            segments.append(buf)
            buf, count = "", 0
    # 如果结尾未满15个字就直接添加到segments
    if buf:
        segments.append(buf)
    return segments
def get_a_message(client_socket):
    # 循环接收直到拿到一行完整回复
    recv_buf = b""
    while b"$" not in recv_buf:
        chunk = client_socket.recv(2048)
        if not chunk:
            print("[客户端] 服务端已断开连接")
            return
        recv_buf += chunk
    line, recv_buf = recv_buf.split(b"$", 1)
    return line.decode("utf-8")
