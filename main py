import logging
import asyncio
import random
import re
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError

# إعدادات API
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8137587721:AAEJiD56RnTiofE0NYRm7WUm9lHnmzAxYQE'

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transfer_bot.log'),
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
            'adds_per_minute': 5,
            'source_group': '',
            'target_group': '',
            'required_count': 100,
            'current_count': 0,
            'transferred_users': []
        }
        self.statistics_message_id = None
        self.is_transfer_active = False
        self.user_client = None
        self.transfer_task = None
        self.waiting_for_input = False
        self.last_message_id = None
        self.is_authenticated = False

# إنشاء زراعة لوحة المفاتيح
def create_main_keyboard():
    return [
        [Button.inline("▶️ بدء النقل", b"start_transfer")],
        [Button.inline("⚙️ إعداد العملية", b"setup_config")],
        [Button.inline("📊 الإحصائيات", b"show_stats")],
        [Button.inline("⏹️ إيقاف النقل", b"stop_transfer")]
    ]

def create_setup_keyboard():
    return [
        [Button.inline("🔐 تسجيل الدخول", b"user_login")],
        [Button.inline("📁 المصدر", b"set_source")],
        [Button.inline("🎯 الهدف", b"set_target")],
        [Button.inline("📊 العدد المطلوب", b"set_count")],
        [Button.inline("⚡ السرعة", b"set_speed")],
        [Button.inline("🔄 اختبار الاتصال", b"test_connection")],
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
        [Button.inline("⏹️ إيقاف نهائي", b"stop_transfer")]
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
            # إرسال رمز التحقق
            code_request = await client.send_code_request(phone_number)
            return client, code_request
        else:
            # المستخدم مسجل بالفعل
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
        # يحتاج كلمة مرور التحقق بخطوتين
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

# الحصول على أعضاء المجموعة
async def get_group_members(client, group_identifier, limit=100):
    try:
        group_entity = await client.get_entity(group_identifier)
        participants = await client.get_participants(group_entity, limit=limit)
        return [user for user in participants if not user.bot and user.id != (await client.get_me()).id]
    except Exception as e:
        logger.error(f"خطأ في جلب الأعضاء: {str(e)}")
        return []

# نقل عضو إلى المجموعة الهدف
async def transfer_member(client, user, target_group):
    try:
        target_entity = await client.get_entity(target_group)
        
        # إضافة المستخدم إلى المجموعة
        await client.add_chat_members(target_entity, user)
        
        logger.info(f"تم نقل المستخدم {user.id} بنجاح")
        return True
    except Exception as e:
        logger.error(f"خطأ في نقل العضو {user.id}: {str(e)}")
        return False

# إنشاء رسالة الإحصائيات
async def create_statistics_message(session):
    progress = session.transfer_settings['current_count']
    total = session.transfer_settings['required_count']
    percentage = (progress / total) * 100 if total > 0 else 0
    remaining = total - progress
    speed = session.transfer_settings['adds_per_minute']
    estimated_time = remaining / speed if speed > 0 else 0
    
    return f"""📊 **إحصائيات النقل الحية**

🔄 **الحالة:** {'🟢 جاري النقل' if session.is_transfer_active else '🔴 متوقف'}
📈 **التقدم:** {progress} / {total}
📊 **النسبة:** {percentage:.1f}%
⚡ **السرعة:** {speed} عضو/دقيقة
⏳ **المتبقي:** {remaining} عضو
🕐 **الوقت المتوقع:** {estimated_time:.1f} دقيقة

📁 **المصدر:** {session.transfer_settings['source_group']}
🎯 **الهدف:** {session.transfer_settings['target_group']}

⏰ **آخر تحديث:** {datetime.now().strftime('%H:%M:%S')}"""

# عملية النقل الرئيسية
async def transfer_process(session):
    try:
        while (session.is_transfer_active and 
               session.transfer_settings['current_count'] < session.transfer_settings['required_count']):
            
            if not session.user_client:
                logger.error("عميل المستخدم غير متوفر")
                break
            
            # جلب الأعضاء من المصدر
            members = await get_group_members(
                session.user_client, 
                session.transfer_settings['source_group'], 
                limit=session.transfer_settings['adds_per_minute'] * 2
            )
            
            if not members:
                logger.info("لا يوجد أعضاء لنقلهم")
                break
            
            # تصفية الأعضاء الذين تم نقلهم مسبقاً
            available_members = [m for m in members if m.id not in session.transfer_settings['transferred_users']]
            
            if not available_members:
                logger.info("تم نقل جميع الأعضاء المتاحين")
                break
            
            # نقل الأعضاء
            successful_transfers = 0
            for member in available_members:
                if not session.is_transfer_active:
                    break
                    
                if successful_transfers >= session.transfer_settings['adds_per_minute']:
                    break
                
                success = await transfer_member(session.user_client, member, session.transfer_settings['target_group'])
                
                if success:
                    session.transfer_settings['current_count'] += 1
                    session.transfer_settings['transferred_users'].append(member.id)
                    successful_transfers += 1
                    logger.info(f"تم نقل العضو {member.id} بنجاح")
                
                # تأخير بين العمليات
                delay = 60 / session.transfer_settings['adds_per_minute']
                await asyncio.sleep(delay)
            
            # إذا لم يتم نقل أي عضو، ننتظر دقيقة ثم نحاول مرة أخرى
            if successful_transfers == 0:
                await asyncio.sleep(60)
            
    except Exception as e:
        logger.error(f"خطأ في عملية النقل: {str(e)}")
        session.is_transfer_active = False

# البوت الرئيسي
class TransferBot:
    def __init__(self):
        self.client = None
        self.user_bots = {}  # تخزين بوتات المستخدمين
        
    async def start_bot(self):
        """بدء البوت الرئيسي للتحكم"""
        self.client = TelegramClient('transfer_controller', API_ID, API_HASH)
        
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            session = get_user_session(user_id)
            
            welcome_text = """🚚 **نظام نقل الأعضاء المتقدم**

باستخدام حسابك الشخصي لنقل الأعضاء بين المجموعات

✅ **المميزات:**
- نقل الأعضاء باستخدام حسابك الشخصي
- تحكم كامل في السرعة والكمية
- إحصائيات حية محدثة
- نظام أمان متكامل

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
                    await self.set_target_group(event, session)
                elif data == 'set_count':
                    await self.set_required_count(event, session)
                elif data == 'set_speed':
                    await self.set_speed(event, session)
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
                    
                await event.answer()
            except Exception as e:
                logger.error(f"خطأ في معالجة الزر: {str(e)}")
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
        logger.info("🤖 البوت الرئيسي يعمل بنجاح!")
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
            elif session.current_operation == 'set_speed':
                await self.process_speed_input(event, session, text)
        except Exception as e:
            logger.error(f"خطأ في معالجة المدخلات: {str(e)}")
            await event.reply("❌ حدث خطأ أثناء معالجة البيانات")
    
    async def start_login(self, event, session):
        """بدء عملية تسجيل الدخول"""
        if session.is_authenticated and session.user_client:
            await event.edit("✅ **أنت مسجل بالفعل!**", buttons=create_setup_keyboard())
            return
        
        session.current_operation = 'login_phone'
        session.waiting_for_input = True
        
        await event.edit(
            "🔐 **تسجيل الدخول بحسابك الشخصي**\n\nأدخل رقم هاتفك بالصيغة الدولية:\n**مثال:** +966500000000",
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
            # إنشاء عميل المستخدم
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
            logger.error(f"خطأ في معالجة رقم الهاتف: {str(e)}")
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
            logger.error(f"خطأ في معالجة الكود: {str(e)}")
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
            logger.error(f"خطأ في معالجة كلمة المرور: {str(e)}")
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
            "📁 **إعداد المجموعة المصدر**\n\nأدخل معرف المجموعة أو الرابط:\n- @groupname\n- https://t.me/groupname\n- -100123456789",
            buttons=[[Button.inline("❌ إلغاء", b"back_main")]]
        )
    
    async def process_source_input(self, event, session, source):
        """معالجة إدخال المصدر"""
        try:
            # التحقق من صحة المجموعة
            entity = await session.user_client.get_entity(source)
            session.transfer_settings['source_group'] = entity.id
            
            await event.reply(f"✅ **تم تعيين المصدر:** {source}", buttons=create_setup_keyboard())
            session.current_operation = None
            
        except Exception as e:
            await event.reply("❌ لم أتمكن من الوصول إلى المجموعة، تأكد من الصلاحيات")
            session.waiting_for_input = True
    
    async def set_target_group(self, event, session):
        """إعداد المجموعة الهدف"""
        if not session.is_authenticated:
            await event.edit("❌ يرجى تسجيل الدخول أولاً!", buttons=create_setup_keyboard())
            return
        
        session.current_operation = 'set_target'
        session.waiting_for_input = True
        
        await event.edit(
            "🎯 **إعداد المجموعة الهدف**\n\nأدخل معرف المجموعة أو الرابط:",
            buttons=[[Button.inline("❌ إلغاء", b"back_main")]]
        )
    
    async def process_target_input(self, event, session, target):
        """معالجة إدخال الهدف"""
        try:
            entity = await session.user_client.get_entity(target)
            session.transfer_settings['target_group'] = entity.id
            
            await event.reply(f"✅ **تم تعيين الهدف:** {target}", buttons=create_setup_keyboard())
            session.current_operation = None
            
        except Exception as e:
            await event.reply
