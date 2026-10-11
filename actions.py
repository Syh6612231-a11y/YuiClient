
class HomeStatus:
    light_on: bool = False          # 灯是否打开
    airconditioner_on: bool = False   # 空调是否打开
    tea_ready: bool = False         # 茶是否泡好
    food_ready: bool = False        # 饭是否做好
    cleaning_done: bool = False     # 卫生是否打扫完

    def to_prompt(self) -> str:
        lines = [
            "请留意当前的家庭状态：",
            f"- 灯：{'开' if self.light_on else '关'}",
            f"- 空调：{'开' if self.airconditioner_on else '关'}",
            f"- 茶：{'已泡好' if self.tea_ready else '还没泡好'}",
            f"- 饭：{'已做好' if self.food_ready else '还没做'}",
            f"- 卫生：{'已打扫' if self.cleaning_done else '未打扫'}",
            "不要重复执行任务。"
        ]
        return "\n".join(lines)
def nothing(home_status):
    print("什么都不做")

def turn_on(home_status):
    print("开灯")
    home_status.light_on = True

def turn_off(home_status):
    print("关灯")
    home_status.light_on = False

def open_airconditioner(home_status):
    print("打开空调")
    home_status.airconditioner_on = True

def close_airconditioner(home_status):
    print("关闭空调")
    home_status.airconditioner_on = False

def tea(home_status):
    print("泡茶")
    home_status.tea_ready = True

def food(home_status):
    print("做饭")
    home_status.food_ready = True

def clean(home_status):
    print("打扫卫生")
    home_status.cleaning_done = True

# 操作码 -> 函数 的映射
actions = {
    0: nothing,
    1: turn_on,
    2: turn_off,
    3: open_airconditioner,
    4: close_airconditioner,
    5: tea,
    6: food,
    7: clean,
}

def do_action(home_status,control_code):
    action=actions[control_code]
    action(home_status)