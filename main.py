import asyncio
import re
import ast
import operator
from collections import OrderedDict
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

BOT_TOKEN = "8583616096:AAH1Agap1qVfWhLaRrtThD_TBAgGdJRJ8Ko"

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

class LRUCache:
    def __init__(self, max_size=1000):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
        self.cache[key] = value

user_bot_messages = LRUCache(max_size=1000)

def eval_node(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        left = eval_node(node.left)
        right = eval_node(node.right)
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Неподдерживаемая операция: {type(node.op).__name__}")
        return op(left, right)
    elif isinstance(node, ast.UnaryOp):
        operand = eval_node(node.operand)
        op = OPERATORS.get(type(node.op))
        if op is None:
            raise ValueError(f"Неподдерживаемая операция: {type(node.op).__name__}")
        return op(operand)
    else:
        raise ValueError(f"Неподдерживаемый тип узла: {type(node).__name__}")

def safe_eval(expr: str) -> float:
    expr = expr.replace(',', '.').replace('^', '**')
    expr = re.sub(r'(\d+\.?\d*)\s*\+%\s*(\d+\.?\d*)', r'(\1 + \1 * \2 / 100)', expr)
    expr = re.sub(r'(\d+\.?\d*)\s*-%\s*(\d+\.?\d*)', r'(\1 - \1 * \2 / 100)', expr)
    expr = re.sub(r'(\d+\.?\d*)\s*%\s*(\d+\.?\d*)', r'(\1 * \2 / 100)', expr)
    node = ast.parse(expr, mode='eval')
    return eval_node(node.body)

def format_result(result):
    if isinstance(result, float):
        if result.is_integer():
            return int(result)
        result = round(result, 4)
        return float(str(result).rstrip('0').rstrip('.'))
    return result

def is_spread_calculation(text: str) -> bool:
    if any(op in text for op in ['+', '-', '*', '/', '^', '%', '(', ')']):
        return False
    parts = text.strip().split()
    if len(parts) not in [2, 3]:
        return False
    try:
        for part in parts:
            float(part.replace(',', '.'))
        return True
    except ValueError:
        return False

def calculate_spread_text(text: str) -> str:
    parts = text.strip().split()
    price1 = float(parts[0].replace(',', '.'))
    price2 = float(parts[1].replace(',', '.'))

    spread_percent = abs(price1 - price2) / min(price1, price2) * 100
    result = f"➡️ <b>Спред:</b> <code>{spread_percent:.2f}%</code>"

    if len(parts) == 3:
        coins = float(parts[2].replace(',', '.'))
        profit_usd = abs(price1 - price2) * coins
        result += f"\n\n💸 <b>Макс. прибыль:</b> <code>{profit_usd:.2f}$</code>"

    return result

def calculate_math_text(expression: str) -> str:
    result = safe_eval(expression)
    result = format_result(result)
    return f"➡️ <b>{result}</b>"

async def send_or_edit_message(message: Message, text: str, bot_message_id: int = None):
    if bot_message_id:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=text,
            parse_mode="HTML"
        )
    else:
        bot_message = await message.reply(text, parse_mode="HTML")
        user_bot_messages.set(message.message_id, bot_message.message_id)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    help_text = """
📊 <b>Калькулятор 2 в 1</b>

<b>1️⃣ Математический калькулятор</b>

<code> +  </code> · сложение
<code> -  </code> · вычитание
<code> *  </code> · умножение
<code> /  </code> · деление
<code> ^  </code> · возведение в степень
<code> %  </code> · процент от числа
<code> +% </code> · прибавить процент
<code> -% </code> · вычесть процент

<b>2️⃣ Калькулятор спреда</b>

<b>· спред</b>
<code>[цена1] [цена2]</code> 

<b>· спред + прибыль</b>
<code>[цена1] [цена2] [кол-во]</code>


<i>* разделитель может быть [ . ] или [ , ]
* поддерживаются сложные выражения
* при изменении выражения ответ обновится</i>
"""
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)

async def process_message(message: Message, bot_message_id: int = None):
    if not message.text:
        await send_or_edit_message(message, "<b>❌ Некорректные данные</b>", bot_message_id)
        return

    expression = message.text.strip()

    if not expression:
        if not bot_message_id:
            await message.reply("<b>❌ Некорректные данные</b>")
        return

    try:
        if is_spread_calculation(expression):
            result_text = calculate_spread_text(expression)
        else:
            result_text = calculate_math_text(expression)

        await send_or_edit_message(message, result_text, bot_message_id)
    except Exception:
        await send_or_edit_message(message, "<b>❌ Некорректные данные</b>", bot_message_id)

@dp.message()
async def calculate(message: Message):
    await process_message(message)

@dp.edited_message()
async def calculate_edited(message: Message):
    bot_message_id = user_bot_messages.get(message.message_id)
    await process_message(message, bot_message_id)

async def main():
    print("🚀 Бот запущен и готов к работе!")
    print("Нажмите Ctrl+C для остановки")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")