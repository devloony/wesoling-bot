import asyncio, logging, os, random, re, sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN=os.getenv('BOT_TOKEN')
if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN не задан')
ADMIN_ID=7146654831
MANAGER_USERNAME='WesolingManager'
PAY_USERNAME='oplatawesoling'
RULES_USERNAME='WesolingRules'
DB='wesoling.db'

bot=Bot(BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp=Dispatcher()

# ---------- DB ----------
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db(); x=c.cursor()
    x.execute('''CREATE TABLE IF NOT EXISTS tournaments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,format TEXT NOT NULL DEFAULT '1x1',
      max_teams INTEGER NOT NULL DEFAULT 16,entry_fee INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'active',created_at TEXT NOT NULL DEFAULT '')''')
    x.execute('''CREATE TABLE IF NOT EXISTS applications(
      id INTEGER PRIMARY KEY AUTOINCREMENT,tournament_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
      username TEXT,nickname TEXT NOT NULL DEFAULT '',timezone TEXT NOT NULL DEFAULT '',game_id TEXT NOT NULL DEFAULT '',
      payment TEXT NOT NULL DEFAULT '',tg_username TEXT NOT NULL DEFAULT '',p2_nickname TEXT NOT NULL DEFAULT '',
      p2_timezone TEXT NOT NULL DEFAULT '',p2_game_id TEXT NOT NULL DEFAULT '',p2_tg_username TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL DEFAULT '')''')
    x.execute('''CREATE TABLE IF NOT EXISTS wallets(user_id INTEGER PRIMARY KEY,username TEXT,balance INTEGER NOT NULL DEFAULT 0)''')
    x.execute('''CREATE TABLE IF NOT EXISTS wallet_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount INTEGER,reason TEXT,created_at TEXT)''')
    for col,definition in [
      ('format',"TEXT NOT NULL DEFAULT '1x1'"),('max_teams','INTEGER NOT NULL DEFAULT 16'),('entry_fee','INTEGER NOT NULL DEFAULT 0')]:
        try:x.execute(f'ALTER TABLE tournaments ADD COLUMN {col} {definition}')
        except sqlite3.OperationalError:pass
    cols=[('p2_nickname',"TEXT NOT NULL DEFAULT ''"),('p2_timezone',"TEXT NOT NULL DEFAULT ''"),('p2_game_id',"TEXT NOT NULL DEFAULT ''"),('p2_tg_username',"TEXT NOT NULL DEFAULT ''")]
    for col,d in cols:
        try:x.execute(f'ALTER TABLE applications ADD COLUMN {col} {d}')
        except sqlite3.OperationalError:pass
    c.commit(); c.close()

def now():return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def q(sql,args=(),one=False):
    c=db(); r=c.execute(sql,args); out=r.fetchone() if one else r.fetchall(); c.close(); return out

def execute(sql,args=()):
    c=db(); r=c.execute(sql,args); c.commit(); v=r.lastrowid; c.close(); return v

def admin(uid):return uid==ADMIN_ID

def clean_at(v):
    v=(v or '').strip()
    return v if re.fullmatch(r'@[A-Za-z0-9_]{5,32}',v) else None

def clean_id(v):return v.strip() if re.fullmatch(r'\d+',v.strip()) else None

def wallet(uid,username=None):
    r=q('SELECT balance FROM wallets WHERE user_id=?',(uid,),True)
    if not r: execute('INSERT INTO wallets(user_id,username,balance) VALUES(?,?,0)',(uid,username)); return 0
    if username: execute('UPDATE wallets SET username=? WHERE user_id=?',(username,uid))
    return r['balance']

def change_coins(uid,amount,reason,username=None):
    balance=wallet(uid,username)+amount
    execute('UPDATE wallets SET balance=? WHERE user_id=?',(balance,uid))
    execute('INSERT INTO wallet_log(user_id,amount,reason,created_at) VALUES(?,?,?,?)',(uid,amount,reason,now()))
    return balance

def spend(uid,amount,reason):
    if wallet(uid)<amount:return False
    change_coins(uid,-amount,reason); return True

def tournaments(active=False):
    return q('SELECT * FROM tournaments '+('WHERE status="active" ' if active else '')+'ORDER BY id DESC')
def tournament(tid):return q('SELECT * FROM tournaments WHERE id=?',(tid,),True)
def apps(tid,status='accepted'):return q('SELECT * FROM applications WHERE tournament_id=? AND status=? ORDER BY id',(tid,status))
def existing(tid,uid):return q("SELECT id,status FROM applications WHERE tournament_id=? AND user_id=? AND status IN ('pending','accepted') LIMIT 1",(tid,uid),True)

# ---------- FSM ----------
class Reg(StatesGroup):
    tournament=State(); p1_nick=State(); p1_tz=State(); p1_id=State(); p1_tg=State(); p2_nick=State(); p2_tz=State(); p2_id=State(); p2_tg=State()
class Create(StatesGroup): name=State(); fmt=State(); teams=State(); fee=State()
class Buy(StatesGroup): amount=State()

# ---------- UI ----------
def kb(rows):return InlineKeyboardMarkup(inline_keyboard=rows)
def tbutton(t,prefix):return InlineKeyboardButton(text=f"🏆 {t['name']} ({len(apps(t['id']))}/{t['max_teams']})",callback_data=f'{prefix}:{t["id"]}')

def menu():return kb([
 [InlineKeyboardButton(text='📝 Регистрация',callback_data='menu_reg'),InlineKeyboardButton(text='🛒 Магазин',callback_data='shop')],
 [InlineKeyboardButton(text='📜 Правила',callback_data='rules'),InlineKeyboardButton(text='💬 Поддержка',callback_data='help')]
])

async def setup():
    await bot.set_my_commands([BotCommand(command=x[0],description=x[1]) for x in [('start','Запуск'),('help','Поддержка'),('reg','Регистрация'),('rules','Правила'),('shop','Магазин'),('balance','Баланс'),('list','Участники'),('setka','Сетка'),('admin','Админ-панель'),('give','Выдать WesoCoins')]])

# ---------- Commands ----------
@dp.message(Command('start'))
async def start(m:Message):
    wallet(m.from_user.id,m.from_user.username)
    await m.answer('👋 <b>Добро пожаловать в Wesoling Tournament!</b>\n\nЗдесь можно регистрироваться на турниры, получать и тратить <b>WesoCoins</b>.',reply_markup=menu())

@dp.message(Command('help'))
async def help_(m:Message):await m.answer(f'💬 Поддержка: @{MANAGER_USERNAME}\n\nДля оплаты: @{PAY_USERNAME}')
@dp.callback_query(F.data=='help')
async def help_cb(c:CallbackQuery):await c.answer();await c.message.answer(f'💬 Поддержка: @{MANAGER_USERNAME}')
@dp.message(Command('rules'))
async def rules(m:Message):await m.answer(f'📖 Правила: https://t.me/{RULES_USERNAME}')
@dp.callback_query(F.data=='rules')
async def rules_cb(c:CallbackQuery):await c.answer();await c.message.answer(f'📖 Правила: https://t.me/{RULES_USERNAME}')

@dp.message(Command('balance'))
async def balance(m:Message):await m.answer(f'💰 Твой баланс: <b>{wallet(m.from_user.id,m.from_user.username)} WesoCoins</b>')

# ---------- Shop ----------
UC=[(60,97),(120,196),(180,296),(300,476),(360,566)]
@dp.message(Command('shop'))
async def shop(m:Message):await show_shop(m)
@dp.callback_query(F.data=='shop')
async def shop_cb(c:CallbackQuery):await c.answer();await show_shop(c.message)
async def show_shop(m):
    text='🛒 <b>Магазин Wesoling</b>\n\n💰 <b>WesoCoins</b>\n1 ₽ = 1 WesoCoin.\n\n🎟 <b>UC</b>\n'
    rows=[]
    for uc,price in UC: text+=f'• {uc} UC — <b>{price} WesoCoins</b>\n'; rows.append([InlineKeyboardButton(text=f'🎮 Купить {uc} UC — {price} WC',callback_data=f'buyuc:{uc}:{price}')])
    text+='\n💳 Чтобы купить WesoCoins, выбери покупку и напиши менеджеру.\n'
    rows.append([InlineKeyboardButton(text='💰 Купить WesoCoins',callback_data='buycoins')])
    await m.answer(text,reply_markup=kb(rows))

@dp.callback_query(F.data=='buycoins')
async def buycoins(c:CallbackQuery,state:FSMContext):
    await c.answer();await c.message.answer(f'💰 <b>Покупка WesoCoins</b>\n\nКурс: <b>1 ₽ = 1 WesoCoin</b>.\n\nНапиши менеджеру @{MANAGER_USERNAME}, укажи количество WesoCoins и способ оплаты.')

@dp.callback_query(F.data.startswith('buyuc:'))
async def buyuc(c:CallbackQuery):
    _,uc,price=c.data.split(':');uc=int(uc);price=int(price)
    if not spend(c.from_user.id,price,f'Покупка {uc} UC'):await c.answer('Недостаточно WesoCoins.',show_alert=True);return
    await c.message.answer(f'✅ Покупка оформлена: <b>{uc} UC</b>.\n\nНапишите @{MANAGER_USERNAME} для получения UC.\nЕсли у вас бан — @{PAY_USERNAME}')
    await c.answer('Оплата списана')

# ---------- Registration ----------
@dp.message(Command('reg'))
async def reg(m:Message,state:FSMContext):await start_reg(m,state)
@dp.callback_query(F.data=='menu_reg')
async def menu_reg(c:CallbackQuery,state:FSMContext):await c.answer();await start_reg(c.message,state)
async def start_reg(m,state):
    await state.clear(); ts=tournaments(True)
    rows=[[tbutton(t,'reg') ] for t in ts if len(apps(t['id']))<t['max_teams']]
    if not rows:await m.answer('📭 Сейчас нет доступных турниров.');return
    await m.answer('📝 <b>Выберите турнир:</b>',reply_markup=kb(rows));await state.set_state(Reg.tournament)

@dp.callback_query(F.data.startswith('reg:'))
async def reg_t(c:CallbackQuery,state:FSMContext):
    tid=int(c.data.split(':')[1]);t=tournament(tid)
    if not t or t['status']!='active':await c.answer('Турнир недоступен.',show_alert=True);return
    if len(apps(tid))>=t['max_teams']:await c.answer('Мест больше нет.',show_alert=True);return
    if existing(tid,c.from_user.id):await c.answer('У тебя уже есть заявка на этот турнир.',show_alert=True);return
    await state.update_data(tournament_id=tid,format=t['format']);await c.message.edit_text(f'🏆 <b>{t["name"]}</b>\n💰 Проходка: <b>{t["entry_fee"]} WC</b> за {"команду" if t["format"]=="2x2" else "человека"}.\n\n1/4. Ник первого игрока:');await state.set_state(Reg.p1_nick);await c.answer()

@dp.message(Reg.p1_nick)
async def p1nick(m,state):
    if not m.text:await m.answer('Введите ник.');return
    await state.update_data(p1_nick=m.text.strip());await m.answer('2/4. Часовой пояс первого игрока:');await state.set_state(Reg.p1_tz)
@dp.message(Reg.p1_tz)
async def p1tz(m,state):
    if not m.text:await m.answer('Введите часовой пояс.');return
    await state.update_data(p1_tz=m.text.strip());await m.answer('3/4. PUBG Mobile ID первого игрока (только цифры):');await state.set_state(Reg.p1_id)
@dp.message(Reg.p1_id)
async def p1id(m,state):
    v=clean_id(m.text or '')
    if not v:await m.answer('❌ ID должен содержать только цифры.');return
    await state.update_data(p1_id=v);await m.answer('4/4. Telegram username первого игрока, обязательно с @:');await state.set_state(Reg.p1_tg)
@dp.message(Reg.p1_tg)
async def p1tg(m,state):
    v=clean_at(m.text or '')
    if not v:await m.answer('❌ Username должен начинаться с @. Например: @Wesoling');return
    d=await state.get_data()
    if d['format']=='2x2':await state.update_data(p1_tg=v);await m.answer('👥 <b>Данные второго игрока</b>\n\n1/4. Ник второго игрока:');await state.set_state(Reg.p2_nick);return
    await state.update_data(p1_tg=v);await finish_reg(m,state)
@dp.message(Reg.p2_nick)
async def p2nick(m,state):
    if not m.text:await m.answer('Введите ник.');return
    await state.update_data(p2_nick=m.text.strip());await m.answer('2/4. Часовой пояс второго игрока:');await state.set_state(Reg.p2_tz)
@dp.message(Reg.p2_tz)
async def p2tz(m,state):
    if not m.text:await m.answer('Введите часовой пояс.');return
    await state.update_data(p2_tz=m.text.strip());await m.answer('3/4. PUBG Mobile ID второго игрока (только цифры):');await state.set_state(Reg.p2_id)
@dp.message(Reg.p2_id)
async def p2id(m,state):
    v=clean_id(m.text or '')
    if not v:await m.answer('❌ ID должен содержать только цифры.');return
    await state.update_data(p2_id=v);await m.answer('4/4. Telegram username второго игрока, обязательно с @:');await state.set_state(Reg.p2_tg)
@dp.message(Reg.p2_tg)
async def p2tg(m,state):
    v=clean_at(m.text or '')
    if not v:await m.answer('❌ Username должен начинаться с @.');return
    await state.update_data(p2_tg=v);await finish_reg(m,state)

async def finish_reg(m:Message,state:FSMContext):
    d=await state.get_data();t=tournament(d['tournament_id']);uid=m.from_user.id
    if not t or t['status']!='active':await state.clear();await m.answer('Турнир закрыт.');return
    if len(apps(t['id']))>=t['max_teams']:await state.clear();await m.answer('Мест больше нет.');return
    if existing(t['id'],uid):await state.clear();await m.answer('У тебя уже есть заявка.');return
    fee=t['entry_fee']
    if wallet(uid,m.from_user.username)<fee:
        await state.clear();await m.answer(f'❌ Недостаточно WesoCoins. Нужно <b>{fee}</b>, у тебя <b>{wallet(uid)}</b>.\n\nНапишите @{MANAGER_USERNAME} для пополнения. Если у вас бан — @{PAY_USERNAME}');return
    if not spend(uid,fee,f'Проходка: {t["name"]}'):
        await state.clear();await m.answer('Не удалось списать WesoCoins.');return
    aid=execute('''INSERT INTO applications(tournament_id,user_id,username,nickname,timezone,game_id,payment,tg_username,p2_nickname,p2_timezone,p2_game_id,p2_tg_username,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
      t['id'],uid,m.from_user.username,d['p1_nick'],d['p1_tz'],d['p1_id'],'WesoCoins',d['p1_tg'],d.get('p2_nick',''),d.get('p2_tz',''),d.get('p2_id',''),d.get('p2_tg',''),'pending',now()))
    await state.clear();await m.answer(f'✅ <b>Заявка отправлена!</b>\n\n🏆 {t["name"]}\n💰 Списано: {fee} WesoCoins\n\nНапишите @{MANAGER_USERNAME} для оплаты/подтверждения. Если у вас бан — @{PAY_USERNAME}')
    p2=''
    if t['format']=='2x2':p2=f'\n👥 <b>Игрок 2:</b> {d["p2_nick"]}\n🌍 {d["p2_tz"]}\n🆔 <code>{d["p2_id"]}</code>\n📱 {d["p2_tg"]}\n'
    text=f'📨 <b>Новая заявка #{aid}</b>\n\n🏆 {t["name"]} [{t["format"]}]\n💰 Проходка: {fee} WC\n\n👤 <b>Игрок 1:</b> {d["p1_nick"]}\n🌍 {d["p1_tz"]}\n🆔 <code>{d["p1_id"]}</code>\n📱 {d["p1_tg"]}\n{p2}\n🆔 Telegram ID регистратора: <code>{uid}</code>'
    try:await bot.send_message(ADMIN_ID,text,reply_markup=kb([[InlineKeyboardButton(text='✅ Принять',callback_data=f'accept:{aid}'),InlineKeyboardButton(text='❌ Отклонить',callback_data=f'reject:{aid}')]]))
    except Exception:logging.exception('admin notify')

# ---------- Admin ----------
@dp.message(Command('admin'))
async def admin_cmd(m:Message):
    if not admin(m.from_user.id):await m.answer('⛔ Нет доступа.');return
    pending=len(q("SELECT id FROM applications WHERE status='pending'"))
    await m.answer('🔐 <b>Админ-панель</b>',reply_markup=kb([
      [InlineKeyboardButton(text='🏆 Создать турнир',callback_data='acreate')],
      [InlineKeyboardButton(text='📋 Турниры',callback_data='atours')],
      [InlineKeyboardButton(text=f'📨 Заявки ({pending})',callback_data='aapps')],
      [InlineKeyboardButton(text='🗑 Удалить турнир',callback_data='adel')]
    ]))
@dp.callback_query(F.data=='acreate')
async def acreate(c:CallbackQuery,state:State):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    await c.message.answer('🏆 Название турнира:');await state.set_state(Create.name);await c.answer()
@dp.message(Create.name)
async def cname(m,state):
    if not admin(m.from_user.id):return
    if not m.text:await m.answer('Введите название.');return
    await state.update_data(name=m.text.strip());await m.answer('Формат:',reply_markup=kb([[InlineKeyboardButton(text='1x1',callback_data='fmt:1x1'),InlineKeyboardButton(text='2x2',callback_data='fmt:2x2')]]));await state.set_state(Create.fmt)
@dp.callback_query(F.data.startswith('fmt:'))
async def cfmt(c,state):
    if not admin(c.from_user.id):return
    fmt=c.data.split(':')[1];await state.update_data(format=fmt);await c.message.answer('Максимальное количество участников/команд (например 16):');await state.set_state(Create.teams);await c.answer()
@dp.message(Create.teams)
async def cteams(m,state):
    if not admin(m.from_user.id):return
    try:n=int((m.text or '').strip())
    except:await m.answer('Введите число.');return
    if n<2 or n>1000:await m.answer('От 2 до 1000.');return
    await state.update_data(teams=n);await m.answer('Стоимость проходки в WesoCoins:\n1x1 — с человека.\n2x2 — с команды, платит регистратор.\n\nВведите число, например 100:');await state.set_state(Create.fee)
@dp.message(Create.fee)
async def cfee(m,state):
    if not admin(m.from_user.id):return
    try:fee=int((m.text or '').strip())
    except:await m.answer('Введите число.');return
    if fee<0:await m.answer('Стоимость не может быть отрицательной.');return
    d=await state.get_data();tid=execute('INSERT INTO tournaments(name,format,max_teams,entry_fee,status,created_at) VALUES(?,?,?,?,?,?)',(d['name'],d['format'],d['teams'],fee,'active',now()));await state.clear();await m.answer(f'✅ Турнир создан!\n\n🏆 {d["name"]}\n🎮 Формат: {d["format"]}\n👥 Лимит: {d["teams"]}\n💰 Проходка: {fee} WC\n🆔 ID: {tid}')

@dp.callback_query(F.data=='atours')
async def atours(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    ts=tournaments();
    if not ts:await c.message.answer('Турниров нет.');return
    text='🏆 <b>Турниры</b>\n\n'
    for t in ts:text+=f'#{t["id"]} <b>{t["name"]}</b> [{t["format"]}] — {len(apps(t["id"]))}/{t["max_teams"]} — {t["entry_fee"]} WC — {"🟢" if t["status"]=="active" else "🔴"}\n'
    await c.message.answer(text);await c.answer()
@dp.callback_query(F.data=='aapps')
async def aapps(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    aa=q("SELECT * FROM applications WHERE status='pending' ORDER BY id")
    if not aa:await c.message.answer('📭 Заявок нет.');return
    for a in aa:
        t=tournament(a['tournament_id']);p2=f'\n\n👥 <b>Игрок 2:</b> {a["p2_nickname"]}\n🌍 {a["p2_timezone"]}\n🆔 <code>{a["p2_game_id"]}</code>\n📱 {a["p2_tg_username"]}' if t['format']=='2x2' else ''
        text=f'📨 <b>Заявка #{a["id"]}</b>\n🏆 {t["name"]} [{t["format"]}]\n\n👤 <b>Игрок 1:</b> {a["nickname"]}\n🌍 {a["timezone"]}\n🆔 <code>{a["game_id"]}</code>\n📱 {a["tg_username"]}{p2}'
        await c.message.answer(text,reply_markup=kb([[InlineKeyboardButton(text='✅ Принять',callback_data=f'accept:{a["id"]}'),InlineKeyboardButton(text='❌ Отклонить',callback_data=f'reject:{a["id"]}')]]))
    await c.answer()
@dp.callback_query(F.data=='adel')
async def adel(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    ts=tournaments();await c.message.answer('🗑 Выберите турнир:',reply_markup=kb([[InlineKeyboardButton(text=f'🗑 {t["name"]}',callback_data=f'del:{t["id"]}')] for t in ts]));await c.answer()
@dp.callback_query(F.data.startswith('del:'))
async def delete(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    tid=int(c.data.split(':')[1]);t=tournament(tid)
    if not t:return await c.answer('Не найден.',show_alert=True)
    await c.message.edit_text(f'Удалить <b>{t["name"]}</b>?',reply_markup=kb([[InlineKeyboardButton(text='✅ Да',callback_data=f'dely:{tid}'),InlineKeyboardButton(text='❌ Нет',callback_data='deln')]]));await c.answer()
@dp.callback_query(F.data.startswith('dely:'))
async def dely(c):
    if not admin(c.from_user.id):return
    tid=int(c.data.split(':')[1]);execute('DELETE FROM applications WHERE tournament_id=?',(tid,));execute('DELETE FROM tournaments WHERE id=?',(tid,));await c.message.edit_text('✅ Турнир удалён.');await c.answer()
@dp.callback_query(F.data=='deln')
async def deln(c):await c.message.edit_text('❌ Отменено.');await c.answer()

# ---------- Accept/reject ----------
@dp.callback_query(F.data.startswith('accept:'))
async def accept(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    aid=int(c.data.split(':')[1]);a=q('SELECT * FROM applications WHERE id=?',(aid,),True)
    if not a or a['status']!='pending':return await c.answer('Заявка уже обработана.',show_alert=True)
    t=tournament(a['tournament_id'])
    if not t or t['status']!='active':return await c.answer('Турнир закрыт.',show_alert=True)
    if len(apps(t['id']))>=t['max_teams']:return await c.answer('Мест нет.',show_alert=True)
    execute("UPDATE applications SET status='accepted' WHERE id=?",(aid,))
    try:await bot.send_message(a['user_id'],f'✅ <b>Заявка принята!</b>\n\n🏆 {t["name"]}\n\nНапишите @{MANAGER_USERNAME} для оплаты. Если у вас бан — @{PAY_USERNAME}')
    except:pass
    await c.message.edit_reply_markup(reply_markup=None);await c.answer('Принято')
@dp.callback_query(F.data.startswith('reject:'))
async def reject(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    aid=int(c.data.split(':')[1]);a=q('SELECT * FROM applications WHERE id=?',(aid,),True)
    if not a or a['status']!='pending':return await c.answer('Заявка уже обработана.',show_alert=True)
    # Возвращаем проходку, так как она списалась при регистрации.
    t=tournament(a['tournament_id']);fee=t['entry_fee'] if t else 0
    execute("UPDATE applications SET status='rejected' WHERE id=?",(aid,));change_coins(a['user_id'],fee,'Возврат за отклонённую заявку')
    try:await bot.send_message(a['user_id'],f'❌ <b>Заявка отклонена.</b>\n\n💰 Возвращено: {fee} WesoCoins.\n\nЕсли это ошибка — @{MANAGER_USERNAME}')
    except:pass
    await c.message.edit_reply_markup(reply_markup=None);await c.answer('Отклонено, WC возвращены')

# ---------- List / bracket ----------
@dp.message(Command('list'))
async def list_(m:Message):
    if not admin(m.from_user.id):return await m.answer('⛔ Только администратору.')
    ts=tournaments(True)
    await m.answer('📋 Выберите турнир:',reply_markup=kb([[tbutton(t,'list') ] for t in ts]))
@dp.callback_query(F.data.startswith('list:'))
async def list_cb(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    t=tournament(int(c.data.split(':')[1]));aa=apps(t['id'])
    if not aa:return await c.message.answer('📭 Участников нет.')
    text=f'🏆 <b>{t["name"]}</b> [{t["format"]}]\n👥 {len(aa)}/{t["max_teams"]}\n\n'
    for i,a in enumerate(aa,1):
        text+=f'<b>{i}.</b> {a["nickname"]} 🆔 <code>{a["game_id"]}</code> 📱 {a["tg_username"]}'
        if t['format']=='2x2':text+=f'\n   👥 {a["p2_nickname"]} 🆔 <code>{a["p2_game_id"]}</code> 📱 {a["p2_tg_username"]}'
        text+='\n\n'
    await c.message.answer(text);await c.answer()
@dp.message(Command('setka'))
async def setka(m:Message):
    if not admin(m.from_user.id):return await m.answer('⛔ Только администратору.')
    ts=tournaments(True);await m.answer('🎲 Выберите турнир:',reply_markup=kb([[tbutton(t,'bracket') ] for t in ts]))
@dp.callback_query(F.data.startswith('bracket:'))
async def bracket(c):
    if not admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    t=tournament(int(c.data.split(':')[1]));aa=list(apps(t['id']))
    if len(aa)<t['max_teams']:return await c.message.answer(f'⛔ Сетка будет доступна после полного набора: {len(aa)}/{t["max_teams"]}.')
    if len(aa)%2:return await c.message.answer('⛔ Для текущей простой сетки нужно чётное количество команд/игроков.')
    random.shuffle(aa);text=f'🎲 <b>Сетка {t["name"]}</b> [{t["format"]}]\n\n'
    for n in range(0,len(aa),2):
        a,b=aa[n],aa[n+1]
        A=f'{a["nickname"]}' + (f' + {a["p2_nickname"]}' if t['format']=='2x2' else '')
        B=f'{b["nickname"]}' + (f' + {b["p2_nickname"]}' if t['format']=='2x2' else '')
        text+=f'<b>Матч {n//2+1}:</b>\n{A} 🆚 {B}\n\n'
    await c.message.answer(text);await c.answer('Сетка создана')

# ---------- Give coins ----------
@dp.message(Command('give'))
async def give(m:Message):
    if not admin(m.from_user.id):return await m.answer('⛔ Только администратору.')
    p=(m.text or '').split()
    if len(p)!=3:return await m.answer('Использование: <code>/give @username количество</code>\nПример: <code>/give @Wesoling 500</code>')
    username=clean_at(p[1]);
    if not username:return await m.answer('❌ Username должен начинаться с @.')
    try:amount=int(p[2])
    except:return await m.answer('❌ Количество должно быть числом.')
    if amount<=0:return await m.answer('❌ Количество должно быть больше 0.')
    r=q('SELECT user_id FROM wallets WHERE username=?',(username[1:],),True)
    if not r:return await m.answer('❌ Этот пользователь ещё не запускал бота, я не могу найти его Telegram ID.')
    bal=change_coins(r['user_id'],amount,f'Выдано администратором {m.from_user.id}',username[1:]);await m.answer(f'✅ Выдано <b>{amount} WesoCoins</b> пользователю {username}.\n💰 Баланс: {bal} WC')

async def main():
    logging.basicConfig(level=logging.INFO);init_db();await setup();print('Wesoling Tournament Bot started');await dp.start_polling(bot)
if __name__=='__main__':asyncio.run(main())
