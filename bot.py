from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str = "casesolve.sqlite3") -> None:
        self.connection = sqlite3.connect(Path(path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                court_chat_id INTEGER,
                court_title TEXT
            );
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_chat_id INTEGER NOT NULL,
                court_chat_id INTEGER,
                plaintiff_id INTEGER,
                defendant_id INTEGER,
                judge_id INTEGER,
                witnesses TEXT NOT NULL DEFAULT '[]',
                state TEXT NOT NULL DEFAULT 'pending',
                turn TEXT NOT NULL DEFAULT 'plaintiff',
                complainant_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                PRIMARY KEY (chat_id, user_id)
            );
            """
        )
        self.connection.commit()

    def remember_user(self, chat_id: int, user_id: int, username: str | None) -> None:
        self.connection.execute(
            """
            INSERT INTO users(chat_id,user_id,username) VALUES(?,?,?)
            ON CONFLICT(chat_id,user_id) DO UPDATE SET username=excluded.username
            """,
            (chat_id, user_id, username.lower() if username else None),
        )
        self.connection.commit()

    def user_by_username(self, chat_id: int, username: str) -> int | None:
        row = self.connection.execute(
            "SELECT user_id FROM users WHERE chat_id=? AND username=?",
            (chat_id, username.lower().lstrip("@")),
        ).fetchone()
        return int(row["user_id"]) if row else None

    def settings(self, chat_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM settings WHERE chat_id=?", (chat_id,)).fetchone()

    def save_settings(self, chat_id: int, owner_id: int, court_chat_id: int | None = None, title: str = "") -> None:
        self.connection.execute(
            """
            INSERT INTO settings(chat_id,owner_id,court_chat_id,court_title) VALUES(?,?,?,?)
            ON CONFLICT(chat_id) DO UPDATE SET owner_id=excluded.owner_id,
            court_chat_id=COALESCE(excluded.court_chat_id, settings.court_chat_id),
            court_title=COALESCE(NULLIF(excluded.court_title,''), settings.court_title)
            """,
            (chat_id, owner_id, court_chat_id, title),
        )
        self.connection.commit()

    def create_case(self, values: dict[str, Any]) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO cases(source_chat_id,court_chat_id,plaintiff_id,defendant_id,judge_id,
            witnesses,state,turn,complainant_id) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                values["source_chat_id"], values.get("court_chat_id"), values.get("plaintiff_id"),
                values.get("defendant_id"), values.get("judge_id"), json.dumps(values.get("witnesses", [])),
                values.get("state", "pending"), values.get("turn", "plaintiff"), values["complainant_id"],
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def case(self, case_id: int) -> sqlite3.Row | None:
        return self.connection.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()

    def update_case(self, case_id: int, **values: Any) -> None:
        if "witnesses" in values:
            values["witnesses"] = json.dumps(values["witnesses"])
        assignments = ", ".join(f"{key}=?" for key in values)
        self.connection.execute(f"UPDATE cases SET {assignments} WHERE id=?", (*values.values(), case_id))
        self.connection.commit()

    def active_case(self, chat_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """SELECT * FROM cases
               WHERE (court_chat_id=? OR source_chat_id=?)
               AND state NOT IN ('finished','stopped')
               ORDER BY id DESC LIMIT 1""",
            (chat_id, chat_id),
        ).fetchone()

    def ready_case(self, chat_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """SELECT * FROM cases
               WHERE (court_chat_id=? OR source_chat_id=?)
               AND state='ready'
               ORDER BY id DESC LIMIT 1""",
            (chat_id, chat_id),
        ).fetchone()

    def delete_case(self, case_id: int) -> None:
        self.connection.execute("DELETE FROM cases WHERE id=?", (case_id,))
        self.connection.commit()

FACTS = [
    ("снежных барсов", "Снежные барсы не умеют рычать, зато издают мягкие звуки, похожие на мурлыканье."),
    ("сиамских кошек", "Окрас сиамской кошки зависит от температуры кожи: холодные участки становятся темнее."),
    ("осьминогов", "У осьминога три сердца, а его кровь имеет голубой оттенок."),
    ("воронов", "Вороны способны запоминать лица людей и отличать знакомых от незнакомцев."),
    ("пчёл", "Пчёлы передают друг другу направление к цветам с помощью особого танца."),
    ("аксолотлей", "Аксолотли могут восстанавливать конечности и некоторые внутренние органы."),
    ("жирафов", "Язык жирафа может достигать примерно полуметра в длину."),
    ("выдр", "Морские выдры иногда держатся за лапы во сне, чтобы не уплыть друг от друга."),
    ("летучих мышей", "Летучие мыши — единственные млекопитающие, способные к настоящему активному полёту."),
    ("слонов", "Слоны могут узнавать себя в зеркале — признак сложного самосознания."),
    ("пингвинов", "У некоторых видов пингвинов партнёры годами возвращаются к одному гнезду."),
    ("коз", "Козы умеют менять интонацию и используют разные звуки в разных ситуациях."),
    ("воробьёв", "Воробьи могут запоминать порядок предметов и находить спрятанную пищу."),
    ("дельфинов", "У каждого дельфина есть собственный характерный свист, похожий на имя."),
    ("полярных медведей", "Шерсть полярного медведя кажется белой, но отдельные волоски почти прозрачны."),
    ("бабочек", "Бабочки чувствуют вкус не только хоботком, но и рецепторами на лапках."),
    ("муравьёв", "Муравьи могут переносить груз, во много раз превышающий массу их тела."),
    ("собак", "Собаки могут понимать направление взгляда человека и использовать его как подсказку."),
    ("кошек", "Кошки используют медленное моргание как дружелюбный сигнал."),
    ("лошадей", "Лошади спят стоя, но для полноценного отдыха им иногда нужен сон лёжа."),
    ("акул", "Акулы существовали на Земле раньше, чем появились первые деревья."),
    ("морских коньков", "У морских коньков потомство вынашивает самец."),
    ("фламинго", "Розовый цвет фламинго появляется благодаря пигментам в пище."),
    ("панд", "Большая панда может провести за едой до двенадцати часов в день."),
    ("колибри", "Колибри способны зависать в воздухе и летать назад."),
    ("светлячков", "Светлячки светятся благодаря химической реакции с очень высокой эффективностью."),
    ("лисы", "Лисы могут использовать магнитное поле Земли для точного прыжка на добычу."),
    ("кроликов", "Кролики общаются не только звуками, но и движениями носа, ушей и лап."),
    ("пауков", "Некоторые пауки используют паутину как планер, чтобы перемещаться по воздуху."),
    ("китов", "Синий кит — самое крупное животное, когда-либо жившее на планете."),
    ("бобров", "Зубы бобра растут всю жизнь и стачиваются во время работы."),
    ("попугаев", "Некоторые попугаи умеют связывать слова с предметами, а не просто повторять звуки."),
    ("хамелеонов", "Хамелеоны меняют цвет не только для маскировки, но и для общения и регулирования температуры."),
    ("ежей", "Ежи рождаются с мягкими иголками, которые твердеют вскоре после рождения."),
    ("кенгуру", "Кенгуру используют хвост как дополнительную опору при ходьбе."),
    ("коал", "Отпечатки пальцев коал удивительно похожи на человеческие."),
    ("моржей", "Усы моржа настолько чувствительны, что помогают находить пищу на дне."),
    ("пеликанов", "Клюв пеликана может вместить больше воды, чем его желудок."),
    ("страусов", "Глаз страуса больше его мозга."),
    ("улиток", "Некоторые улитки могут впадать в спячку на несколько лет."),
    ("медуз", "У некоторых медуз нет мозга, но есть распределённая нервная сеть."),
    ("черепах", "Некоторые черепахи могут дышать через кожу во время зимовки."),
    ("крокодилов", "Крокодилы глотают камни, которые помогают им нырять и переваривать пищу."),
    ("тигров", "Полосы тигра есть не только на шерсти, но и на коже."),
    ("леопардов", "Леопарды умеют затаскивать добычу на деревья, защищая её от конкурентов."),
    ("сов", "Совы не могут двигать глазами, поэтому поворачивают голову."),
    ("орлов", "Орлы видят детали с большой высоты благодаря особому строению глаз."),
    ("чайки", "Чайки могут пить морскую воду: специальные железы выводят лишнюю соль."),
    ("пингвинов", "Пингвины узнают партнёра и птенца по голосу среди тысяч птиц."),
    ("медоносных барсуков", "Медоносные барсуки известны смелостью и очень плотной кожей."),
    ("опоссумов", "Опоссумы редко болеют бешенством из-за необычно низкой температуры тела."),
    ("мангустов", "Мангусты умеют противостоять некоторым видам змеиного яда."),
    ("лам", "Ламы могут предупреждать стадо об опасности особым сигналом."),
    ("альпак", "Шерсть альпаки очень тёплая и при этом легче овечьей."),
    ("ос", "Осы могут узнавать лица сородичей внутри своей колонии."),
    ("стрекоз", "Стрекозы способны двигать четырьмя крыльями независимо."),
    ("сверчков", "По частоте стрекотания сверчка можно примерно оценить температуру воздуха."),
    ("комаров", "Комаров привлекают углекислый газ, тепло тела и запах кожи."),
    ("пиявок", "Некоторые пиявки используют десятки маленьких зубчиков для укуса."),
    ("морских звёзд", "Морские звёзды не имеют мозга и крови в привычном смысле."),
    ("кораллов", "Кораллы — животные, хотя часто выглядят как растения."),
    ("губок", "Морские губки фильтруют огромные объёмы воды через своё тело."),
    ("кальмаров", "У гигантских кальмаров глаза могут быть размером с футбольный мяч."),
    ("раков", "Раки могут отращивать потерянные клешни, хотя восстановленная клешня сначала меньше."),
    ("крабов", "Крабы ходят боком из-за устройства суставов своих ног."),
    ("белок", "Белки запоминают расположение множества тайников с орехами."),
    ("сусликов", "Некоторые суслики предупреждают сородичей об опасности разными сигналами."),
    ("хомяков", "Щёчные мешки хомяка могут растягиваться почти до плеч."),
    ("мышей", "Мыши могут смеяться ультразвуком во время игры."),
    ("крыс", "Крысы способны учиться помогать друг другу и запоминают добрых сородичей."),
    ("свиней", "Свиньи хорошо обучаются и могут решать задачи с отражением в зеркале."),
    ("коров", "Коровы образуют устойчивые дружеские связи и спокойнее чувствуют себя рядом с друзьями."),
    ("овец", "Овцы способны запоминать лица других овец и людей."),
    ("кур", "Куры издают разные звуки для разных угроз и могут обучать этому цыплят."),
    ("уток", "Утята способны запечатлеть образ первого заботящегося о них существа."),
    ("гусей", "Гуси охраняют стаю и часто предупреждают друг друга о приближении опасности."),
    ("воронков", "Некоторые птицы используют листья или палочки как инструменты."),
    ("дятлов", "У дятлов язык может оборачиваться вокруг черепа и защищать мозг при ударах."),
    ("туканов", "Большой клюв тукана помогает ему отдавать тепло в жарком климате."),
    ("павлинов", "Рисунок на хвосте павлина помогает самке оценивать здоровье самца."),
    ("канареек", "Канарейки могут менять песни в зависимости от окружения."),
    ("жаворонков", "Жаворонки способны петь в полёте, поднимаясь высоко над землёй."),
    ("растений", "Подсолнухи в молодом возрасте поворачиваются вслед за солнцем."),
    ("деревьев", "Некоторые деревья передают химические сигналы соседям об атаке насекомых."),
    ("грибов", "Грибница под землёй может занимать площадь в несколько квадратных километров."),
    ("кактусов", "Колючки кактуса — изменённые листья, которые уменьшают потерю воды."),
    ("бамбука", "Некоторые виды бамбука растут почти метр за сутки."),
    ("мха", "Мхи способны переживать сильное высыхание и оживать после увлажнения."),
    ("подснежников", "Подснежники могут пробиваться через снег благодаря веществам, защищающим клетки от холода."),
    ("океанов", "Океаны производят примерно половину кислорода Земли благодаря микроскопическому планктону."),
    ("облаков", "Облако может весить сотни тонн, хотя его капли распределены на огромной площади."),
    ("молнии", "Молния нагревает воздух вокруг себя до температуры, выше поверхности Солнца."),
    ("радуги", "Радуга на самом деле образует полный круг, но с земли обычно видна только дуга."),
    ("льда", "Лёд плавает, потому что при замерзании вода расширяется и становится менее плотной."),
    ("снега", "Снежинки почти всегда имеют шесть лучей из-за структуры молекул воды."),
    ("луны", "Луна каждый год удаляется от Земли примерно на несколько сантиметров."),
    ("Марса", "На Марсе находится крупнейший известный вулкан Солнечной системы — Олимп."),
    ("Венеры", "На Венере сутки длиннее года из-за очень медленного вращения планеты."),
    ("Сатурна", "Плотность Сатурна настолько мала, что теоретически он мог бы плавать в огромном океане."),
    ("космоса", "В космосе нет привычного звука, потому что звуковым волнам нужна среда."),
    ("человеческого сна", "Во время сна мозг сортирует воспоминания и укрепляет важные связи."),
    ("человеческой кожи", "Кожа — самый большой орган человеческого тела."),
    ("глаз", "Человеческий глаз различает больше оттенков зелёного, чем многих других цветов."),
    ("сердца", "Сердце человека за жизнь совершает миллиарды сокращений."),
    ("памяти", "Запахи часто вызывают особенно яркие воспоминания, потому что связаны с эмоциональными зонами мозга."),
    ("музыки", "Ритм музыки может синхронизировать движения людей, даже если они этого не замечают."),
    ("языка", "В мире существует более семи тысяч языков."),
    ("книг", "Чтение художественных историй может временно усиливать способность понимать чувства других."),
    ("кофе", "Кофеин блокирует рецепторы аденозина — вещества, которое накапливает ощущение усталости."),
    ("мёда", "Правильно хранящийся мёд может оставаться съедобным очень долго."),
    ("шоколада", "Какао-бобы растут прямо на стволе и крупных ветвях дерева какао."),
    ("хлеба", "Дрожжи превращают часть сахаров в углекислый газ, благодаря чему тесто поднимается."),
    ("сыра", "Аромат сыра формируют бактерии и ферменты, которые работают во время созревания."),
    ("ракушек", "Рисунок ракушки часто формируется по математическим законам роста."),
    ("мыльных пузырей", "Мыльные пузыри переливаются, потому что свет отражается от тончайшей плёнки под разными углами."),
    ("магнитов", "У каждого магнита есть северный и южный полюс — отдельного магнитного полюса не наблюдали."),
    ("времени", "Время на спутниках идёт немного иначе, чем на поверхности Земли, поэтому GPS учитывает теорию относительности."),
    ("грома", "Гром возникает из-за резкого расширения воздуха, нагретого молнией."),
]


import asyncio
import html
import logging
import os
import re
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, Message


logging.basicConfig(level=logging.INFO)
db = Database(os.getenv("DATABASE_PATH", "casesolve.sqlite3"))
router = Router()


# ─── FSM States ────────────────────────────────────────────────────────────────

class SetupStates(StatesGroup):
    waiting_for_chat = State()


class CaseStates(StatesGroup):
    waiting_for_roles = State()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def display(user: Any) -> str:
    name = html.escape(getattr(user, "full_name", None) or "Участник")
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def clean_command(text: str | None) -> str:
    return re.sub(r"[^a-zа-яё]", "", (text or "").lower())


async def is_admin(message: Message, user_id: int) -> bool:
    if message.chat.type == ChatType.PRIVATE:
        return False
    member = await message.bot.get_chat_member(message.chat.id, user_id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}


async def owner_id(bot: Bot, chat_id: int) -> int | None:
    settings = db.settings(chat_id)
    if settings:
        return int(settings["owner_id"])
    try:
        admins = await bot.get_chat_administrators(chat_id)
        owner = next((a.user.id for a in admins if a.status == ChatMemberStatus.CREATOR), None)
        if owner:
            db.save_settings(chat_id, owner)
        return owner
    except Exception:
        return None


async def is_owner(message: Message) -> bool:
    if not message.from_user:
        return False
    oid = await owner_id(message.bot, message.chat.id)
    return oid == message.from_user.id


def remember_sender(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE and message.from_user:
        username = message.from_user.username or ""
        db.remember_user(message.chat.id, message.from_user.id, username)


# ─── Markups ───────────────────────────────────────────────────────────────────

def role_markup(case_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚖️ Создать суд", callback_data=f"create:{case_id}")],
    ])


def judge_markup(case_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Остановить", callback_data=f"stop:{case_id}")],
        [InlineKeyboardButton(text="⚖️ Принять решение", callback_data=f"deliberate:{case_id}")],
    ])


def verdict_markup(case_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Сказать итог", callback_data=f"verdict_menu:{case_id}")],
    ])


def verdict_choices(case_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Виновен истец", callback_data=f"verdict:{case_id}:plaintiff")],
        [InlineKeyboardButton(text="Виновен ответчик", callback_data=f"verdict:{case_id}:defendant")],
        [InlineKeyboardButton(text="Ничья", callback_data=f"verdict:{case_id}:draw")],
    ])


def cleanup_markup(case_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 Удалить историю чата и участников", callback_data=f"cleanup:{case_id}")],
    ])


# ─── Role parsing ──────────────────────────────────────────────────────────────

async def parse_roles(message: Message) -> dict[str, Any]:
    """
    Разбирает сообщение формата:
      Истец: @user; Ответчик: @user; Свидетель: @user; Судья: @user
    Поддерживает:
      - text_mention (кликабельное упоминание с ID)
      - mention (@username) — ищем в базе запомненных пользователей
    """
    text = message.text or ""
    ids: list[int] = []

    for entity in (message.entities or []):
        if entity.type == "text_mention" and entity.user:
            ids.append(entity.user.id)
        elif entity.type == "mention":
            username = entity.extract_from(text).lstrip("@")
            found = db.user_by_username(message.chat.id, username)
            if found:
                ids.append(found)

    # Определяем порядок ролей по меткам в тексте
    role_sequence: list[str] = []
    for label in re.findall(
        r"(истец|истица|ответчик|ответчица|свидетел\w*|судья)\s*:",
        text.lower(),
    ):
        if label.startswith("ист"):
            role_sequence.append("plaintiff_id")
        elif label.startswith("ответ"):
            role_sequence.append("defendant_id")
        elif label.startswith("суд"):
            role_sequence.append("judge_id")
        else:
            role_sequence.append("witness")

    role_ids: dict[str, int | None] = {
        "plaintiff_id": None,
        "defendant_id": None,
        "judge_id": None,
    }
    witness_ids: list[int] = []

    for key, user_id in zip(role_sequence, ids):
        if key == "witness":
            if len(witness_ids) < 5:
                witness_ids.append(user_id)
        elif role_ids.get(key) is None:
            role_ids[key] = user_id

    # Если меток не было — раздать по порядку
    if not role_sequence:
        if len(ids) > 0:
            role_ids["plaintiff_id"] = ids[0]
        if len(ids) > 1:
            role_ids["defendant_id"] = ids[1]
        if len(ids) > 2:
            role_ids["judge_id"] = ids[2]
        witness_ids = ids[3:8]

    role_ids["witnesses"] = witness_ids  # type: ignore[assignment]
    return role_ids


# ─── Court logic ───────────────────────────────────────────────────────────────

async def apply_permissions(bot: Bot, case: Any, turn: str) -> None:
    """Даёт право писать только текущему спикеру, остальных мутит."""
    chat_id = case["court_chat_id"]
    if not chat_id:
        return
    import json as _json
    participants = [
        case["plaintiff_id"],
        case["defendant_id"],
        case["judge_id"],
        *_json.loads(case["witnesses"] or "[]"),
    ]
    muted = ChatPermissions(can_send_messages=False)
    allowed = ChatPermissions(can_send_messages=True)
    speaker = case["plaintiff_id"] if turn == "plaintiff" else case["defendant_id"]
    judge_id = case["judge_id"]
    oid = await owner_id(bot, chat_id)

    for uid in participants:
        if not uid:
            continue
        perms = allowed if uid in (speaker, judge_id, oid) else muted
        try:
            await bot.restrict_chat_member(chat_id, uid, perms)
        except Exception:
            pass


async def begin_court(bot: Bot, case_id: int, court_id: int) -> None:
    case = db.case(case_id)
    if not case:
        return
    import json as _json
    witnesses = _json.loads(case["witnesses"] or "[]")
    witness_lines = "".join(
        f"\nСвидетель: <a href='tg://user?id={w}'>участник</a>" for w in witnesses
    )
    await bot.send_message(
        court_id,
        f"⚖️ <b>Суд №{case_id} начинается.</b>\n\n"
        f"Истец: <a href='tg://user?id={case['plaintiff_id']}'>участник</a>\n"
        f"Ответчик: <a href='tg://user?id={case['defendant_id']}'>участник</a>"
        f"{witness_lines}\n\n"
        "Судья может говорить в любой момент.\n"
        "Истец и ответчик выступают по очереди.",
        reply_markup=judge_markup(case_id),
    )
    await apply_permissions(bot, case, "plaintiff")


# ─── Handlers: start / setup / status ──────────────────────────────────────────

@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "⚖️ <b>CaseSolve</b>\n\n"
        "Приветствую. Я организую честный и последовательный суд внутри группы.\n\n"
        "🛠 <b>В группе:</b>\n"
        "• <code>! Суд</code> или <code>/lawsuit</code> — вызвать участника в суд\n"
        "  Ответьте командой на сообщение участника или укажите его через @упоминание\n"
        "• Владелец может назначить роли: Истец, Ответчик, Свидетель, Судья\n\n"
        "🔧 <b>Для владельца:</b>\n"
        "• <code>/setup</code> — настроить чат для проведения судов\n"
        "• <code>/status</code> — показать текущие настройки\n\n"
        "❕️ Команды суда работают только в группах."
    )


@router.message(Command("setup"))
async def setup(message: Message, state: FSMContext) -> None:
    if message.chat.type == ChatType.PRIVATE:
        args = (message.text or "").split(maxsplit=1)
        if len(args) == 2 and args[1].lstrip("-").isdigit():
            chat_id = int(args[1])
            try:
                member = await message.bot.get_chat_member(chat_id, message.from_user.id)
                if member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
                    await message.answer("🔒 Настроить чат может только его администратор или владелец.")
                    return
            except Exception:
                await message.answer("❕️ Не удалось проверить группу. Добавьте меня в группу и выдайте права администратора.")
                return
            db.save_settings(chat_id, message.from_user.id, chat_id, "")
            await message.answer("✔️ Группа настроена для проведения судов.")
            return
        await message.answer(
            "❔️ Укажите ID группы:\n<code>/setup -1001234567890</code>\n\n"
            "ID группы можно узнать через @userinfobot."
        )
        return

    if not message.from_user or not await is_admin(message, message.from_user.id):
        await message.answer("🔒 Только администратор может настроить чат для судов.")
        return
    db.save_settings(message.chat.id, message.from_user.id, message.chat.id, message.chat.title or "")
    await message.answer("✔️ Этот чат настроен как площадка для судов.")


@router.message(Command("status"))
async def status(message: Message) -> None:
    settings = db.settings(message.chat.id)
    if not settings:
        await message.answer("❕️ Чат для судов ещё не настроен. Используйте /setup.")
        return
    court = html.escape(settings["court_title"] or str(settings["court_chat_id"]))
    await message.answer(f"⚙️ Чат для судов: <b>{court}</b>\nСтатус: готов к новым делам.")


# ─── Handler: new member ───────────────────────────────────────────────────────

@router.message(F.new_chat_members)
async def on_join(message: Message) -> None:
    me = await message.bot.get_me()
    for member in (message.new_chat_members or []):
        if member.id == me.id:
            await message.answer(
                "⚖️ <b>CaseSolve</b> теперь в этой группе.\n\n"
                "Я помогаю организовывать справедливые судебные разбирательства.\n\n"
                "🛠 Команды:\n"
                "• <code>! Суд</code> или <code>/lawsuit</code> — вызвать участника\n"
                "• <code>/setup</code> — настроить чат (для владельца)\n"
                "• <code>/status</code> — текущие настройки\n\n"
                "Для начала работы владелец должен выполнить <code>/setup</code>."
            )


# ─── Handler: roles input (FSM) ────────────────────────────────────────────────

@router.message(CaseStates.waiting_for_roles)
async def receive_roles(message: Message, state: FSMContext) -> None:
    remember_sender(message)
    if not message.from_user or not await is_admin(message, message.from_user.id):
        return
    roles = await parse_roles(message)
    if not roles["plaintiff_id"] or not roles["defendant_id"]:
        await message.answer(
            "❕️ <b>Не нашёл Истца или Ответчика.</b>\n\n"
            "Telegram передаёт ID пользователя только через кликабельное упоминание.\n\n"
            "Как это сделать:\n"
            "1. Начните вводить <code>@username</code>\n"
            "2. Выберите пользователя из <b>выпадающего списка</b> Telegram\n"
            "3. Имя станет синим — это значит ID передан\n\n"
            "Или попросите участников написать хотя бы одно сообщение в этой группе "
            "— тогда бот запомнит их и сможет найти по @username."
        )
        return
    settings = db.settings(message.chat.id)
    if not settings:
        await message.answer("❕️ Сначала настройте чат командой /setup.")
        await state.clear()
        return
    case_id = db.create_case({
        **roles,
        "judge_id": roles["judge_id"] or settings["owner_id"],
        "source_chat_id": message.chat.id,
        "court_chat_id": settings["court_chat_id"],
        "complainant_id": message.from_user.id,
        "state": "ready",
    })
    await state.clear()
    await message.answer(
        f"🗃 <b>Дело №{case_id} подготовлено.</b>\n\n"
        "Напишите свидетелей следующим сообщением:\n"
        "<code>Свидетель: @юзер; Свидетель: @юзер</code>\n\n"
        "Или отправьте <b>«без свидетелей»</b> чтобы сразу начать суд.",
        reply_markup=role_markup(case_id),
    )


# ─── Handler: main text dispatcher ────────────────────────────────────────────

@router.message(F.text)
async def text_dispatcher(message: Message, state: FSMContext) -> None:
    remember_sender(message)
    if not message.from_user:
        return
    text = message.text or ""

    # 1. Ожидание ввода свидетелей для дела в статусе ready
    if message.chat.type != ChatType.PRIVATE and await is_owner(message):
        ready = db.ready_case(message.chat.id)
        if ready:
            tl = text.strip().lower()
            no_witnesses = any(w in tl for w in ["без свидетелей", "без свид", "нет свид"])
            has_witness = "свидетел" in tl
            if no_witnesses or has_witness:
                witness_ids: list[int] = []
                if not no_witnesses:
                    roles = await parse_roles(message)
                    witness_ids = (roles.get("witnesses") or [])[:5]
                db.update_case(ready["id"], witnesses=witness_ids, state="active", turn="plaintiff")
                court_id = ready["court_chat_id"] or message.chat.id
                await begin_court(message.bot, int(ready["id"]), court_id)
                return

    # 2. Очередь выступлений в активном суде
    if message.chat.type != ChatType.PRIVATE:
        active = db.active_case(message.chat.id)
        if active and active["state"] == "active":
            uid = message.from_user.id
            if uid == active["plaintiff_id"] and active["turn"] == "plaintiff":
                db.update_case(active["id"], turn="defendant")
                await apply_permissions(message.bot, active, "defendant")
                await message.answer("⚖️ Слово передаётся <b>Ответчику</b>.")
                return
            if uid == active["defendant_id"] and active["turn"] == "defendant":
                db.update_case(active["id"], turn="plaintiff")
                await apply_permissions(message.bot, active, "plaintiff")
                await message.answer("⚖️ Слово снова передаётся <b>Истцу</b>.")
                return

    # 3. Команды суда (! Суд / /lawsuit)
    command = clean_command(text)
    is_lawsuit = command in {"суд", "lawsuit"} or command.startswith("суд")
    if not is_lawsuit:
        return

    if message.chat.type == ChatType.PRIVATE:
        await message.answer("❕️ Команды суда работают только внутри группы.")
        return

    settings = db.settings(message.chat.id)
    if not settings:
        if await is_admin(message, message.from_user.id):
            db.save_settings(message.chat.id, message.from_user.id, message.chat.id, message.chat.title or "")
            settings = db.settings(message.chat.id)
        else:
            await message.answer("❕️ Владелец ещё не настроил чат для судов. Выполните /setup.")
            return

    is_admin_user = await is_admin(message, message.from_user.id)

    # Администратор вводит команду → просим роли
    if is_admin_user:
        await state.set_state(CaseStates.waiting_for_roles)
        await message.answer(
            "❔️ <b>Кто участвует в суде?</b>\n\n"
            "Отправьте сообщение в формате:\n"
            "<code>Истец: @юзер; Ответчик: @юзер; Свидетель: @юзер; Судья: @юзер</code>\n\n"
            "Свидетелей максимум 5. Для начала суда достаточно Истца и Ответчика.\n\n"
            "❕️ При вводе @username выбирайте пользователя из выпадающего списка Telegram "
            "— тогда бот получит его ID."
        )
        return

    # Обычный участник — вызывает другого в суд
    roles = await parse_roles(message)
    target = roles.get("defendant_id")
    if not target:
        await message.answer(
            "❔️ Чтобы вызвать участника в суд:\n"
            "• Ответьте на его сообщение командой <code>! Суд</code>\n"
            "• Или напишите <code>! Суд @username</code> (выберите из списка)"
        )
        return

    case_id = db.create_case({
        "source_chat_id": message.chat.id,
        "court_chat_id": settings["court_chat_id"],
        "plaintiff_id": message.from_user.id,
        "defendant_id": target,
        "judge_id": settings["owner_id"],
        "complainant_id": message.from_user.id,
    })
    await message.answer(
        f"‼️\n"
        f"{display(message.from_user)} вызывает в суд "
        f"<a href='tg://user?id={target}'>участника</a>.\n"
        f"‼️",
        reply_markup=role_markup(case_id),
    )
    oid = await owner_id(message.bot, message.chat.id)
    if oid:
        await message.answer(
            f"✔️\nВызван <a href='tg://user?id={oid}'>Владелец</a> группы.\n"
            "Ожидайте создания суда.\n✔️"
        )


# ─── Callback: create case ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("create:"))
async def create_case_callback(callback: CallbackQuery) -> None:
    case_id = int(callback.data.split(":")[1])
    case = db.case(case_id)
    if not case or not callback.message:
        await callback.answer("Дело не найдено.", show_alert=True)
        return
    if not await is_owner(callback.message):
        await callback.answer("🔒 Только владелец может создать суд.", show_alert=True)
        return
    if not case["plaintiff_id"] or not case["defendant_id"]:
        await callback.answer("Нужны Истец и Ответчик.", show_alert=True)
        return
    db.update_case(case_id, state="ready")
    await callback.message.answer(
        f"🗃 <b>Суд №{case_id} создаётся.</b>\n\n"
        "Напишите свидетелей следующим сообщением:\n"
        "<code>Свидетель: @юзер; Свидетель: @юзер</code>\n\n"
        "Или отправьте <b>«без свидетелей»</b> чтобы сразу начать суд.",
    )
    await callback.answer("✔️ Суд создан")


# ─── Callback: stop ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("stop:"))
async def stop_case(callback: CallbackQuery) -> None:
    case_id = int(callback.data.split(":")[1])
    case = db.case(case_id)
    if not case or not callback.message:
        return
    if not case["judge_id"] or callback.from_user.id != case["judge_id"]:
        await callback.answer("🔒 Только судья может остановить суд.", show_alert=True)
        return
    db.update_case(case_id, state="stopped")
    await callback.message.answer("🛑 <b>Суд остановлен.</b>")
    await callback.answer()


# ─── Callback: deliberate ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("deliberate:"))
async def deliberate(callback: CallbackQuery) -> None:
    case_id = int(callback.data.split(":")[1])
    case = db.case(case_id)
    if not case or not callback.message:
        return
    if callback.from_user.id != case["judge_id"]:
        await callback.answer("🔒 Только судья принимает решение.", show_alert=True)
        return
    db.update_case(case_id, state="deliberating")
    muted = ChatPermissions(can_send_messages=False)
    import json as _json
    court_id = case["court_chat_id"]
    if court_id:
        participants = [
            case["plaintiff_id"],
            case["defendant_id"],
            *_json.loads(case["witnesses"] or "[]"),
        ]
        for uid in participants:
            if uid:
                try:
                    await callback.bot.restrict_chat_member(court_id, uid, muted)
                except Exception:
                    pass
    await callback.message.answer(
        "💼 <b>Суд удаляется в совещательную комнату для принятия решения.</b>\n"
        "Ожидайте объявления итогов.",
        reply_markup=verdict_markup(case_id),
    )
    await callback.answer()


# ─── Callback: verdict menu ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("verdict_menu:"))
async def verdict_menu(callback: CallbackQuery) -> None:
    case_id = int(callback.data.split(":")[1])
    case = db.case(case_id)
    if not case or not callback.message:
        return
    if callback.from_user.id != case["judge_id"]:
        await callback.answer("🔒 Только судья выносит приговор.", show_alert=True)
        return
    await callback.message.answer(
        "⚖️ <b>Вынести решение:</b>",
        reply_markup=verdict_choices(case_id),
    )
    await callback.answer()


# ─── Callback: verdict ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("verdict:"))
async def verdict(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    case_id = int(parts[1])
    result = parts[2]
    case = db.case(case_id)
    if not case or not callback.message:
        return
    if callback.from_user.id != case["judge_id"]:
        await callback.answer("🔒 Только судья выносит приговор.", show_alert=True)
        return
    db.update_case(case_id, state="finished")
    verdicts = {
        "plaintiff": "⚖️ <b>Решение суда:</b> виновен <b>Истец</b>.",
        "defendant": "⚖️ <b>Решение суда:</b> виновен <b>Ответчик</b>.",
        "draw": "⚖️ <b>Решение суда:</b> ничья. Обе стороны признаны равно ответственными.",
    }
    await callback.message.answer(
        verdicts.get(result, "⚖️ Решение вынесено.") +
        "\n\nНаказание объявит судья.",
        reply_markup=cleanup_markup(case_id),
    )
    await callback.answer()


# ─── Callback: cleanup ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cleanup:"))
async def cleanup(callback: CallbackQuery) -> None:
    case_id = int(callback.data.split(":")[1])
    case = db.case(case_id)
    if not case or not callback.message:
        return
    if not await is_owner(callback.message):
        await callback.answer("🔒 Только владелец может завершить и очистить дело.", show_alert=True)
        return
    import json as _json
    court_id = case["court_chat_id"]
    oid = await owner_id(callback.bot, court_id) if court_id else None
    participants = [
        case["plaintiff_id"],
        case["defendant_id"],
        case["judge_id"],
        *_json.loads(case["witnesses"] or "[]"),
    ]
    if court_id:
        for uid in participants:
            if uid and uid != oid:
                try:
                    await callback.bot.ban_chat_member(court_id, uid)
                    await callback.bot.unban_chat_member(court_id, uid)
                except Exception:
                    pass
    db.delete_case(case_id)
    await callback.message.answer("🗑 <b>Дело закрыто.</b> Участники удалены из судебного чата.")
    await callback.answer()


# ─── Facts loop ───────────────────────────────────────────────────────────────

async def facts_loop(bot: Bot) -> None:
    index = 0
    while True:
        await asyncio.sleep(2 * 60 * 60)
        subject, fact = FACTS[index % len(FACTS)]
        index += 1
        chats = db.all_court_chats()
        for row in chats:
            try:
                await bot.send_message(
                    int(row["court_chat_id"]),
                    f"💼 <b>Интересный факт про {subject}!</b>\n\n"
                    f"°{html.escape(fact)} >:3°"
                )
            except Exception:
                pass


# ─── Keep-alive HTTP server ────────────────────────────────────────────────────

async def keep_alive() -> None:
    from aiohttp import web

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info("Keep-alive server on :%d", port)


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await keep_alive()
    asyncio.create_task(facts_loop(bot))
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
