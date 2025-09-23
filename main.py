import logging
import asyncio
import random
import re
import os
import time
import sys
import datetime
from datetime import datetime, timedelta
from telethon import TelegramClient, functions, types, errors, events, Button
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError

# إعدادات API
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8137587721:AAEJiD56RnTiofE0NYRm7WUm9lHnmzAxYQE'

# ألوان للتنسيق
GREEN = '\033[1;32m'
RED = '\033[1;31m'
YELLOW = '\033[1;33m'
CYAN = '\033[1;36m'
RESET = '\033[0m'

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('advanced_transfer_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# حالة المستخدمين
user_sessions = {}

class UserSession:
    def __init__(self, user_id):
        self.user_id = user_id
        self.phone_verified = False
        self.login_attempts = 0
        self.verification_attempts = 0
        self.current_operation = None
        self.phone_number = None
        self.verification_code = None
        self.code_expiry = None
        self.setup_complete = False
        self.transfer_settings = {
            'adds_per_minute': 10,
            'source_group': '',
            'target_channel': '',
            'required_count': 100,
            'current_count': 0,
            'transferred_users': [],
            'transfer_mode': 'turbo'
        }
        self.statistics_message_id = None
        self.is_transfer_active = False
        self.user_client = None
        self.transfer_task = None
        self.waiting_for_input = False
        self.last_message_id = None
        self.is_authenticated = False
        self.last_stats_content = ""
        
        # إحصائيات النقل
        self.transfer_stats = {
            'added_count': 0,
            'skipped_count': 0,
            'privacy_block': 0,
            'already_member': 0,
            'errors_count': 0,
            'start_time': None,
            'total_members': 0
        }

# إنشاء زراعة لوحة المفاتيح
def create_main_keyboard():
    return [
        [Button.inline("🚀 بدء النقل السريع", b"start_transfer")],
        [Button.inline("⚙️ إعداد القناة", b"setup_config")],
        [Button.inline("📊 الإحصائيات", b"show_stats")],
        [Button.inline("⏹️ إيقاف النقل", b"stop_transfer")]
    ]

def create_setup_keyboard():
    return [
        [Button.inline("🔐 تسجيل الدخول", b"user_login")],
        [Button.inline("📁 المصدر (مجموعة)", b"set_source")],
        [Button.inline("📢 الهدف (قناة)", b"set_target")],
        [Button.inline("📊 العدد المطلوب", b"set_count")],
        [Button.inline("⚡ سرعة النقل", b"set_speed")],
        [Button.inline("🔄 اختبار الاتصال", b"test_connection")],
        [Button.inline("← رجوع", b"back_main")]
    ]

def create_speed_keyboard():
    return [
        [Button.inline("🐢 آمن (5/دقيقة)", b"speed_5")],
        [Button.inline("⚡ سريع (10/دقيقة)", b"speed_10")],
        [Button.inline("🚀 توربو (20/دقيقة)", b"speed_20")],
        [Button.inline("💣 أقصى سرعة (50/دقيقة)", b"speed_50")],
        [Button.inline("← رجوع", b"back_main")]
    ]

def create_login_keyboard():
    return [
        [Button.inline("🔄 إعادة الإرسال", b"resend_code")],
        [Button.inline("❌ إلغاء", b"cancel_login")]
    ]

def create_transfer_keyboard():
    return [
        [Button.inline("⏸️ إيقاف مؤقت", b"pause_transfer")],
        [Button.inline("⏹️ إيقاف نهائي", b"stop_transfer")],
        [Button.inline("📊 تحديث الإحصائيات", b"refresh_stats")]
    ]

# الحصول على جلسة المستخدم
def get_user_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = UserSession(user_id)
    return user_sessions[user_id]

# إنشاء عميل Telethon للمستخدم
async def create_user_client(phone_number, user_id):
    try:
        session_file = f"sessions/user_{user_id}_{phone_number.replace('+', '')}"
        client = TelegramClient(session_file, API_ID, API_HASH)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            code_request = await client.send_code_request(phone_number)
            return client, code_request
        else:
            return client, None
    except Exception as e:
        logger.error(f"خطأ في إنشاء العميل: {str(e)}")
        return None, None

# التحقق من رقم الهاتف وإرسال الكود
async def send_verification_code(client, phone_number):
    try:
        await client.send_code_request(phone_number)
        return True
    except Exception as e:
        logger.error(f"خطأ في إرسال الكود: {str(e)}")
        return False

# تسجيل الدخول بالكود
async def login_with_code(client, phone_number, code):
    try:
        await client.sign_in(phone_number, code)
        return True
    except SessionPasswordNeededError:
        return "2fa_required"
    except PhoneCodeInvalidError:
        return "invalid_code"
    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول: {str(e)}")
        return False

# تسجيل الدخول بكلمة المرور
async def login_with_password(client, password):
    try:
        await client.sign_in(password=password)
        return True
    except Exception as e:
        logger.error(f"خطأ في تسجيل الدخول بكلمة المرور: {str(e)}")
        return False

# الحصول على أعضاء المجموعة بنفس طريقة الكود الأصلي
async def get_group_members(client, group_identifier):
    try:
        source = await client.get_entity(group_identifier)
        members = client.get_participants(source, aggressive=True)
        return await members
    except Exception as e:
        logger.error(f"خطأ في جلب الأعضاء: {str(e)}")
        return []

# نقل عضو باستخدام الطريقة الأصلية
async def invite_member(client, member, target):
    try:
        await client(functions.channels.InviteToChannelRequest(
            channel=target,
            users=[types.InputUser(
                user_id=member.id,
                access_hash=member.access_hash
            )]
        ))
        return True
    except errors.FloodWaitError as e:
        logger.warning(f"Flood wait: {e.seconds} seconds")
        await asyncio.sleep(e.seconds + 5)
        return await invite_member(client, member, target)
    except errors.UserPrivacyRestrictedError:
        logger.info(f"User privacy restricted: {member.id}")
        return "privacy_restricted"
    except errors.UserAlreadyParticipantError:
        logger.info(f"User already participant: {member.id}")
        return "already_member"
    except Exception as e:
        logger.error(f"Error inviting member {member.id}: {str(e)}")
        return False

# إنشاء رسالة الإحصائيات
async def create_statistics_message(session):
    progress = session.transfer_settings['current_count']
    total = session.transfer_settings['required_count']
    percentage = (progress / total) * 100 if total > 0 else 0
    remaining = total - progress
    speed = session.transfer_settings['adds_per_minute']
    
    speed_names = {
        5: "🐢 آمن (5/دقيقة)",
        10: "⚡ سريع (10/دقيقة)", 
        20: "🚀 توربو (20/دقيقة)",
        50: "💣 أقصى سرعة (50/دقيقة)"
    }
    speed_display = speed_names.get(speed, f"⚡ {speed}/دقيقة")
    
    estimated_time = remaining / speed if speed > 0 else 0
    
    # إحصائيات النقل
    stats = session.transfer_stats
    elapsed = time.time() - stats['start_time'] if stats['start_time'] else 0
    current_speed = (stats['added_count'] / (elapsed / 60)) if elapsed > 60 else 0
    
    stats_text = f"""📊 **إحصائيات نقل القناة الحية**

🎯 **الهدف:** نقل الأعضاء إلى قناة
🔄 **الحالة:** {'🟢 جاري النقل' if session.is_transfer_active else '🔴 متوقف'}
📈 **التقدم:** {progress} / {total}
📊 **النسبة:** {percentage:.1f}%
⚡ **السرعة:** {speed_display}
📈 **السرعة الفعلية:** {current_speed:.1f} عضو/دقيقة

📊 **الإحصائيات التفصيلية:**
✅ تمت الإضافة: {stats['added_count']}
🔄 موجودين مسبقاً: {stats['already_member']}
🚫 خصوصية: {stats['privacy_block']}
❌ أخطاء: {stats['errors_count']}

📁 **المصدر:** {session.transfer_settings['source_group']}
📢 **الهدف:** {session.transfer_settings['target_channel']}

⏰ **المدة:** {str(datetime.timedelta(seconds=int(elapsed)))}
⏰ **آخر تحديث:** {datetime.now().strftime('%H:%M:%S')}"""
    
    return stats_text

# عملية النقل الرئيسية بنفس طريقة الكود الأصلي
async def advanced_transfer_process(session):
    """عملية النقل باستخدام الطريقة الأصلية المتقدمة"""
    try:
        if not session.user_client:
            logger.error("❌ عميل المستخدم غير متوفر")
            return
        
        # جلب الكيانات
        source = await session.user_client.get_entity(session.transfer_settings['source_group'])
        target = await session.user_client.get_entity(session.transfer_settings['target_channel'])
        
        # جلب الأعضاء
        logger.info("🔄 يتم جلب قائمة الأعضاء ...")
        members = await get_group_members(session.user_client, source)
        
        if not members:
            logger.error("❌ لم يتم العثور على أعضاء في المجموعة!")
            return
        
        session.transfer_stats['total_members'] = len(members)
        session.transfer_stats['start_time'] = time.time()
        
        logger.info(f"✅ تم جلب {len(members)} عضو من المجموعة.")
        
        # بدء عملية النقل
        for member in members:
            if not session.is_transfer_active:
                break
                
            if session.transfer_settings['current_count'] >= session.transfer_settings['required_count']:
                break
            
            # نقل العضو
            result = await invite_member(session.user_client, member, target)
            
            if result is True:
                session.transfer_settings['current_count'] += 1
                session.transfer_stats['added_count'] += 1
                session.transfer_settings['transferred_users'].append(member.id)
                logger.info(f"✅ تمت دعوة {member.first_name or 'عضو'}")
                
            elif result == "already_member":
                session.transfer_stats['already_member'] += 1
                logger.info(f"ℹ️ {member.first_name or 'عضو'} موجود بالفعل")
                
            elif result == "privacy_restricted":
                session.transfer_stats['privacy_block'] += 1
                logger.info(f"🚫 {member.first_name or 'عضو'} لا يسمح بدعوته")
                
            else:
                session.transfer_stats['errors_count'] += 1
                session.transfer_stats['skipped_count'] += 1
                logger.error(f"❌ خطأ مع {member.first_name or 'عضو'}")
            
            # تأخير بين العمليات حسب السرعة المحددة
            delay = max(2, 60 / session.transfer_settings['adds_per_minute'])
            await asyncio.sleep(delay)
            
    except Exception as e:
        logger.error(f"❌ خطأ في عملية النقل: {str(e)}")
        session.is_transfer_active = False

# البوت الرئيسي
class AdvancedTransferBot:
    def __init__(self):
        self.client = None
        
    async def start_bot(self):
        """بدء البوت الرئيسي للتحكم"""
        self.client = TelegramClient('advanced_transfer_bot', API_ID, API_HASH)
        
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            session = get_user_session(user_id)
            
            welcome_text = """🚀 **نظام النقل المتقدم للقنوات**

🎯 **مخصص لنقل الأعضاء من المجموعات إلى القنوات**

✅ **المميزات:**
- استخدام الطريقة الأصلية المتقدمة للنقل
- نقل سريع للقنوات بسرعات عالية
- إحصائيات حية مفصلة
- تحكم كامل في السرعة
- نظام إدارة متكامل

⚡ **السرعات المتاحة:**
- 🐢 آمن: 5 أعضاء/دقيقة
- ⚡ سريع: 10 أعضاء/دقيقة  
- 🚀 توربو: 20 أعضاء/دقيقة
- 💣 أقصى سرعة: 50 عضو/دقيقة

اختر أحد الخيارات للبدء:"""
            
            await event.reply(welcome_text, buttons=create_main_keyboard())
        
        @self.client.on(events.CallbackQuery)
        async def button_handler(event):
            user_id = event.sender_id
            session = get_user_session(user_id)
            data = event.data.decode('utf-8')
            
            try:
                if data == 'start_transfer':
                    await self.start_transfer(event, session)
                elif data == 'stop_transfer':
                    await self.stop_transfer(event, session)
                elif data == 'setup_config':
                    await self.show_setup(event, session)
                elif data == 'show_stats':
                    await self.show_stats(event, session)
                elif data == 'user_login':
                    await self.start_login(event, session)
                elif data == 'set_source':
                    await self.set_source_group(event, session)
                elif data == 'set_target':
                    await self.set_target_channel(event, session)
                elif data == 'set_count':
                    await self.set_required_count(event, session)
                elif data == 'set_speed':
                    await self.show_speed_options(event, session)
                elif data.startswith('speed_'):
                    await self.set_speed(event, session, data)
                elif data == 'test_connection':
                    await self.test_connection(event, session)
                elif data == 'back_main':
                    await self.back_to_main(event, session)
                elif data == 'resend_code':
                    await self.resend_code(event, session)
                elif data == 'cancel_login':
                    await self.cancel_login(event, session)
                elif data == 'pause_transfer':
                    await self.pause_transfer(event, session)
                elif data == 'refresh_stats':
                    await self.refresh_stats(event, session)
                    
                await event.answer()
            except Exception as e:
                logger.error(f"❌ خطأ في معالجة الزر: {str(e)}")
                await event.answer("❌ حدث خطأ أثناء المعالجة")
        
        @self.client.on(events.NewMessage)
        async def message_handler(event):
            if event.message.message.startswith('/'):
                return
                
            user_id = event.sender_id
            session = get_user_session(user_id)
            
            if not session.waiting_for_input:
                return
                
            text = event.message.message.strip()
            await self.handle_user_input(event, session, text)
        
        # بدء البوت باستخدام التوكن
        await self.client.start(bot_token=BOT_TOKEN)
        print(CYAN + """
═══════════════════════════════════════
🚀 نظام نقل أعضاء تيليجرام المتقدم 🚀
═══════════════════════════════════════
""" + RESET)
        logger.info("🚀 بوت النقل المتقدم يعمل بنجاح!")
        await self.client.run_until_disconnected()
    
    async def handle_user_input(self, event, session, text):
        """معالجة المدخلات النصية من المستخدم"""
        session.waiting_for_input = False
        
        try:
            if session.current_operation == 'login_phone':
                await self.process_phone_input(event, session, text)
            elif session.current_operation == 'login_code':
                await self.process_code_input(event, session, text)
            elif session.current_operation == 'login_password':
                await self.process_password_input(event, session, text)
            elif session.current_operation == 'set_source':
                await self.process_source_input(event, session, text)
            elif session.current_operation == 'set_target':
                await self.process_target_input(event, session, text)
            elif session.current_operation == 'set_count':
                await self.process_count_input(event, session, text)
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة المدخلات: {str(e)}")
            await event.reply("❌ حدث خطأ أثناء معالجة البيانات")
    
    async def show_speed_options(self, event, session):
        """عرض خيارات السرعة"""
        await event.edit(
            "⚡ **اختر سرعة نقل القناة**\n\n"
            "🐢 **آمن (5/دقيقة):** مناسب للمجموعات الصغيرة\n"
            "⚡ **سريع (10/دقيقة):** سرعة متوازنة\n"
            "🚀 **توربو (20/دقيقة):** سريع مع نقل فعال\n"
            "💣 **أقصى سرعة (50/دقيقة):** للقنوات الكبيرة\n\n"
            "🎯 **ملاحظة:** يستخدم الطريقة الأصلية المتقدمة",
            buttons=create_speed_keyboard()
        )
    
    async def set_speed(self, event, session, speed_data):
        """تعيين السرعة المختارة"""
        speed_value = int(speed_data.replace('speed_', ''))
        session.transfer_settings['adds_per_minute'] = speed_value
        
        speed_names = {
            5: "آمن (5 أعضاء/دقيقة)",
            10: "سريع (10 أعضاء/دقيقة)",
            20: "توربو (20 عضو/دقيقة)", 
            50: "أقصى سرعة (50 عضو/دقيقة)"
        }
        
        await event.edit(
            f"✅ **تم تعيين السرعة:** {speed_names[speed_value]}",
            buttons=create_setup_keyboard()
        )
    
    async def start_login(self, event, session):
        """بدء عملية تسجيل الدخول"""
        if session.is_authenticated and session.user_client:
            await event.edit("✅ **أنت مسجل بالفعل!**", buttons=create_setup_keyboard())
            return
        
        session.current_operation = 'login_phone'
        session.waiting_for_input = True
        
        await event.edit(
            "🔐 **تسجيل الدخول بحسابك الشخصي**\n\n"
            "أدخل رقم هاتفك بالصيغة الدولية:\n**مثال:** +966500000000",
            buttons=[[Button.inline("❌ إلغاء", b"cancel_login")]]
        )
    
    async def process_phone_input(self, event, session, phone_number):
        """معالجة إدخال رقم الهاتف"""
        if not re.match(r'^\+\d{10,15}$', phone_number):
            await event.reply("❌ رقم الهاتف غير صالح! يرجى استخدام الصيغة الدولية")
            session.waiting_for_input = True
            return
        
        session.phone_number = phone_number
        
        try:
            session.user_client, code_request = await create_user_client(phone_number, session.user_id)
            
            if not session.user_client:
                await event.reply("❌ فشل في إنشاء الجلسة، يرجى المحاولة مرة أخرى")
                return
            
            session.current_operation = 'login_code'
            session.waiting_for_input = True
            
            await event.reply(
                "📱 **تم إرسال رمز التحقق إلى هاتفك**\n\nأدخل الرمز الذي استلمته:",
                buttons=create_login_keyboard()
            )
            
        except PhoneNumberInvalidError:
            await event.reply("❌ رقم الهاتف غير صالح، يرجى التحقق والمحاولة مرة أخرى")
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة رقم الهاتف: {str(e)}")
            await event.reply("❌ حدث خطأ غير متوقع، يرجى المحاولة مرة أخرى")
    
    async def process_code_input(self, event, session, code):
        """معالجة إدخال كود التحقق"""
        try:
            result = await login_with_code(session.user_client, session.phone_number, code)
            
            if result == True:
                session.is_authenticated = True
                session.phone_verified = True
                session.current_operation = None
                
                me = await session.user_client.get_me()
                await event.reply(
                    f"✅ **تم التسجيل بنجاح!**\n\n👤 **مرحباً:** {me.first_name}\n📞 **الهاتف:** {session.phone_number}",
                    buttons=create_setup_keyboard()
                )
                
            elif result == "2fa_required":
                session.current_operation = 'login_password'
                session.waiting_for_input = True
                await event.reply("🔐 **يتطلب التحقق بخطوتين**\n\nأدخل كلمة المرور:")
                
            elif result == "invalid_code":
                await event.reply("❌ رمز التحقق غير صحيح، يرجى المحاولة مرة أخرى")
                session.waiting_for_input = True
            else:
                await event.reply("❌ فشل التسجيل، يرجى المحاولة مرة أخرى")
                session.waiting_for_input = True
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة الكود: {str(e)}")
            await event.reply("❌ حدث خطأ أثناء التحقق، يرجى المحاولة مرة أخرى")
            session.waiting_for_input = True
    
    async def process_password_input(self, event, session, password):
        """معالجة إدخال كلمة المرور"""
        try:
            success = await login_with_password(session.user_client, password)
            
            if success:
                session.is_authenticated = True
                session.phone_verified = True
                session.current_operation = None
                
                me = await session.user_client.get_me()
                await event.reply(
                    f"✅ **تم التسجيل بنجاح!**\n\n👤 **مرحباً:** {me.first_name}",
                    buttons=create_setup_keyboard()
                )
            else:
                await event.reply("❌ كلمة المرور غير صحيحة، يرجى المحاولة مرة أخرى")
                session.waiting_for_input = True
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة كلمة المرور: {str(e)}")
            await event.reply("❌ حدث خطأ أثناء التحقق، يرجى المحاولة مرة أخرى")
            session.waiting_for_input = True
    
    async def set_source_group(self, event, session):
        """إعداد المجموعة المصدر"""
        if not session.is_authenticated:
            await event.edit("❌ يرجى تسجيل الدخول أولاً!", buttons=create_setup_keyboard())
            return
        
        session.current_operation = 'set_source'
        session.waiting_for_input = True
        
        await event.edit(
            "📁 **إعداد المجموعة المصدر**\n\n"
            "أدخل رابط المجموعة التي تريد نسخ الأعضاء منها:",
            buttons=[[Button.inline("❌ إلغاء", b"back_main")]]
        )
    
    async def process_source_input(self, event, session, source):
        """معالجة إدخال المصدر"""
        try:
            entity = await session.user_client.get_entity(source)
            session.transfer_settings['source_group'] = source
            
            await event.reply(f"✅ **تم تعيين المصدر:** {source}", buttons=create_setup_keyboard())
            session.current_operation = None
            
        except Exception as e:
            await event.reply("❌ لم أتمكن من الوصول إلى المجموعة، تأكد من الصلاحيات")
            session.waiting_for_input = True
    
    async def set_target_channel(self, event, session):
        """إعداد القناة الهدف"""
        if not session.is_authenticated:
            await event.edit("❌ يرجى تسجيل الدخول أولاً!", buttons=create_setup_keyboard())
            return
        
        session.current_operation = 'set_target'
        session.waiting_for_input = True
        
        await event.edit(
            "📢 **إعداد القناة الهدف**\n\n"
            "أدخل رابط القناة التي تريد الإضافة إليها:",
            buttons=[[Button.inline("❌ إلغاء", b"back_main")]]
        )
    
    async def process_target_input(self, event, session, target):
        """معالجة إدخال الهدف"""
        try:
            entity = await session.user_client.get_entity(target)
            session.transfer_settings['target_channel'] = target
            
            await event.reply(f"✅ **تم تعيين الهدف (قناة):** {target}", buttons=create_setup_keyboard())
            session.current_operation = None
            
        except Exception as e:
            await event.reply("❌ لم أتمكن من الوصول إلى القناة، تأكد من الصلاحيات")
            session.waiting_for_input = True
    
    async def set_required_count(self, event, session):
        """إعداد العدد المطلوب"""
        session.current_operation = 'set_count'
        session.waiting_for_input = True
        
        await event.edit(
            "🎯 **العدد الإجمالي المطلوب**\n\nأدخل عدد الأعضاء المطلوب نقلهم:",
            buttons=[[Button.inline("❌ إلغاء", b"back_main")]]
        )
    
    async def process_count_input(self, event, session, count_text):
        """معالجة إدخال العدد"""
        try:
            count = int(count_text)
            if count < 1 or count > 10000:
                await event.reply("❌ الرقم يجب أن يكون بين 1 و 10000")
                session.waiting_for_input = True
                return
            
            session.transfer_settings['required_count'] = count
            await event.reply(f"✅ **تم تعيين العدد المطلوب:** {count}", buttons=create_setup_keyboard())
            session.current_operation = None
            
        except ValueError:
            await event.reply("❌ يرجى إدخال رقم صحيح")
            session.waiting_for_input = True
    
    async def start_transfer(self, event, session):
        """بدء عملية النقل"""
        if not session.is_authenticated:
            await event.edit("❌ يرجى تسجيل الدخول أولاً!", buttons=create_main_keyboard())
            return
        
        if not all([session.transfer_settings['source_group'], 
                   session.transfer_settings['target_channel'],
                   session.transfer_settings['required_count'] > 0]):
            await event.edit("❌ يرجى إكمال الإعدادات أولاً!", buttons=create_main_keyboard())
            return
        
        if session.is_transfer_active:
            await event.edit("⚠️ **العملية جارية بالفعل!**", buttons=create_main_keyboard())
            return
        
        # إعادة تعيين الإحصائيات
        session.transfer_stats = {
            'added_count': 0,
            'skipped_count': 0,
            'privacy_block': 0,
            'already_member': 0,
            'errors_count': 0,
            'start_time': time.time(),
            'total_members': 0
        }
        
        session.is_transfer_active = True
        
        # بدء عملية النقل المتقدمة
        session.transfer_task = asyncio.create_task(advanced_transfer_process(session))
        
        # إرسال رسالة الإحصائيات
        stats_text = await create_statistics_message(session)
        message = await event.edit(stats_text, buttons=create_transfer_keyboard())
        session.statistics_message_id = message.id
        session.last_stats_content = stats_text
        
        # بدء تحديث الإحصائيات
        asyncio.create_task(self.update_statistics_loop(session, event))
        
        logger.info(f"🚀 بدء نقل القناة للمستخدم {session.user_id}")
    
    async def update_statistics_loop(self, session, event):
        """حلقة تحديث الإحصائيات"""
        while session.is_transfer_active:
            try:
                stats_text = await create_statistics_message(session)
                
                if stats_text != session.last_stats_content:
                    await event.edit(stats_text, buttons=create_transfer_keyboard())
                    session.last_stats_content = stats_text
                
                await asyncio.sleep(5)
            except Exception as e:
                if "Content of the message was not modified" in str(e):
                    pass
                else:
                    logger.error(f"❌ خطأ في تحديث الإحصائيات: {str(e)}")
                await asyncio.sleep(5)
    
    async def refresh_stats(self, event, session):
        """تحديث الإحصائيات يدوياً"""
        try:
            stats_text = await create_statistics_message(session)
            await event.edit(stats_text, buttons=create_transfer_keyboard())
            await event.answer("✅ تم تحديث الإحصائيات")
        except Exception as e:
            await event.answer("❌ خطأ في التحديث")
    
    async def stop_transfer(self, event, session):
        """إيقاف عملية النقل"""
        session.is_transfer_active = False
        if session.transfer_task:
            session.transfer_task.cancel()
        
        # عرض التقرير النهائي
        stats = session.transfer_stats
        elapsed = time.time() - stats['start_time'] if stats['start_time'] else 0
        
        report_text = f"""📊 **تقرير النقل النهائي**

✅ **تمت الإضافة:** {stats['added_count']}
🔄 **موجودين مسبقاً:** {stats['already_member']}
🚫 **خصوصية:** {stats['privacy_block']}
❌ **أخطاء:** {stats['errors_count']}
⏳ **المدة الكلية:** {str(datetime.timedelta(seconds=int(elapsed)))}

🎯 **العملية تمت بنجاح**"""
        
        await event.edit(report_text, buttons=create_main_keyboard())
        logger.info(f"⏹️ إيقاف نقل القناة للمستخدم {session.user_id}")
    
    async def pause_transfer(self, event, session):
        """إيقاف مؤقت للعملية"""
        session.is_transfer_active = False
        await event.answer("⏸️ تم الإيقاف المؤقت")
    
    async def show_setup(self, event, session):
        """عرض شاشة الإعدادات"""
        status = "✅ مفعل" if session.is_authenticated else "❌ غير مفعل"
        
        speed = session.transfer_settings['adds_per_minute']
        speed_names = {
            5: "🐢 آمن (5/دقيقة)",
            10: "⚡ سريع (10/دقيقة)",
            20: "🚀 توربو (20/دقيقة)",
            50: "💣 أقصى سرعة (50/دقيقة)"
        }
        speed_display = speed_names.get(speed, f"⚡ {speed}/دقيقة")
        
        setup_text = f"""⚙️ **إعدادات نقل القناة**

🔐 **الحساب:** {status}
📁 **المصدر:** {session.transfer_settings['source_group'] or 'غير محدد'}
📢 **الهدف:** {session.transfer_settings['target_channel'] or 'غير محدد'}
📊 **العدد المطلوب:** {session.transfer_settings['required_count']}
⚡ **السرعة:** {speed_display}

اختر الإعداد الذي تريد تعديله:"""
        
        await event.edit(setup_text, buttons=create_setup_keyboard())
    
    async def show_stats(self, event, session):
        """عرض الإحصائيات"""
        stats_text = await create_statistics_message(session)
        await event.edit(stats_text, buttons=create_main_keyboard())
    
    async def test_connection(self, event, session):
        """اختبار الاتصال"""
        if not session.is_authenticated:
            await event.edit("❌ يرجى تسجيل الدخول أولاً!", buttons=create_setup_keyboard())
            return
        
        try:
            me = await session.user_client.get_me()
            
            source_ok = False
            target_ok = False
            
            if session.transfer_settings['source_group']:
                try:
                    source_entity = await session.user_client.get_entity(session.transfer_settings['source_group'])
                    source_ok = True
                except:
                    source_ok = False
            
            if session.transfer_settings['target_channel']:
                try:
                    target_entity = await session.user_client.get_entity(session.transfer_settings['target_channel'])
                    target_ok = True
                except:
                    target_ok = False
            
            status_text = f"✅ **الاتصال نشط**\n\n👤 **الحساب:** {me.first_name}\n"
            status_text += f"📞 **الهاتف:** {session.phone_number}\n"
            status_text += f"📁 **المصدر:** {'✅ متصل' if source_ok else '❌ غير متصل'}\n"
            status_text += f"📢 **الهدف:** {'✅ متصل' if target_ok else '❌ غير متصل'}"
            
            await event.edit(status_text, buttons=create_setup_keyboard())
        except Exception as e:
            await event.edit(f"❌ **فشل الاتصال:** {str(e)}", buttons=create_setup_keyboard())
    
    async def back_to_main(self, event, session):
        """العودة للقائمة الرئيسية"""
        await event.edit("📊 **لوحة التحكم الرئيسية**", buttons=create_main_keyboard())
    
    async def resend_code(self, event, session):
        """إعادة إرسال الكود"""
        if not session.phone_number:
            await event.answer("❌ لم يتم تحديد رقم الهاتف")
            return
        
        try:
            await send_verification_code(session.user_client, session.phone_number)
            await event.answer("✅ تم إعادة إرسال الكود")
        except Exception as e:
            await event.answer("❌ فشل إعادة الإرسال")
    
    async def cancel_login(self, event, session):
        """إلغاء تسجيل الدخول"""
        session.current_operation = None
        session.waiting_for_input = False
        if session.user_client:
            await session.user_client.disconnect()
            session.user_client = None
        await event.edit("❌ **تم إلغاء التسجيل**", buttons=create_main_keyboard())

# تشغيل البوت
async def main():
    os.makedirs('sessions', exist_ok=True)
    
    bot = AdvancedTransferBot()
    await bot.start_bot()

if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت النقل المتقدم...")
    print(f"🤖 التوكن: {BOT_TOKEN}")
    print(f"🔑 API ID: {API_ID}")
    print("📢 البوت يستخدم الطريقة الأصلية المتقدمة للنقل")
    asyncio.run(main())
